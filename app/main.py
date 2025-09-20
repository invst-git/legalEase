from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import json
import os
import io

from app import models, schemas, auth, services, utils
from app.database import SessionLocal, create_db_and_tables
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from app import repository as fs_repo

create_db_and_tables()

app = FastAPI(
    title="Project Chimera",
    description="An AI-powered legal document analysis and co-pilot.",
    version="0.1.0",
)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    class _Anonymous:
        def __init__(self):
            self.id = 0
            self.email = "anonymous@local"

    if not token:
        return _Anonymous()
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return _Anonymous()
    except JWTError:
        return _Anonymous()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        return _Anonymous()
    return user

@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/analyses/me", response_model=list[schemas.AnalysisResult])
async def read_user_analyses(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return db.query(models.Analysis).filter(models.Analysis.owner_id == current_user.id).all()

@app.post("/analyze", response_model=schemas.IntelligentAnalysis)
async def analyze_document(
    document: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    # Validate allowed file types by extension and MIME
    allowed_exts = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
    allowed_mimes = {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'application/rtf',
        'text/rtf',
    }
    fname = document.filename or ''
    ext = ('.' + fname.split('.')[-1].lower()) if '.' in fname else ''
    if ext and ext not in allowed_exts and document.content_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, DOC, DOCX, TXT, RTF.")

    raw_bytes = await document.read()
    try:
        contents = await utils.extract_text_from_document(raw_bytes, document.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not contents or not any(contents): 
        raise HTTPException(status_code=400, detail="Could not extract text from the document.")
    
    # --- RE-INSTATED CLASSIFICATION CHECK ---
    document_classification = await services.classify_document_type(contents)
    if document_classification == "NonLegalDocument":
        raise HTTPException(
            status_code=400, 
            detail="The uploaded file does not appear to be a legal document. Please upload a relevant agreement or contract."
        )
    # --- END OF CHECK ---

    # Duplicate detection by content hash
    existing_id = await services.find_existing_analysis_by_hash(db, current_user.id, contents)
    if existing_id:
        # Load existing full analysis and return it (no new entry)
        fa = await services.get_full_analysis(db, existing_id, current_user.id)
        ia = await services.full_analysis_to_intelligent(fa)
        # Backfill page images for scanned PDFs if missing
        if not ia.extracted_text or (len(ia.extracted_text) == 1 and len(ia.extracted_text[0]) < 100):
            try:
                ia.page_images = await utils.get_page_images_if_scanned(raw_bytes, document.content_type)
            except Exception:
                ia.page_images = []
        return ia

    analysis_result = await services.process_large_document(contents)
    analysis_result.extracted_text = contents
    # Add scanned page images if applicable
    try:
        analysis_result.page_images = await utils.get_page_images_if_scanned(raw_bytes, document.content_type)
    except Exception:
        analysis_result.page_images = []

    # Firestore path (non-disruptive, gated by env)
    if os.getenv("DB_BACKEND", "").lower() == "firestore":
        try:
            creation = await services.create_analysis_record(
                current_user.id,
                document.filename,
                analysis_result.assessment,
                [item.model_dump() for item in analysis_result.key_info],
                [item.model_dump() for item in analysis_result.identified_actions],
            )
            analysis_result.id = creation.get("id")
            analysis_result.filename = document.filename
            analysis_result.created_at = creation.get("created_at")
            analysis_result.risk_level = await services.derive_risk_level(analysis_result)
            # Compute precomputed highlights for immediate rendering on first load
            try:
                analysis_result.risk_highlights = services.compute_risk_highlights_for_ia(analysis_result)
            except Exception:
                analysis_result.risk_highlights = []
            await services.persist_analysis_meta(db, {"id": analysis_result.id, "owner_id": current_user.id}, contents, analysis_result)
            # Save original PDF to GCS (optional best-effort)
            try:
                if (document.content_type or '').lower() == 'application/pdf':
                    fs_repo.upload_original_pdf(int(analysis_result.id), raw_bytes)
            except Exception:
                pass
            return analysis_result
        except Exception as e:
            # Graceful fallback to SQLite if Firestore is not configured/available
            print(f"Firestore unavailable, falling back to SQLite: {e}")

    # Default SQLite path
    db_analysis = models.Analysis(
        filename=document.filename,
        assessment=analysis_result.assessment,
        key_info_json=json.dumps([item.model_dump() for item in analysis_result.key_info]),
        actions_json=json.dumps([item.model_dump() for item in analysis_result.identified_actions]),
        owner_id=current_user.id
    )
    db.add(db_analysis)
    db.commit()
    # attach ids/metadata in response
    analysis_result.id = db_analysis.id
    analysis_result.filename = document.filename
    analysis_result.created_at = await services.now_iso()
    analysis_result.risk_level = await services.derive_risk_level(analysis_result)
    # Compute precomputed highlights for immediate rendering on first load
    try:
        analysis_result.risk_highlights = services.compute_risk_highlights_for_ia(analysis_result)
    except Exception:
        analysis_result.risk_highlights = []
    # persist updated risk_reason if set during derive
    await services.persist_analysis_meta(db, db_analysis, contents, analysis_result)
    # Save original PDF to local storage (best-effort)
    try:
        if (document.content_type or '').lower() == 'application/pdf':
            import os as _os
            folder = _os.path.join('data', 'uploads', f'analysis_{db_analysis.id}')
            _os.makedirs(folder, exist_ok=True)
            path = _os.path.join(folder, 'original.pdf')
            with open(path, 'wb') as f:
                f.write(raw_bytes)
    except Exception:
        pass
    return analysis_result


@app.get("/analyses/{analysis_id}/file")
async def get_analysis_file(analysis_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    # Ownership check via existing helper (non-disruptive)
    try:
        _ = await services.get_full_analysis(db, analysis_id, current_user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Firestore path: redirect to signed URL if available, else stream
    if os.getenv("DB_BACKEND", "").lower() == "firestore":
        try:
            url = fs_repo.get_original_pdf_signed_url(int(analysis_id))
            if url:
                return RedirectResponse(url)
        except Exception:
            pass
        # Fallback: attempt to stream (not optimal for large files)
        try:
            from google.cloud import storage as _storage
            st, bucket = fs_repo._st_client_bucket()  # type: ignore
            blob = bucket.blob(f"analyses/{analysis_id}/original.pdf")
            if not blob.exists():
                raise HTTPException(status_code=404, detail="Original file not found")
            data = blob.download_as_bytes()
            return StreamingResponse(io.BytesIO(data), media_type='application/pdf', headers={'Content-Disposition': 'inline'})
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Original file not found")

    # SQLite path: stream local file if present
    local_path = os.path.join('data', 'uploads', f'analysis_{analysis_id}', 'original.pdf')
    if not os.path.exists(local_path):
        raise HTTPException(status_code=404, detail="Original file not found")
    return FileResponse(local_path, media_type='application/pdf', headers={'Content-Disposition': 'inline'})

@app.post("/simulate", response_model=schemas.SimulationResponse)
async def simulate_risk(request: schemas.SimulationRequest, current_user: schemas.User = Depends(get_current_user)):
    # The 'key_info' from the request is already a list of dicts, no conversion needed.
    simulation_result = await services.get_risk_simulation(
        clause_text=request.clause_text,
        document_context=request.document_context,
        key_info=request.key_info
    )
    return schemas.SimulationResponse(simulation_text=simulation_result)

@app.post("/rewrite", response_model=schemas.RewriteResponse)
async def rewrite_clause(request: schemas.RewriteRequest, current_user: schemas.User = Depends(get_current_user)):
    rewritten_versions = await services.get_clause_rewrites(
        clause_key=request.clause_key,
        clause_text=request.clause_text,
        document_context=request.document_context
    )
    return schemas.RewriteResponse(rewritten_clauses=rewritten_versions)

@app.post("/analyses/{analysis_id}/locate", response_model=schemas.LocateResponse)
async def locate_highlight(
    analysis_id: int,
    request: schemas.LocateRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Return exact locations (page + text offsets and/or OCR boxes) for a given text."""
    try:
        ok = await services.has_analysis_access(db, analysis_id, current_user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return await services.locate_text_anchors(db, analysis_id, current_user.id, request.text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Locate failed: {e}")

@app.post("/benchmark", response_model=schemas.BenchmarkResponse)
async def benchmark_clause(request: schemas.BenchmarkRequest, current_user: schemas.User = Depends(get_current_user)):
    benchmark_data = await services.get_clause_benchmark(
        clause_text=request.clause_text,
        clause_key=request.clause_key
    )
    return schemas.BenchmarkResponse(**benchmark_data)

@app.post("/query", response_model=schemas.QueryResponse)
async def query_document(request: schemas.QueryRequest, current_user: schemas.User = Depends(get_current_user)):
    """
    Accepts a user question and returns an answer based on the document context.
    """
    result = await services.answer_user_question(request.question, request.full_text, request.history)
    # Optionally persist conversation if analysis_id provided
    if request.analysis_id:
        await services.append_conversation_message(
            analysis_id=request.analysis_id,
            owner_id=current_user.id,
            user_message={"role": "user", "content": request.question},
            assistant_message={"role": "assistant", "content": result.get("answer", "")}
        )
    # Ensure both required fields are present
    if not isinstance(result, dict):
        result = {}
    answer = result.get("answer", "The answer to this question could not be found in the provided document.")
    citation = result.get("citation", "")
    return schemas.QueryResponse(answer=answer, citation=citation)

@app.get("/analyses/dashboard", response_model=list[schemas.DashboardItem])
async def get_dashboard_items(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return await services.get_dashboard_list(db, current_user.id)

@app.get("/analyses/{analysis_id}", response_model=schemas.FullAnalysisResponse)
async def get_analysis(analysis_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return await services.get_full_analysis(db, analysis_id, current_user.id)

@app.post("/timeline", response_model=schemas.TimelineResponse)
async def generate_timeline(request: schemas.TimelineRequest, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return await services.generate_timeline(db, request.analysis_id, current_user.id)

@app.get("/timeline/{analysis_id}", response_model=schemas.TimelineResponse)
async def list_timeline(analysis_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return await services.list_timeline(db, analysis_id, current_user.id)

@app.post("/reminders", response_model=schemas.ReminderResponse)
async def create_reminder(request: schemas.ReminderRequest, current_user: schemas.User = Depends(get_current_user)):
    ok = await services.save_reminder(request.analysis_id, request.event_id, request.email, request.days_before)
    return schemas.ReminderResponse(success=ok)

@app.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(analysis_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    # Firestore path: lightweight ownership check, then delete
    if os.getenv("DB_BACKEND", "").lower() == "firestore":
        has_access = await services.has_analysis_access(db, analysis_id, current_user.id)
        if not has_access:
            raise HTTPException(status_code=404, detail="Analysis not found")
        await services.delete_analysis(db, analysis_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # SQLite path: Ensure the analysis exists and belongs to the current user
    analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id, models.Analysis.owner_id == current_user.id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await services.delete_analysis(db, analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/analyses/{analysis_id}/export")
async def export_analysis_pdf(
    analysis_id: int, 
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Export analysis as a downloadable PDF with original document attached.
    """
    # Check if PDF export is enabled
    if os.getenv("EXPORT_PDF_ENABLED", "true").lower() in ("false", "0", "no", "off"):
        raise HTTPException(status_code=503, detail="PDF export is currently disabled")
    
    # Get full analysis data with ownership check
    try:
        full_analysis = await services.get_full_analysis(db, analysis_id, current_user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get timeline data
    timeline_data = None
    try:
        timeline_response = await services.list_timeline(db, analysis_id, current_user.id)
        timeline_data = {
            "lifecycle_summary": timeline_response.lifecycle_summary,
            "events": [item.model_dump() if hasattr(item, 'model_dump') else item for item in timeline_response.events]
        }
    except Exception:
        # Timeline not available, continue without it
        timeline_data = None
    
    # Convert to dict for PDF generation
    analysis_data = {
        "id": full_analysis.id,
        "filename": full_analysis.filename,
        "created_at": full_analysis.created_at,
        "risk_level": full_analysis.risk_level,
        "risk_reason": full_analysis.risk_reason,
        "assessment": full_analysis.assessment,
        "key_info": [item.model_dump() if hasattr(item, 'model_dump') else item for item in full_analysis.key_info],
        "identified_actions": [item.model_dump() if hasattr(item, 'model_dump') else item for item in full_analysis.identified_actions],
        "timeline": timeline_data
    }
    
    # Get company name from environment
    company_name = os.getenv("COMPANY_NAME", "Your Company")
    
    # Create analysis PDF
    analysis_pdf_bytes = utils.create_analysis_pdf(analysis_data, company_name)
    
    # Try to get original document
    original_bytes = None
    original_filename = full_analysis.filename or "document"
    original_mime_type = "application/pdf"  # Default assumption
    
    # Determine original file type from filename
    if original_filename.lower().endswith('.docx'):
        original_mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif original_filename.lower().endswith('.doc'):
        original_mime_type = "application/msword"
    elif original_filename.lower().endswith('.txt'):
        original_mime_type = "text/plain"
    elif original_filename.lower().endswith('.rtf'):
        original_mime_type = "application/rtf"
    
    # Try to retrieve original document
    try:
        # Firestore path
        if os.getenv("DB_BACKEND", "").lower() == "firestore":
            try:
                # Try to get from GCS
                from google.cloud import storage as _storage
                st, bucket = fs_repo._st_client_bucket()  # type: ignore
                blob = bucket.blob(f"analyses/{analysis_id}/original.pdf")
                if blob.exists():
                    original_bytes = blob.download_as_bytes()
            except Exception:
                pass
        else:
            # SQLite path - try local file
            local_path = os.path.join('data', 'uploads', f'analysis_{analysis_id}', 'original.pdf')
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    original_bytes = f.read()
    except Exception:
        # Original document not found - continue with analysis-only PDF
        pass
    
    # Generate final PDF
    if original_bytes:
        if original_mime_type == "application/pdf":
            # Merge PDFs
            final_pdf_bytes = utils.merge_pdf_with_original(analysis_pdf_bytes, original_bytes)
        else:
            # Attach non-PDF as attachment
            final_pdf_bytes = utils.attach_non_pdf_original(
                analysis_pdf_bytes, 
                original_bytes, 
                original_filename, 
                original_mime_type
            )
            # Add notice page about attachment
            notice_page = utils.create_attachment_notice_page(original_filename)
            notice_reader = pypdf.PdfReader(io.BytesIO(notice_page))
            analysis_reader = pypdf.PdfReader(io.BytesIO(final_pdf_bytes))
            writer = pypdf.PdfWriter()
            
            # Add analysis pages
            for page in analysis_reader.pages:
                writer.add_page(page)
            
            # Add notice page
            for page in notice_reader.pages:
                writer.add_page(page)
            
            # Write final PDF
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            final_pdf_bytes = output_buffer.getvalue()
            output_buffer.close()
    else:
        # No original document - just return analysis PDF
        final_pdf_bytes = analysis_pdf_bytes
    
    # Generate filename
    safe_filename = "".join(c for c in original_filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
    if not safe_filename:
        safe_filename = "document"
    export_filename = f"analysis_{analysis_id}_{safe_filename}_export.pdf"
    
    # Return PDF as streaming response
    return StreamingResponse(
        io.BytesIO(final_pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{export_filename}\"",
            "Content-Length": str(len(final_pdf_bytes))
        }
    )
