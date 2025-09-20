import os
import json
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv
from app.schemas import IntelligentAnalysis
from google.cloud import vision
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
try:
    from google.cloud import documentai_v1 as documentai
except Exception:
    documentai = None
import google.auth
import base64
import requests
import sqlite3
import numpy as np
import hashlib
import datetime
from sqlalchemy.orm import Session
import re
from app import models, schemas
from app import repository as fs_repo

# Load environment variables
load_dotenv()

DB_BACKEND = os.getenv("DB_BACKEND", "").lower()
AI_PROVIDER = os.getenv("AI_PROVIDER", "").lower()

# Configure AI model
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception:
    print("Error: GOOGLE_API_KEY not found or invalid.")
    model = None

# Define safety settings appropriate for analyzing professional/legal documents
# This reduces the chance of false positives on dense legal text.
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# Enforce concise assessments (2-3 sentences, reasonable length)
def _shorten_assessment(text: str, max_sentences: int = 3, max_chars: int = 600) -> str:
    try:
        if not text:
            return text
        s = " ".join((text or "").split())
        # Simple sentence split heuristic
        parts = re.split(r"(?<=[\.!?])\s+", s)
        if not parts:
            parts = [s]
        clipped = " ".join(parts[:max_sentences]).strip()
        if len(clipped) > max_chars:
            clipped = (clipped[: max(0, max_chars - 1)].rstrip() + "…") if len(clipped) > 0 else clipped
        return clipped
    except Exception:
        return text

# ---- OCR Function (Swapped to Document AI with Vision fallback) ----
async def extract_text_with_ocr(image_bytes_list: list[bytes]) -> list[str]:
    """Runs OCR for a list of page images and returns a list of per-page texts.

    Preference order:
    1) Document AI (if configured/available)
    2) Fallback to Cloud Vision (previous behavior)
    """
    processor_id = os.environ.get("DOCAI_PROCESSOR_ID")
    location = os.environ.get("DOCAI_LOCATION", "us")
    project_id = os.environ.get("DOCAI_PROJECT_ID")
    if not project_id:
        try:
            creds, default_project = google.auth.default()
            if default_project:
                project_id = default_project
        except Exception:
            project_id = None

    # Try Document AI first when processor info is available
    if processor_id and project_id and documentai is not None:
        try:
            try:
                da_client = documentai.DocumentProcessorServiceAsyncClient()
                name = da_client.processor_path(project_id, location, processor_id)
                tasks = []
                for img in image_bytes_list:
                    raw_document = documentai.RawDocument(content=img, mime_type="image/png")
                    req = documentai.ProcessRequest(name=name, raw_document=raw_document)
                    tasks.append(da_client.process_document(request=req))
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                page_texts: list[str] = []
                for r in responses:
                    if isinstance(r, Exception):
                        print(f"Document AI error for one page: {r}")
                        page_texts.append("")
                        continue
                    txt = ""
                    if getattr(r, "document", None) and getattr(r.document, "text", ""):
                        txt = r.document.text
                    page_texts.append(txt)
                # If at least one page produced text, return the list
                if any(t.strip() for t in page_texts):
                    return page_texts
            except Exception as e_async:
                # Fallback to sync client in thread executor
                print(f"Doc AI async client unavailable, trying sync: {e_async}")
                da_client_sync = documentai.DocumentProcessorServiceClient()
                name = da_client_sync.processor_path(project_id, location, processor_id)
                loop = asyncio.get_event_loop()

                def _process_one(img: bytes) -> str:
                    raw_document = documentai.RawDocument(content=img, mime_type="image/png")
                    req = documentai.ProcessRequest(name=name, raw_document=raw_document)
                    resp = da_client_sync.process_document(request=req)
                    try:
                        return resp.document.text if resp and resp.document else ""
                    except Exception as e:
                        print(f"Document AI sync error for one page: {e}")
                        return ""

                texts = await asyncio.gather(*[loop.run_in_executor(None, _process_one, img) for img in image_bytes_list])
                if any(t.strip() for t in texts):
                    return list(texts)
        except Exception as e:
            print(f"Document AI OCR failed, will try Vision fallback: {e}")

    # Vision fallback (keeps app behavior if Doc AI not configured)
    try:
        client = vision.ImageAnnotatorAsyncClient()
        requests = []
        for image_content in image_bytes_list:
            image = vision.Image(content=image_content)
            features = [vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
            requests.append(vision.AnnotateImageRequest(image=image, features=features))

        response = await client.batch_annotate_images(requests=requests)
        page_texts: list[str] = []
        for annotation in response.responses:
            if annotation.error.message:
                print(f"Cloud Vision API Error for one page: {annotation.error.message}")
            txt = ""
            if annotation.full_text_annotation:
                txt = annotation.full_text_annotation.text
            page_texts.append(txt)
        return page_texts
    except Exception as e:
        print(f"An error occurred during OCR processing: {e}")
        return [f"Error: OCR processing failed. Details: {str(e)}"]


# ---- UPDATED: Intelligent Analysis Function ----
# In app/services.py

# ... (keep all other functions and imports) ...

# In app/services.py

# ... (keep all other functions and imports) ...

async def get_intelligent_analysis(text: str) -> IntelligentAnalysis:
    if not model: raise ValueError("Generative model not initialized.")
    prompt = f"""
    You are a meticulous legal analyst AI. Your sole purpose is to extract, classify, and summarize information directly from the provided text. Adhere strictly to all instructions.

    ### Instruction 1: Extract Key Information (`key_info`)
    Extract key data points. For each item, you MUST set `is_negotiable` AND `is_benchmarkable`.
    - `is_negotiable: true` for rules, conditions, or financial amounts.
    - `is_negotiable: false` for factual identifiers like names, addresses, dates.
    - `is_benchmarkable: true` for quantifiable terms with a market standard (Rent, Security Deposit, Notice Period).
    - `is_benchmarkable: false` for unique facts (Party Name, Address).

    ### Instruction 2: Extract Obligations (`identified_actions`)
    Extract specific duties and obligations. For each, you MUST also set `is_negotiable` and `is_benchmarkable`.
    - DO NOT provide generic advice. Extract ONLY from the text provided.

    ### Instruction 3: Generate an Assessment (`assessment`)
    Provide a brief, 2-3 sentence summary of the document's overall purpose.

    ### JSON Output Schema:
    Respond ONLY with a valid JSON object that follows this exact schema.
    {{
      "key_info": [
        {{ "key": "Monthly Rent", "value": "...", "is_negotiable": true, "is_benchmarkable": true }}
      ],
      "identified_actions": [
        {{ "text": "Tenant shall pay a security deposit of ₹50,000.", "is_negotiable": true, "is_benchmarkable": true }}
      ],
      "assessment": "..."
    }}

    ### Document Text to Analyze:
    ---
    {text}
    ---
    """
    try:
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        if not response.text: raise ValueError(f"AI response blocked. Details: {response.prompt_feedback}")
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_response)
        # Ensure assessment stays concise
        if isinstance(data, dict) and isinstance(data.get("assessment"), str):
            data["assessment"] = _shorten_assessment(data["assessment"])
        return IntelligentAnalysis(**data)
    except Exception as e:
        # Return a structured error
        return IntelligentAnalysis(
            key_info=[{"key": "Error", "value": "Failed to analyze", "is_negotiable": False, "is_benchmarkable": False}],
            identified_actions=[], assessment=f"AI model failed to process. Details: {e}", extracted_text=[]
        )

# ---- UPDATED: Function to Summarize a Single Chunk ----
async def summarize_chunk(chunk: str) -> str:
    if not model:
        return "Error: Model not initialized."
    try:
        prompt = f"Concisely summarize the key entities, obligations, dates, and important clauses from the following section of a legal document. Focus only on the most critical information.\n\n---\n{chunk}"
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        
        if not response.text:
            print(f"A chunk summary was blocked. Finish Reason: {response.prompt_feedback.block_reason}.")
            return "" # Return empty string for a blocked chunk

        return response.text.strip()
    except Exception as e:
        print(f"Error summarizing chunk: {e}")
        return ""


# ---- Main Orchestrator for Large Document Processing (Unchanged) ----
async def process_large_document(chunks: list[str]) -> IntelligentAnalysis:
    # ... (This function remains exactly the same as before) ...
    if len(chunks) <= 3:
        print("Document is small. Performing direct analysis.")
        full_text = "\n".join(chunks)
        return await get_intelligent_analysis(full_text)

    print(f"Document is large ({len(chunks)} pages). Running detailed per-chunk analysis...")
    analysis_tasks = [get_intelligent_analysis(chunk) for chunk in chunks]
    results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

    combined_key_info: list[schemas.KeyInfoItem] = []
    combined_actions: list[schemas.ActionItem] = []
    assessments: list[str] = []
    errors_encountered = False

    for idx, result in enumerate(results, start=1):
        if isinstance(result, Exception):
            errors_encountered = True
            print(f"Chunk analysis failed for section {idx}: {result}")
            continue
        combined_key_info.extend(result.key_info or [])
        combined_actions.extend(result.identified_actions or [])
        if result.assessment:
            assessments.append(result.assessment.strip())

    if not combined_key_info and not combined_actions:
        print("Per-chunk analysis produced no results; falling back to full document analysis.")
        full_text = "\n".join(chunks)
        return await get_intelligent_analysis(full_text)

    assessment_text = " ".join(filter(None, assessments)).strip()
    if not assessment_text:
        assessment_text = "Unable to generate assessment from individual sections."
        if errors_encountered:
            assessment_text += " Some sections may have failed during analysis."
    # Keep final assessment brief
    assessment_text = _shorten_assessment(assessment_text)

    return IntelligentAnalysis(
        key_info=combined_key_info,
        identified_actions=combined_actions,
        assessment=assessment_text,
    )

async def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

async def derive_risk_level(analysis: IntelligentAnalysis) -> str:
    # Qualitative heuristic based on severity, balance, clarity extracted via the model
    # Fallback to action count if needed.
    try:
        actions_text = "\n".join([f"- {item.text}" for item in (analysis.identified_actions or [])])
        full_doc_text = "\n".join(analysis.extracted_text or [])
        prompt = f"""
        You are a legal risk assessor. Read the entire document text AND the list of obligations/clauses below, then rate the overall document risk as Low, Medium, or High considering these factors:
        1) Severity (how demanding the obligations are),
        2) Balance (whether obligations are one-sided), and
        3) Clarity (vagueness increases risk).

        Always base your assessment on the full document context; use the clauses list as additional guidance.

        Also provide a brief explanation with the top 2-3 drivers of risk.

        Respond ONLY in JSON with this schema:
        {{
          "risk_level": "Low|Medium|High",
          "reason": "One short paragraph with 2-3 key clauses and why they matter."
        }}

        Full Document Text:
        ---
        {full_doc_text}
        ---

        Clauses (for convenience):
        ---
        {actions_text}
        ---
        """
        generation_config = GenerationConfig(response_mime_type="application/json")
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS, generation_config=generation_config)
        data = json.loads((response.text or "{}").strip())
        level = (data.get("risk_level") or "").title()
        if level not in {"Low", "Medium", "High"}:
            level = "Medium" if len(analysis.identified_actions or []) >= 4 else "Low"
        analysis.risk_reason = data.get("reason", "")
        return level
    except Exception:
        count = len(analysis.identified_actions or [])
        return "High" if count >= 8 else ("Medium" if count >= 4 else "Low")

def _hash_content(pages: list[str]) -> str:
    h = hashlib.sha256()
    for p in pages:
        h.update((p or "").encode("utf-8"))
    return h.hexdigest()

async def persist_analysis_meta(db: Session, analysis: models.Analysis | dict, pages: list[str], ia: IntelligentAnalysis) -> None:
    # Common values
    content_hash = _hash_content(pages)
    risk = await derive_risk_level(ia)
    created_at = await now_iso()

    # Firestore backend
    if fs_repo.is_firestore_enabled():
        analysis_id = getattr(analysis, 'id', None) or (analysis.get('id') if isinstance(analysis, dict) else None)
        owner_id = getattr(analysis, 'owner_id', None) or (analysis.get('owner_id') if isinstance(analysis, dict) else 0)
        try:
            fs_repo.persist_meta(
                analysis_id=int(analysis_id),
                owner_id=int(owner_id or 0),
                pages=pages,
                page_images=getattr(ia, 'page_images', None) or [],
                risk_level=risk,
                risk_reason=getattr(ia, 'risk_reason', None) or "",
                content_hash=content_hash,
            )
        except Exception as _:
            pass
        return

    # Default SQLite backend
    existing = db.query(models.AnalysisMeta).filter(models.AnalysisMeta.analysis_id == analysis.id).first()
    if existing:
        existing.created_at = existing.created_at or created_at
        existing.extracted_text_json = existing.extracted_text_json or json.dumps(pages)
        existing.risk_level = risk
        existing.risk_reason = ia.risk_reason or existing.risk_reason or ""
        existing.content_hash = existing.content_hash or content_hash
        # Save page images if provided
        if not getattr(existing, 'page_images_json', None):
            try:
                existing.page_images_json = json.dumps(ia.page_images or [])
            except Exception:
                existing.page_images_json = json.dumps([])
        db.add(existing)
    else:
        meta = models.AnalysisMeta(
            analysis_id=analysis.id,
            owner_id=analysis.owner_id,
            created_at=created_at,
            extracted_text_json=json.dumps(pages),
            page_images_json=json.dumps(ia.page_images or []),
            risk_level=risk,
            risk_reason=ia.risk_reason or "",
            content_hash=content_hash,
            conversation_json=json.dumps([]),
        )
        db.add(meta)
    db.commit()

async def get_dashboard_list(db: Session, owner_id: int) -> list[schemas.DashboardItem]:
    if fs_repo.is_firestore_enabled():
        try:
            rows = fs_repo.list_dashboard(owner_id)
            return [schemas.DashboardItem(id=r["id"], filename=r.get("filename", ""), created_at=r.get("created_at"), risk_level=r.get("risk_level")) for r in rows]
        except Exception:
            return []
    items = db.query(models.Analysis, models.AnalysisMeta).join(models.AnalysisMeta, models.Analysis.id == models.AnalysisMeta.analysis_id).filter(models.Analysis.owner_id == owner_id).all()
    result = []
    for a, m in items:
        result.append(schemas.DashboardItem(id=a.id, filename=a.filename, created_at=m.created_at, risk_level=m.risk_level))
    return result

async def get_full_analysis(db: Session, analysis_id: int, owner_id: int) -> schemas.FullAnalysisResponse:
    if fs_repo.is_firestore_enabled():
        data = fs_repo.get_full_analysis(analysis_id, owner_id)
        key_info = [schemas.KeyInfoItem(**item) for item in data.get("key_info", [])]
        actions = [schemas.ActionItem(**item) for item in data.get("identified_actions", [])]
        pages = data.get("extracted_text", []) or []
        page_images = data.get("page_images", []) or []
        conversation = [schemas.ChatMessage(**msg) for msg in data.get("conversation", [])]
        fa = schemas.FullAnalysisResponse(
            id=int(data.get("id") or analysis_id),
            filename=data.get("filename", ""),
            assessment=data.get("assessment", ""),
            key_info=key_info,
            identified_actions=actions,
            extracted_text=pages,
            page_images=page_images,
            created_at=data.get("created_at"),
            risk_level=data.get("risk_level"),
            risk_reason=data.get("risk_reason"),
            conversation=conversation,
        )
        # Compute risk highlights (best-effort, no failures bubble up)
        try:
            fa.risk_highlights = _compute_risk_highlights_from_fa(fa)
        except Exception:
            fa.risk_highlights = []
        # Prewarm OCR cache for scanned PDFs (first few pages) in background
        try:
            if fa.page_images:
                asyncio.create_task(_prewarm_scanned_pages_ocr(int(fa.id), fa.page_images))
        except Exception:
            pass
        return fa
    a = db.query(models.Analysis).filter(models.Analysis.id == analysis_id, models.Analysis.owner_id == owner_id).first()
    if not a:
        raise ValueError("Analysis not found")
    m = db.query(models.AnalysisMeta).filter(models.AnalysisMeta.analysis_id == analysis_id, models.AnalysisMeta.owner_id == owner_id).first()
    key_info = [schemas.KeyInfoItem(**item) for item in json.loads(a.key_info_json or "[]")]
    actions = [schemas.ActionItem(**item) for item in json.loads(a.actions_json or "[]")]
    pages = json.loads(m.extracted_text_json or "[]") if m else []
    page_images = json.loads(getattr(m, 'page_images_json', '[]') or '[]') if m else []
    conversation_raw = json.loads(m.conversation_json or "[]") if m else []
    conversation = [schemas.ChatMessage(**msg) for msg in conversation_raw]
    fa = schemas.FullAnalysisResponse(
        id=a.id,
        filename=a.filename,
        assessment=a.assessment or "",
        key_info=key_info,
        identified_actions=actions,
        extracted_text=pages,
        page_images=page_images,
        created_at=m.created_at if m else None,
        risk_level=m.risk_level if m else None,
        risk_reason=m.risk_reason if m else None,
        conversation=conversation,
    )
    # Compute risk highlights (best-effort)
    try:
        fa.risk_highlights = _compute_risk_highlights_from_fa(fa)
    except Exception:
        fa.risk_highlights = []
    # Prewarm OCR cache for scanned PDFs (first few pages) in background
    try:
        if fa.page_images:
            asyncio.create_task(_prewarm_scanned_pages_ocr(int(fa.id), fa.page_images))
    except Exception:
        pass
    return fa

async def append_conversation_message(analysis_id: int, owner_id: int, user_message: dict, assistant_message: dict) -> None:
    if fs_repo.is_firestore_enabled():
        try:
            fs_repo.append_conversation_message(analysis_id, owner_id, user_message, assistant_message)
        except Exception:
            pass
        return
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        meta = db.query(models.AnalysisMeta).filter(models.AnalysisMeta.analysis_id == analysis_id, models.AnalysisMeta.owner_id == owner_id).first()
        if not meta:
            return
        convo = json.loads(meta.conversation_json or "[]")
        convo.append(user_message)
        convo.append(assistant_message)
        meta.conversation_json = json.dumps(convo)
        db.add(meta)
        db.commit()
    finally:
        db.close()

async def has_analysis_access(db: Session, analysis_id: int, owner_id: int) -> bool:
    """Lightweight existence/ownership check, Firestore-aware."""
    if fs_repo.is_firestore_enabled():
        try:
            return fs_repo.check_owner(analysis_id, owner_id)
        except Exception:
            return False
    # SQLite path
    a = db.query(models.Analysis).filter(models.Analysis.id == analysis_id, models.Analysis.owner_id == owner_id).first()
    return bool(a)

async def find_existing_analysis_by_hash(db: Session, owner_id: int, pages: list[str]) -> int | None:
    content_hash = _hash_content(pages)
    if fs_repo.is_firestore_enabled():
        try:
            return fs_repo.find_by_content_hash(owner_id, content_hash)
        except Exception:
            return None
    m = db.query(models.AnalysisMeta).filter(
        models.AnalysisMeta.owner_id == owner_id,
        models.AnalysisMeta.content_hash == content_hash
    ).first()
    return m.analysis_id if m else None

async def full_analysis_to_intelligent(fa: schemas.FullAnalysisResponse) -> schemas.IntelligentAnalysis:
    return schemas.IntelligentAnalysis(
        key_info=fa.key_info,
        identified_actions=fa.identified_actions,
        assessment=fa.assessment,
        extracted_text=fa.extracted_text,
        page_images=getattr(fa, 'page_images', []) or [],
        id=fa.id,
        filename=fa.filename,
        risk_level=fa.risk_level,
        created_at=fa.created_at,
    )

# --- Timeline generation ---
async def generate_timeline(db: Session, analysis_id: int, owner_id: int) -> schemas.TimelineResponse:
    fa = await get_full_analysis(db, analysis_id, owner_id)
    # Build prompts with extracted text and key info to identify dates/events
    doc_text = "\n".join(fa.extracted_text or [])
    key_info_str = "\n".join([f"- {k.key}: {k.value}" for k in (fa.key_info or [])])
    prompt = f"""
    You are an assistant that extracts a legal agreement lifecycle timeline.
    From the Document Text and Key Info, find:
    - Agreement start and end dates (key_date)
    - Recurring payment due dates (payment_due) with the monthly day
    - Critical action deadlines (action_required), like renewal/termination notice deadlines
    Provide a brief lifecycle summary.

    Respond ONLY in JSON with this schema:
    {{
      "lifecycle_summary": "...",
      "events": [
        {{"date": "YYYY-MM-DD", "label": "...", "kind": "key_date|payment_due|action_required", "description": "..."}}
      ]
    }}

    Key Info:
    ---
    {key_info_str}
    ---
    Document Text:
    ---
    {doc_text[:8000]}
    ---
    """
    generation_config = GenerationConfig(response_mime_type="application/json")
    try:
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS, generation_config=generation_config)
        data = json.loads((response.text or "{}").strip())
    except Exception:
        data = {"lifecycle_summary": "Timeline unavailable.", "events": []}

    # Persist events
    raw_events = data.get("events", []) or []
    lifecycle_summary = data.get("lifecycle_summary", "")

    if fs_repo.is_firestore_enabled():
        stored = fs_repo.replace_timeline(analysis_id, owner_id, raw_events, lifecycle_summary)
        items = [schemas.TimelineEvent(id=None, date=e.get("date", ""), label=e.get("label", ""), kind=e.get("kind", "key_date"), description=e.get("description", "")) for e in stored]
        return schemas.TimelineResponse(lifecycle_summary=lifecycle_summary, events=items)

    # SQLite path
    db.query(models.TimelineEvent).filter(models.TimelineEvent.analysis_id == analysis_id).delete()
    events = []
    for e in raw_events:
        # Normalize fields and skip events with missing/invalid dates to satisfy NOT NULL constraint
        date_str = (e.get("date") or "").strip()
        if not date_str:
            continue
        try:
            datetime.date.fromisoformat(date_str)
        except Exception:
            continue
        label = (e.get("label") or "").strip()
        kind = (e.get("kind") or "key_date").strip() or "key_date"
        description = (e.get("description") or "").strip()
        te = models.TimelineEvent(
            analysis_id=analysis_id,
            date=date_str,
            label=label,
            kind=kind,
            description=description,
        )
        db.add(te)
        events.append(te)
    db.commit()
    stored = db.query(models.TimelineEvent).filter(models.TimelineEvent.analysis_id == analysis_id).all()
    items = [schemas.TimelineEvent(id=ev.id, date=ev.date, label=ev.label, kind=ev.kind, description=ev.description) for ev in stored]
    return schemas.TimelineResponse(lifecycle_summary=lifecycle_summary, events=items)

async def list_timeline(db: Session, analysis_id: int, owner_id: int) -> schemas.TimelineResponse:
    _ = await get_full_analysis(db, analysis_id, owner_id) # ownership check
    if fs_repo.is_firestore_enabled():
        summary, items_raw = fs_repo.list_timeline(analysis_id, owner_id)
        items = [schemas.TimelineEvent(id=None, date=e.get("date", ""), label=e.get("label", ""), kind=e.get("kind", "key_date"), description=e.get("description", "")) for e in items_raw]
        summary = summary or ("" if items else "No timeline events found for this analysis.")
        return schemas.TimelineResponse(lifecycle_summary=summary, events=items)
    stored = db.query(models.TimelineEvent).filter(models.TimelineEvent.analysis_id == analysis_id).all()
    items = [schemas.TimelineEvent(id=ev.id, date=ev.date, label=ev.label, kind=ev.kind, description=ev.description) for ev in stored]
    summary = "" if items else "No timeline events found for this analysis."
    return schemas.TimelineResponse(lifecycle_summary=summary, events=items)

async def save_reminder(analysis_id: int, event_id: int, email: str, days_before: int) -> bool:
    # Placeholder: hook to email scheduling system; currently accept and no-op
    print(f"Reminder scheduled: analysis={analysis_id}, event={event_id}, email={email}, days_before={days_before}")
    return True

async def delete_analysis(db: Session, analysis_id: int) -> bool:
    """Delete an analysis and its related metadata/events."""
    if fs_repo.is_firestore_enabled():
        try:
            return fs_repo.delete_analysis(analysis_id)
        except Exception:
            return False
    # SQLite path
    db.query(models.TimelineEvent).filter(models.TimelineEvent.analysis_id == analysis_id).delete()
    db.query(models.AnalysisMeta).filter(models.AnalysisMeta.analysis_id == analysis_id).delete()
    db.query(models.Analysis).filter(models.Analysis.id == analysis_id).delete()
    db.commit()
    return True

async def get_risk_simulation(clause_text: str, document_context: str, key_info: list) -> str:
    """
    Generates a realistic risk scenario for a specific legal clause, using the full document context.
    """
    if not model:
        raise ValueError("Generative model not initialized.")

    # Convert key_info list to a more readable string format for the prompt
    key_info_str = "\n".join([f"- {item['key']}: {item['value']}" for item in key_info])

    prompt = f"""
    Act as a pragmatic risk analyst. You will be given the key facts from a legal document, a general assessment, and one specific clause.
    Your task is to generate a realistic, negative consequence scenario for the provided clause.

    **CRITICAL INSTRUCTION:** You MUST use the correct names and roles of the parties as defined in the 'Key Facts' section in your scenario. Do not confuse the parties.

    **Key Facts from Document:**
    {key_info_str}

    **General Document Assessment:**
    {document_context}

    **Clause to Analyze:**
    "{clause_text}"

    **Generate the risk simulation now (2-4 sentences), concluding with brief, actionable advice:**
    """
    try:
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        
        if not response.text:
            raise ValueError(f"The AI response was blocked. Details: {response.prompt_feedback}")
            
        return response.text.strip()
    except Exception as e:
        print(f"An error occurred during risk simulation: {e}")
        return f"Error: Could not generate a risk simulation. Details: {str(e)}"
    
async def get_clause_rewrites(clause_key: str, clause_text: str, document_context: str) -> list[str]:
    """
    Generates alternative, more favorable phrasings for a legal clause.
    """
    if not model:
        raise ValueError("Generative model not initialized.")

    prompt = f"""
    Act as an expert legal negotiator providing advice to one party in a negotiation.
    You will be given the context of a legal document and a specific clause from it.
    Your task is to rewrite the clause to be more favorable to the primary user (e.g., the Tenant, the Borrower, the Employee).

    Instructions:
    1.  Generate exactly THREE distinct alternative phrasings.
    2.  Each alternative should be clear, professional, and legally sound.
    3.  Briefly label each version's approach (e.g., "More Balanced," "Slightly More Favorable," "Assertive Position").
    4.  Return ONLY the rewritten clauses as a numbered list. Do not add any extra explanations or conversational text.

    **Document Context:**
    {document_context}

    **Clause to Rewrite ("{clause_key}"):**
    "{clause_text}"

    **Generate the three rewritten versions now:**
    """
    try:
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        if not response.text:
            raise ValueError(f"The AI response was blocked. Details: {response.prompt_feedback}")
        
        # Split the response into a list of clauses
        # The model is prompted to return a numbered list, so we split by newline
        clauses = [clause.strip() for clause in response.text.strip().split('\n') if clause.strip()]
        return clauses
    except Exception as e:
        print(f"An error occurred during clause rewrite: {e}")
        return [f"Error: Could not generate rewrites. Details: {str(e)}"]
    

async def classify_document_type(page_chunks: list[str]) -> str:
    """
    Classifies a document as 'LegalAgreement' or 'NonLegalDocument' using:
    1) Cheap lexical/structural cue scoring per page with early exits.
    2) If inconclusive, LLM verification on top-K most informative pages.
    """
    if not model:
        raise ValueError("Generative model not initialized.")

    def _normalize(s: str) -> str:
        return (s or "").strip()

    def _compute_legal_cue_score(text: str) -> float:
        t = (_normalize(text)).lower()
        if not t:
            return 0.0
        score = 0.0
        # Title/keywords (strong signals)
        title_keywords = [
            "agreement", "contract", "lease", "addendum", "master service agreement",
            "terms and conditions", "statement of work", "non-disclosure agreement",
            "confidentiality agreement", "employment agreement", "loan agreement",
            "purchase agreement"
        ]
        first_300 = t[:300]
        score += sum(2.0 for kw in title_keywords if kw in first_300)

        # Legal markers
        legal_markers = [
            "whereas", "in witness whereof", "governing law", "indemnif", "confidential",
            "term and termination", "force majeure", "severab", "assignment", "liability",
            "warranty", "entire agreement", "notices"
        ]
        score += sum(1.0 for kw in legal_markers if kw in t)

        # Structure cues: numbered sections/clauses
        numbered = re.findall(r"^\s*\d+(?:\.\d+)*\s+", t, flags=re.MULTILINE)
        score += min(5, len(numbered)) * 0.5
        if "section" in t or "clause" in t:
            score += 0.5

        # Parties / signature blocks
        party_defs = ["this agreement is between", "by and between", "the parties"]
        score += sum(1.5 for kw in party_defs if kw in t)
        signature_markers = ["signed:", "signature", "by:", "name:", "title:"]
        score += sum(0.5 for kw in signature_markers if kw in t[-800:])  # near end

        # Dates/money density
        date_hits = len(re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|\b\d{4}\b", t))
        money_hits = len(re.findall(r"[$€£]\s*\d|\b\d{1,3}(?:,\d{3})+\b|\b\d+%\b", t))
        length = max(1, len(t))
        score += 3.0 * ((date_hits + money_hits) / (length / 1000))  # per 1k chars
        return score

    def _select_informative_pages(pages: list[str], k: int = 3) -> list[str]:
        scored = [(i, _compute_legal_cue_score(p or "")) for i, p in enumerate(pages)]
        scored.sort(key=lambda x: x[1], reverse=True)
        # take top k non-empty scores
        top = [pages[i] for i, s in scored[:k] if s > 0]
        # if all zero, fallback to first/middle/last as a safety
        if not top:
            if not pages:
                return []
            if len(pages) <= 3:
                return pages
            mid = len(pages) // 2
            return [pages[0], pages[mid], pages[-1]]
        return top

    pages = page_chunks or []
    if not pages:
        return "NonLegalDocument"

    # Early exits using cue scoring
    scores = [_compute_legal_cue_score(p or "") for p in pages]
    max_score = max(scores) if scores else 0.0
    sum_scores = sum(scores)
    first_page_score = scores[0] if scores else 0.0

    # High-confidence legal: strong signals on first page or any page
    if first_page_score >= 4.0 or max_score >= 6.0 or sum_scores >= 10.0:
        return "LegalAgreement"
    # High-confidence non-legal: no signals across pages
    if sum_scores < 1.0 and max_score < 1.0:
        return "NonLegalDocument"

    # Inconclusive → LLM verification on top-K informative pages
    sample_pages = _select_informative_pages(pages, k=3)
    text_sample = "\n\n---\n\n".join(sample_pages)[:6000]

    try:
        prompt = f"""
        You are a document classification AI. Your task is to determine if the provided text, sampled from a document, is from a legal agreement or a non-legal document.

        First, analyze the sample for legal-document signals (e.g., "WHEREAS", numbered clauses, party definitions, signature blocks).

        Finally, provide your answer as one of two possible single-word strings: 'LegalAgreement' or 'NonLegalDocument'.

        Text sample(s) to classify:
        ---
        {text_sample}
        ---
        """
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        if (response.text or "").find("LegalAgreement") != -1:
            return "LegalAgreement"
        return "NonLegalDocument"
    except Exception as e:
        print(f"An error occurred during document classification: {e}")
        # Fall back to cue decision (conservative)
        return "NonLegalDocument" if sum_scores < 3.0 else "LegalAgreement"
    
DB_FILE = "benchmark.db"

def find_similar_clauses(query_embedding: list, top_k: int = 3) -> list:
    """Finds the most similar clauses from the SQLite DB using cosine similarity."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT text, category, embedding FROM clauses")
    all_clauses = cursor.fetchall()
    conn.close()

    query_vec = np.array(query_embedding)
    similarities = []
    for text, category, embedding_json in all_clauses:
        db_vec = np.array(json.loads(embedding_json))
        # Calculate cosine similarity
        similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
        similarities.append((similarity, text, category))
    
    # Sort by similarity and return the top_k
    similarities.sort(key=lambda x: x[0], reverse=True)
    return similarities[:top_k]
    
async def get_clause_benchmark(clause_text: str) -> dict:
    """
    Analyzes a clause against the benchmark database using semantic search.
    """
    if not model:
        raise ValueError("Generative model not initialized.")
    
    try:
        # 1. Generate an embedding for the user's clause
        result = genai.embed_content(model='models/text-embedding-004',
                                     content=clause_text,
                                     task_type="RETRIEVAL_QUERY")
        query_embedding = result['embedding']
        
        # 2. Find the top 3 most similar clauses from our DB
        similar_clauses = find_similar_clauses(query_embedding, top_k=3)
        
        if not similar_clauses:
            return {"benchmark_result": "Could not find comparable clauses in the benchmark data.", "examples": []}

        # 3. Analyze the categories of the similar clauses
        categories = [category for _, _, category in similar_clauses]
        examples = [text for _, text, _ in similar_clauses]
        
        # Simple logic: if any strict clauses are found, flag it as strict.
        if any("Strict" in c for c in categories):
            benchmark_result = "This clause appears stricter than the market standard."
        elif any("Lenient" in c for c in categories):
            benchmark_result = "This clause appears more lenient than the market standard."
        else:
            benchmark_result = "This clause appears to be a standard market term."
            
        return {"benchmark_result": benchmark_result, "examples": examples}

    except Exception as e:
        print(f"An error occurred during benchmarking: {e}")
        return {"benchmark_result": f"Error during analysis: {e}", "examples": []}
    
def _is_subjective_question(question: str) -> bool:
    """Heuristic detection for subjective/judgment questions."""
    q = (question or "").lower()
    subjective_terms = [
        "fair", "unfair", "favorable", "favourable", "good for me", "bad for me",
        "risky", "risk overall", "overall risk", "standard", "market standard",
        "balanced", "reasonable", "is this good", "is this bad", "is this ok",
        "is this okay", "is this typical", "is this favourable", "favourable to",
        "favorable to", "advantage", "disadvantage", "pro or con", "pros and cons"
    ]
    return any(term in q for term in subjective_terms)

async def answer_user_question(question: str, full_text: str, history: list | None = None) -> dict:
    """
    Answers a user's question based ONLY on the provided document text.
    """
    if not model: raise ValueError("Generative model not initialized.")
    
    # Prepare recent conversation history (last 10 turns) for follow-up context
    history = history or []
    def _format_msg(m):
        if isinstance(m, dict):
            role = m.get('role', 'user')
            content = m.get('content', '')
        else:
            role = getattr(m, 'role', 'user')
            content = getattr(m, 'content', '')
        role = (role or 'user').upper()
        return f"{role}: {content}"
    formatted_history = "\n".join([_format_msg(m) for m in history[-10:]])

    subjective = _is_subjective_question(question)
    if subjective:
        prompt = f"""
        You are Clause Oracle — Document-Grounded Legal Q&A Co‑Pilot.
        Identity rule: If the user's question asks for your name or who you are, respond ONLY with "Clause Oracle — Document-Grounded Legal Q&A Co‑Pilot".
        You are a document-grounded, informational co-pilot.
        Your job is to provide a balanced, factual analysis based only on the Document Text.

        IMPORTANT: The user's question is subjective (e.g., about fairness, favorability, risk, or whether terms are standard). In such cases you MUST:
        1) Begin with a clear disclaimer that you cannot provide a legal opinion (no legal advice).
        2) Provide a balanced factual analysis grounded in the document, with two titled sections:
           - "Key clauses that may be considered favorable to [Party X]"
           - "Key clauses that may be considered favorable to [Party Y]"
           Where possible, infer the party roles (e.g., Landlord/Tenant, Company/Employee) from the document; otherwise use "Party A" and "Party B". Under each, list specific terms with brief summaries grounded in the text. Keep a neutral tone.
        3) Conclude with guidance: suggest using the Risk Simulation tool on specific clauses and the Negotiation Helper for potentially unfavorable terms. End with a final disclaimer to consult a qualified professional for legal advice.

        Output rules:
        - Return ONLY JSON with fields: "answer" and "citation".
        - Put the full three-part response in "answer" as plain text with clear section headings.
        - Set "citation" to an empty string.

        ---
        CONVERSATION HISTORY (most recent first):
        {formatted_history}
        ---
        DOCUMENT TEXT:
        {full_text}
        ---
        USER QUESTION: "{question}"
        """
    else:
        prompt = f"""
        You are Clause Oracle — Document-Grounded Legal Q&A Co‑Pilot.
        Identity rule: If the user's question asks for your name or who you are, respond ONLY with "Clause Oracle — Document-Grounded Legal Q&A Co‑Pilot".
        You are a specialized Question & Answering AI.
        Your primary task is to answer the user's question based on the provided document text. Stay grounded in the document.

        Conversation rules:
        - Use the conversation history to understand follow-ups; do not repeat prior answers unless needed.
        - If the user asks for a simple explanation of a common concept (e.g., "what is a late fee"), give a brief, plain-language definition AND immediately relate it back to the document's specific terms if present.
        - Remain informational, not advisory. Do not opine on fairness or enforceability.
        - If the answer cannot be found in the document, respond exactly: "The answer to this question could not be found in the provided document."

        Steps:
        1. Read the conversation history and the user's question.
        2. Search the Document Text for the most relevant passage.
        3. Formulate a concise, direct answer, grounded in the text. If you added a general explanation, tie it back to the document specifics.
        4. Provide the exact quote from the document that supports the answer.

        Respond ONLY with a valid JSON object following this schema:
        {{
          "answer": "Your concise answer here.",
          "citation": "The direct quote from the document that supports the answer."
        }}

        ---
        CONVERSATION HISTORY (most recent first):
        {formatted_history}
        ---
        DOCUMENT TEXT:
        {full_text}
        ---
        USER QUESTION: "{question}"
        """
    # Vertex AI path (only for Clause Oracle). Do not fallback to other providers.
    if AI_PROVIDER == "vertex":
        try:
            # Import locally to avoid hard dependency when not enabled
            from app import ai_provider as _ap
            # Vertex client is sync; use a thread to avoid blocking the loop
            import asyncio as _asyncio
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    data = await _asyncio.to_thread(_ap.generate_oracle_json, prompt)
                    if not isinstance(data, dict):
                        data = {"answer": str(data or ""), "citation": ""}
                    data.setdefault("answer", "")
                    data.setdefault("citation", "")
                    return data
                except Exception as e:
                    last_err = e
                    # brief backoff before retrying
                    if attempt < 2:
                        await _asyncio.sleep(0.5 * (2 ** attempt))
            print(f"Vertex AI path failed after retries: {last_err}")
            return {"answer": "An error occurred while querying Vertex AI. Please try again.", "citation": ""}
        except Exception as e:
            print(f"Vertex AI setup failed: {e}")
            return {"answer": "Vertex AI is not configured correctly.", "citation": ""}

    # Default provider path (used only when AI_PROVIDER != "vertex")
    try:
        generation_config = GenerationConfig(response_mime_type="application/json")
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS, generation_config=generation_config)
        try:
            data = json.loads(response.text)
        except Exception:
            text = (response.text or '').strip()
            data = {"answer": text, "citation": ""}
        return data
    except Exception as e:
        print(f"An error occurred during Q&A: {e}")
        return {"answer": "An error occurred while processing your question.", "citation": ""}


# --- Firestore-specific create (analyses) ---
async def create_analysis_record(owner_id: int, filename: str, assessment: str, key_info: list, actions: list) -> dict:
    """Create an analysis record in Firestore and return {id, created_at}.

    SQLite is not handled here; call this only if Firestore is enabled.
    """
    if not fs_repo.is_firestore_enabled():
        raise RuntimeError("Firestore backend not enabled")
    try:
        return fs_repo.create_analysis(owner_id, filename, assessment, key_info, actions)
    except Exception as e:
        raise RuntimeError(f"Failed to create analysis in Firestore: {e}")


# --- Highlight location (anchors on demand) ---
import unicodedata as _ud

def _normalize_with_map(s: str) -> tuple[str, list[int]]:
    """Return a lenient, lowercased, whitespace-collapsed string and a map from
    normalized indices back to original indices. Removes soft hyphens, zero-width,
    unifies quotes and hyphens, and strips most punctuation that frequently differs.
    """
    if not s:
        return "", []
    # NFKD to strip accents
    s = _ud.normalize('NFKD', s)
    # Strip control chars
    s = s.replace("\u00AD", "").replace("\u200B", "")
    out = []
    idx_map: list[int] = []
    prev_was_space = False
    i = 0
    L = len(s)
    while i < L:
        ch = s[i]
        # Handle hyphenation at line breaks: '-\n' -> ''
        if ch == '-' and i + 1 < L and s[i+1] in ('\n', '\r'):
            i += 2
            continue
        # Collapse whitespace to single space
        if ch.isspace():
            if not prev_was_space:
                out.append(' ')
                idx_map.append(i)
                prev_was_space = True
            i += 1
            continue
        prev_was_space = False
        # Normalize common punctuation variants
        if ch in '“”"′’‘`´ʼʹ’':
            ch = '"' if ch in '“”"' else "'"
        if ch in '–—‑':  # en/em/nb hyphens
            ch = '-'
        # Remove punctuation we don't want to match on
        # Keep: hyphen, digits, letters, percent
        if not (ch.isalnum() or ch in ['-', '%']):
            i += 1
            continue
        out.append(ch.lower())
        idx_map.append(i)
        i += 1
    # Remove leading/trailing spaces if any
    norm = ''.join(out).strip()
    # Rebuild idx_map for trimmed spaces
    if out and (out[0] == ' ' or out[-1] == ' '):
        # find first/last non-space in out
        start = 0
        end = len(out)
        while start < end and out[start] == ' ': start += 1
        while end > start and out[end-1] == ' ': end -= 1
        norm = ''.join(out[start:end])
        idx_map = idx_map[start:end]
    return norm, idx_map

_STOPWORDS = set('''a an and are as at be by for from has have in into is it its of on or that the this to will shall with each per including include includes such such as if then than whereas whereof thereof thereof herein hereby thereof pursuant under between both either neither not no nor any all more most least less few upon within without once when whenever while whose which who whom what where why how their there they're them they we you your our ours mine his her hers him he she i do does did can could may might must should would'''.split())

def _tokenize_norm(s: str) -> list[str]:
    return [t for t in (s or '').split(' ') if t]

def _salient_tokens(tokens: list[str]) -> set[str]:
    sal = set()
    for t in tokens:
        if t in _STOPWORDS:
            continue
        if len(t) >= 4 or any(c.isdigit() for c in t) or ('-' in t) or ('/' in t):
            sal.add(t)
    return sal

def _best_scored_window(q_tokens: list[str], salient: set[str], page_norm: str) -> tuple[int, int, int, int] | None:
    """Return the best matching window (start,end,tokens_matched,salient_count)
    by scanning all contiguous token windows (len -> 3). Requires at least one
    salient token in the window to avoid generic matches.
    """
    if not q_tokens:
        return None
    token_join = ' '.join
    best: tuple[int,int,int,int] | None = None
    # Try decreasing window sizes
    for win in range(len(q_tokens), 2, -1):
        for i in range(0, len(q_tokens) - win + 1):
            window = q_tokens[i:i+win]
            sal_count = sum(1 for t in window if t in salient)
            if sal_count == 0:
                continue  # skip generic windows
            phrase = token_join(window)
            pos = page_norm.find(phrase)
            if pos >= 0:
                cand = (pos, pos + len(phrase), win, sal_count)
                if best is None:
                    best = cand
                else:
                    # Prefer more tokens, then more salient, then earlier position
                    if cand[2] > best[2] or (cand[2] == best[2] and cand[3] > best[3]) or (cand[2] == best[2] and cand[3] == best[3] and cand[0] < best[0]):
                        best = cand
        if best is not None:
            # early break if we found a window of this size
            break
    return best

def _expand_to_full_lines(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a span to cover full line(s) bounded by newlines. Handles \r\n, \n, and \r.
    Returns (start, end) in original string indices.
    """
    if start < 0 or end < 0 or start >= end:
        return start, end
    n = len(text or "")
    if n == 0:
        return start, end
    # Find previous line break
    s = start
    i = start - 1
    while i >= 0:
        ch = text[i]
        if ch == '\n' or ch == '\r':
            s = i + 1
            break
        i -= 1
    # Find next line break
    e = end
    j = end
    while j < n:
        ch = text[j]
        if ch == '\n' or ch == '\r':
            e = j
            break
        j += 1
    return max(0, s), min(n, e)

def _score_action_text(t: str) -> int:
    """Heuristic severity score for an obligation string."""
    if not t:
        return 0
    s = t.lower()
    score = 0
    # Strong risk terms
    strong = ["indemnif", "termination", "terminate", "liability", "unlimited", "default", "remedy", "waiver"]
    for kw in strong:
        if kw in s:
            score += 5
    # Financial/penalty
    fin = ["penalt", "late fee", "interest", "liquidated", "damages", "fee", "fine", "%", "$"]
    for kw in fin:
        if kw in s:
            score += 3
    # Restrictive covenants / jurisdiction
    cov = ["non-compete", "noncompete", "non-solicit", "nonsolicit", "exclusiv", "governing law", "jurisdiction", "venue", "sole discretion"]
    for kw in cov:
        if kw in s:
            score += 2
    # Deadlines / notices
    if "notice" in s or "days" in s:
        score += 1
    # Magnify by length a bit to prefer more specific items
    score += min(5, len(s) // 80)
    return score

def _is_risky_action_text(t: str) -> bool:
    """Classify whether an obligation text is risky enough to highlight.
    Uses keyword families across multiple risk themes.
    """
    if not t:
        return False
    s = t.lower()
    themes = [
        ["assumption of risk", "accepts all risk", "at own risk", "hold harmless", "indemnif"],
        ["unlimited liability", "no cap", "without limit", "waiver", "waive rights"],
        ["confidential", "non-disclosure", "penalt", "fine", "per day", "per word"],
        ["governing law", "jurisdiction", "venue", "exclusive", "sole discretion"],
        ["terminate", "termination for convenience", "default", "remedy"],
        ["liquidated damages", "late fee", "% interest", "interest", "%"],
    ]
    hits = 0
    for fam in themes:
        if any(kw in s for kw in fam):
            hits += 1
    # Also consider numeric/monetary cues
    num_money = any(ch.isdigit() for ch in s) and ("$" in s or "%" in s)
    return hits >= 1 or num_money or _score_action_text(t) >= 5

def _find_best_anchor_in_pages(pages: list[str], query_text: str) -> tuple[int, int, int, str] | None:
    """Return (page_idx, start, end, strategy) for best match of query across pages using
    the same normalization and windowing approach as locate_text_anchors.
    """
    if not query_text:
        return None
    q_norm, _ = _normalize_with_map(query_text)
    if not q_norm:
        return None
    q_tokens = _tokenize_norm(q_norm)
    q_salient = _salient_tokens(q_tokens)
    candidates: list[tuple[int, int, int, int, int, str]] = []
    # (score, page_idx, start_char, end_char, norm_pos, strategy)
    for idx, page_text in enumerate(pages or []):
        if not page_text:
            continue
        norm, idx_map = _normalize_with_map(page_text)
        pos = norm.find(q_norm)
        if pos >= 0:
            start = idx_map[pos] if pos < len(idx_map) else 0
            end_norm = pos + len(q_norm)
            end = idx_map[end_norm-1] + 1 if end_norm-1 < len(idx_map) else start + len(query_text)
            score = 1_000_000 + (end - start)
            candidates.append((score, idx, start, end, pos, "text:normalized"))
        else:
            if q_tokens:
                found = _best_scored_window(q_tokens, q_salient, norm)
                if found:
                    s, e, win, sal = found
                    start = idx_map[s] if s < len(idx_map) else 0
                    end = idx_map[e-1] + 1 if e-1 < len(idx_map) else start
                    if end > start:
                        score = win*100 + sal*10
                        candidates.append((score, idx, start, end, s, "text:ngram"))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1], x[4]))
    _, page_idx, start, end, _, strategy = candidates[0]
    return page_idx, start, end, strategy

def _compute_risk_highlights_from_fa(fa: schemas.FullAnalysisResponse) -> list[schemas.AnchorMatch]:
    """Select multiple risky obligations and return their best line-bounded anchors.
    Returns a list for fast, zero-lag rendering.
    """
    actions = getattr(fa, 'identified_actions', None) or []
    pages = getattr(fa, 'extracted_text', None) or []
    if not actions or not pages:
        return []
    # Score and filter risky items
    items: list[tuple[int, int, str]] = []  # (score, len, text)
    risky_texts: list[str] = []
    for a in actions:
        try:
            txt = getattr(a, 'text', None) or (a.get('text') if isinstance(a, dict) else '')
        except Exception:
            txt = ''
        if not txt:
            continue
        sc = _score_action_text(txt)
        if _is_risky_action_text(txt):
            risky_texts.append(txt)
        items.append((sc, len(txt), txt))
    if not risky_texts:
        # Fallback: take top 5 by score
        items.sort(key=lambda x: (-x[0], -x[1]))
        risky_texts = [t for _, _, t in items[:5]]
    # Build anchors for each risky text (cap to 12)
    matches: list[schemas.AnchorMatch] = []
    seen_spans: set[tuple[int,int,int]] = set()  # (page, start, end)
    for txt in risky_texts[:12]:
        found = _find_best_anchor_in_pages(pages, txt)
        if not found:
            continue
        page_idx, s, e, strategy = found
        s2, e2 = _expand_to_full_lines(pages[page_idx], s, e)
        key = (page_idx, s2, e2)
        if key in seen_spans:
            continue
        seen_spans.add(key)
        match = schemas.AnchorMatch(page_index=page_idx, char_start=s2, char_end=e2, strategy=(strategy + "+risk"))
        # If scanned pages exist, compute OCR box as well
        try:
            if getattr(fa, 'page_images', None) and page_idx is not None and 0 <= page_idx < len(fa.page_images):
                cache_key = (int(getattr(fa, 'id', 0) or 0), int(page_idx))
                cached = _OCR_CACHE.get(cache_key)
                if cached is None:
                    _get_or_build_ocr_cache_for_page_sync(int(getattr(fa, 'id', 0) or 0), int(page_idx), fa.page_images[page_idx])
                    cached = _OCR_CACHE.get(cache_key)
                if cached is not None:
                    agg_norm, norm2raw, idx_map, W, H = cached
                    q_raw = (pages[page_idx] or '')[s2:e2]
                    q_norm2, _ = _normalize_with_map(q_raw)
                    q_tokens = _tokenize_norm(q_norm2)
                    q_salient = _salient_tokens(q_tokens)
                    mpos = agg_norm.find(q_norm2) if q_norm2 else -1
                    mend = mpos + len(q_norm2) if mpos >= 0 else -1
                    if mpos < 0 and q_tokens:
                        found2 = _best_scored_window(q_tokens, q_salient, agg_norm)
                        if found2:
                            mpos, mend, _, _ = found2
                    if mpos >= 0 and mend > mpos:
                        s_raw = norm2raw[mpos] if mpos < len(norm2raw) else 0
                        e_raw = norm2raw[mend-1] + 1 if mend-1 < len(norm2raw) else s_raw
                        x_min = y_min = 1.0
                        x_max = y_max = 0.0
                        found_any = False
                        for s0, e0, rect in idx_map:
                            if e0 <= s_raw:
                                continue
                            if s0 >= e_raw:
                                break
                            x, y, w, h = rect
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x + w)
                            y_max = max(y_max, y + h)
                            found_any = True
                        if found_any:
                            pad = 0.005
                            x_min = max(0.0, x_min - pad)
                            y_min = max(0.0, y_min - pad)
                            x_max = min(1.0, x_max + pad)
                            y_max = min(1.0, y_max + pad)
                            match.boxes = [schemas.AnchorBox(x=x_min, y=y_min, w=max(0.0, x_max - x_min), h=max(0.0, y_max - y_min))]
                            match.strategy = (match.strategy or "") + "+ocr"
        except Exception:
            pass
        matches.append(match)
    return matches

def compute_risk_highlights_for_ia(ia: schemas.IntelligentAnalysis) -> list[schemas.AnchorMatch]:
    """Compute risky line highlight(s) from an IntelligentAnalysis object.
    Mirrors the FA-based method but avoids requiring a full FA.
    """
    try:
        actions = getattr(ia, 'identified_actions', None) or []
        pages = getattr(ia, 'extracted_text', None) or []
        if not actions or not pages:
            return []
        # Score and filter risky items
        items: list[tuple[int, int, str]] = []
        risky_texts: list[str] = []
        for a in actions:
            try:
                txt = getattr(a, 'text', None) or (a.get('text') if isinstance(a, dict) else '')
            except Exception:
                txt = ''
            if not txt:
                continue
            sc = _score_action_text(txt)
            if _is_risky_action_text(txt):
                risky_texts.append(txt)
            items.append((sc, len(txt), txt))
        if not risky_texts:
            items.sort(key=lambda x: (-x[0], -x[1]))
            risky_texts = [t for _, _, t in items[:5]]
        matches: list[schemas.AnchorMatch] = []
        seen_spans: set[tuple[int,int,int]] = set()
        for txt in risky_texts[:12]:
            found = _find_best_anchor_in_pages(pages, txt)
            if not found:
                continue
            page_idx, s, e, strategy = found
            s2, e2 = _expand_to_full_lines(pages[page_idx], s, e)
            key = (page_idx, s2, e2)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            match = schemas.AnchorMatch(page_index=page_idx, char_start=s2, char_end=e2, strategy=(strategy + "+risk"))
        # If scanned images exist, attempt to compute OCR box as well
        try:
            if getattr(ia, 'page_images', None) and page_idx is not None and 0 <= page_idx < len(ia.page_images):
                aid = int(getattr(ia, 'id', 0) or 0)
                cache = _get_or_build_ocr_cache_for_page_sync(aid, int(page_idx), ia.page_images[page_idx])
                if cache:
                    agg_norm, norm2raw, idx_map, W, H = cache
                    q_raw = (pages[page_idx] or '')[s2:e2]
                    q_norm2, _ = _normalize_with_map(q_raw)
                    q_tokens = _tokenize_norm(q_norm2)
                    q_salient = _salient_tokens(q_tokens)
                    mpos = agg_norm.find(q_norm2) if q_norm2 else -1
                    mend = mpos + len(q_norm2) if mpos >= 0 else -1
                    if mpos < 0 and q_tokens:
                        found2 = _best_scored_window(q_tokens, q_salient, agg_norm)
                        if found2:
                            mpos, mend, _, _ = found2
                    if mpos >= 0 and mend > mpos:
                        s_raw = norm2raw[mpos] if mpos < len(norm2raw) else 0
                        e_raw = norm2raw[mend-1] + 1 if mend-1 < len(norm2raw) else s_raw
                        x_min = y_min = 1.0
                        x_max = y_max = 0.0
                        found_any = False
                        for s0, e0, rect in idx_map:
                            if e0 <= s_raw:
                                continue
                            if s0 >= e_raw:
                                break
                            x, y, w, h = rect
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x + w)
                            y_max = max(y_max, y + h)
                            found_any = True
                        if found_any:
                            pad = 0.005
                            x_min = max(0.0, x_min - pad)
                            y_min = max(0.0, y_min - pad)
                            x_max = min(1.0, x_max + pad)
                            y_max = min(1.0, y_max + pad)
                            match.boxes = [schemas.AnchorBox(x=x_min, y=y_min, w=max(0.0, x_max - x_min), h=max(0.0, y_max - y_min))]
                            match.strategy = (match.strategy or "") + "+ocr"
        except Exception:
            pass
        matches.append(match)
        # continue building all matches (do not return early)
        
        
        
        
        
        
        return matches
    except Exception:
        return []
def _get_or_build_ocr_cache_for_page_sync(analysis_id: int, pidx: int, data_uri: str):
    """Populate OCR cache for a scanned page synchronously using Cloud Vision (fallback).
    Returns the cached tuple or None on failure. Only used for scanned pages.
    """
    try:
        key = (int(analysis_id), int(pidx))
        cached = _OCR_CACHE.get(key)
        if cached is not None:
            return cached
        if not data_uri:
            return None
        img_bytes = None
        if data_uri.startswith('data:image'):
            try:
                b64 = data_uri.split(',', 1)[1]
                img_bytes = base64.b64decode(b64)
            except Exception:
                img_bytes = None
        elif data_uri.startswith('http://') or data_uri.startswith('https://'):
            try:
                r = requests.get(data_uri, timeout=5)
                r.raise_for_status()
                img_bytes = r.content
            except Exception:
                img_bytes = None
        if not img_bytes:
            return None
        # Prefer Document AI if configured (synchronous client)
        try:
            processor_id = os.environ.get("DOCAI_PROCESSOR_ID")
            location = os.environ.get("DOCAI_LOCATION", "us")
            project_id = os.environ.get("DOCAI_PROJECT_ID")
            if not project_id:
                try:
                    creds, default_project = google.auth.default()
                    if default_project:
                        project_id = default_project
                except Exception:
                    project_id = None
            if documentai is not None and processor_id and project_id:
                da_client_sync = documentai.DocumentProcessorServiceClient()
                name = da_client_sync.processor_path(project_id, location, processor_id)
                raw_document = documentai.RawDocument(content=img_bytes, mime_type="image/png")
                req = documentai.ProcessRequest(name=name, raw_document=raw_document)
                resp = da_client_sync.process_document(request=req)
                doc = getattr(resp, 'document', None)
                if doc and getattr(doc, 'text', None) is not None:
                    agg_raw = doc.text or ''
                    try:
                        page0 = doc.pages[0]
                        dim = getattr(page0, 'dimension', None)
                        W = float(getattr(dim, 'width', 1.0) or 1.0)
                        H = float(getattr(dim, 'height', 1.0) or 1.0)
                    except Exception:
                        W = H = 1.0
                        page0 = None
                    idx_map = []
                    if page0 is not None:
                        for token in getattr(page0, 'tokens', []) or []:
                            layout = getattr(token, 'layout', None)
                            if not layout:
                                continue
                            ta = getattr(layout, 'text_anchor', None)
                            segs = getattr(ta, 'text_segments', []) if ta else []
                            if not segs:
                                continue
                            start_raw = int(getattr(segs[0], 'start_index', 0) or 0)
                            end_raw = int(getattr(segs[0], 'end_index', 0) or 0)
                            bp = getattr(layout, 'bounding_poly', None)
                            rect = (0.0, 0.0, 0.0, 0.0)
                            if bp is not None:
                                nvs = getattr(bp, 'normalized_vertices', None)
                                if nvs:
                                    xs = [v.x for v in nvs]
                                    ys = [v.y for v in nvs]
                                    x0, x1 = min(xs), max(xs)
                                    y0, y1 = min(ys), max(ys)
                                    rect = (max(0.0, x0), max(0.0, y0), max(0.0, (x1 - x0)), max(0.0, (y1 - y0)))
                                else:
                                    vs = getattr(bp, 'vertices', None) or []
                                    if vs:
                                        xs = [v.x for v in vs]
                                        ys = [v.y for v in vs]
                                        x0, x1 = min(xs), max(xs)
                                        y0, y1 = min(ys), max(ys)
                                        rect = (max(0.0, x0 / W), max(0.0, y0 / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                            idx_map.append((start_raw, end_raw, rect))
                    agg_norm, norm2raw = _normalize_with_map(agg_raw)
                    _OCR_CACHE[key] = (agg_norm, norm2raw, idx_map, W, H)
                    return _OCR_CACHE.get(key)
        except Exception:
            pass
        # Cloud Vision synchronous fallback
        try:
            from google.cloud import vision as _vision
            client = _vision.ImageAnnotatorClient()
            image = _vision.Image(content=img_bytes)
            response = client.document_text_detection(image=image)
            fta = response.full_text_annotation
            if not fta or not getattr(fta, 'pages', None):
                return None
            page = fta.pages[0]
            W = float(page.width or 1)
            H = float(page.height or 1)
            tokens = []
            for block in page.blocks:
                for para in block.paragraphs:
                    for word in para.words:
                        t = "".join([s.text for s in word.symbols])
                        poly = word.bounding_box
                        xs = [v.x for v in poly.vertices]
                        ys = [v.y for v in poly.vertices]
                        x0, x1 = min(xs), max(xs)
                        y0, y1 = min(ys), max(ys)
                        rect = (max(0.0, x0 / W), max(0.0, (y0) / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                        tokens.append((t, rect))
            agg = []
            raw_idx_map = []
            pos0 = 0
            for t, rect in tokens:
                if not t:
                    continue
                if agg:
                    agg.append(' ')
                    pos0 += 1
                agg.append(t)
                s0 = pos0
                pos0 += len(t)
                raw_idx_map.append((s0, pos0, rect))
            agg_raw = ''.join(agg)
            agg_norm, norm2raw = _normalize_with_map(agg_raw)
            _OCR_CACHE[key] = (agg_norm, norm2raw, raw_idx_map, W, H)
            return _OCR_CACHE.get(key)
        except Exception:
            return None
    except Exception:
        return None

_OCR_CACHE: dict[
    tuple[int, int],
    tuple[str, list[int], list[tuple[int,int,tuple[float,float,float,float]]], float, float]
] = {}

async def locate_text_anchors(db: Session, analysis_id: int, owner_id: int, query_text: str) -> schemas.LocateResponse:
    """Find exact occurrences of query_text in the document.

    - For text pages: returns page + char ranges (exact, case-insensitive).
    - For scanned pages with images: also returns OCR-based bounding boxes for exact token spans.
    """
    if not query_text or not query_text.strip():
        return schemas.LocateResponse(matches=[])

    fa = await get_full_analysis(db, analysis_id, owner_id)
    pages = fa.extracted_text or []
    q_raw = query_text or ""
    q_norm, _ = _normalize_with_map(q_raw)
    q_tokens = _tokenize_norm(q_norm)
    q_salient = _salient_tokens(q_tokens)
    candidates: list[tuple[int, int, int, int, int, str]] = []
    # (score, page_idx, start_char, end_char, norm_pos, strategy)
    best_phrase_norm: str | None = None

    # Pass 1: text exact match (case-insensitive) per page
    for idx, page_text in enumerate(pages):
        if not page_text:
            continue
        norm, idx_map = _normalize_with_map(page_text)
        pos = norm.find(q_norm) if q_norm else -1
        if pos >= 0:
            start = idx_map[pos] if pos < len(idx_map) else 0
            end_norm = pos + len(q_norm)
            end = idx_map[end_norm-1] + 1 if end_norm-1 < len(idx_map) else start + len(q_raw)
            score = 1_000_000 + (end - start)
            candidates.append((score, idx, start, end, pos, "text:normalized"))
        else:
            if q_tokens:
                found = _best_scored_window(q_tokens, q_salient, norm)
                if found:
                    s, e, win, sal = found
                    start = idx_map[s] if s < len(idx_map) else 0
                    end = idx_map[e-1] + 1 if e-1 < len(idx_map) else start
                    if end > start:
                        score = win*100 + sal*10
                        candidates.append((score, idx, start, end, s, "text:ngram"))

    if not candidates:
        return schemas.LocateResponse(matches=[])
    # choose best candidate across all pages
    candidates.sort(key=lambda x: (-x[0], x[1], x[4]))
    best_score, best_page, best_start, best_end, best_norm_pos, best_strategy = candidates[0]
    match = schemas.AnchorMatch(page_index=best_page, char_start=best_start, char_end=best_end, strategy=best_strategy)

    # Build the normalized phrase actually matched to feed OCR matching
    try:
        page_norm, idx_map = _normalize_with_map(pages[best_page])
        if best_strategy.startswith("text:normalized"):
            best_phrase_norm = page_norm[best_norm_pos: best_norm_pos + len(q_norm)] if q_norm else None
        else:
            # Approximate: slice norm from s..e
            best_phrase_norm = page_norm[best_norm_pos: best_norm_pos + (best_end - best_start)]
    except Exception:
        best_phrase_norm = q_norm

    # If scanned (page_images available) and we have a match on a page, compute OCR boxes for that page only
    if (getattr(fa, 'page_images', None) or []) and best_page is not None:
        try:
            from google.cloud import vision as _vision
            client = _vision.ImageAnnotatorAsyncClient()
            pidx = int(best_page)
            data_uri = fa.page_images[pidx] if pidx < len(fa.page_images) else ""
            img_bytes: bytes | None = None
            if data_uri and data_uri.startswith("data:image"):
                cache_key = (int(analysis_id), pidx)
                cached = _OCR_CACHE.get(cache_key)
                if cached is None:
                    # OCR this page
                    try:
                        b64 = data_uri.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64)
                    except Exception:
                        img_bytes = b""
            elif data_uri and (data_uri.startswith("http://") or data_uri.startswith("https://")):
                cache_key = (int(analysis_id), pidx)
                cached = _OCR_CACHE.get(cache_key)
                if cached is None:
                    try:
                        r = requests.get(data_uri, timeout=5)
                        r.raise_for_status()
                        img_bytes = r.content
                    except Exception:
                        img_bytes = None
            else:
                cached = None

            if (cache_key := (int(analysis_id), pidx)) and _OCR_CACHE.get(cache_key) is None and img_bytes is not None:
                # Prefer Document AI OCR if configured
                processor_id = os.environ.get("DOCAI_PROCESSOR_ID")
                location = os.environ.get("DOCAI_LOCATION", "us")
                project_id = os.environ.get("DOCAI_PROJECT_ID")
                if not project_id:
                    try:
                        creds, default_project = google.auth.default()
                        if default_project:
                            project_id = default_project
                    except Exception:
                        project_id = None
                used_docai = False
                if documentai is not None and processor_id and project_id:
                    try:
                        da_client_sync = documentai.DocumentProcessorServiceClient()
                        name = da_client_sync.processor_path(project_id, location, processor_id)
                        raw_document = documentai.RawDocument(content=img_bytes, mime_type="image/png")
                        req = documentai.ProcessRequest(name=name, raw_document=raw_document)
                        resp = da_client_sync.process_document(request=req)
                        doc = getattr(resp, 'document', None)
                        if doc and getattr(doc, 'text', None) is not None:
                            # Build token map from Document AI tokens
                            agg_raw = doc.text or ''
                            try:
                                page0 = doc.pages[0]
                                dim = getattr(page0, 'dimension', None)
                                W = float(getattr(dim, 'width', 1.0) or 1.0)
                                H = float(getattr(dim, 'height', 1.0) or 1.0)
                            except Exception:
                                W = H = 1.0
                                page0 = None
                            idx_map = []  # (start_raw, end_raw, rect)
                            if page0 is not None:
                                for token in getattr(page0, 'tokens', []) or []:
                                    layout = getattr(token, 'layout', None)
                                    if not layout:
                                        continue
                                    ta = getattr(layout, 'text_anchor', None)
                                    segs = getattr(ta, 'text_segments', []) if ta else []
                                    if not segs:
                                        continue
                                    start_raw = int(getattr(segs[0], 'start_index', 0) or 0)
                                    end_raw = int(getattr(segs[0], 'end_index', 0) or 0)
                                    bp = getattr(layout, 'bounding_poly', None)
                                    rect = (0.0, 0.0, 0.0, 0.0)
                                    if bp is not None:
                                        nvs = getattr(bp, 'normalized_vertices', None)
                                        if nvs:
                                            xs = [v.x for v in nvs]
                                            ys = [v.y for v in nvs]
                                            x0, x1 = min(xs), max(xs)
                                            y0, y1 = min(ys), max(ys)
                                            rect = (max(0.0, x0), max(0.0, y0), max(0.0, (x1 - x0)), max(0.0, (y1 - y0)))
                                        else:
                                            vs = getattr(bp, 'vertices', None) or []
                                            if vs:
                                                xs = [v.x for v in vs]
                                                ys = [v.y for v in vs]
                                                x0, x1 = min(xs), max(xs)
                                                y0, y1 = min(ys), max(ys)
                                                rect = (max(0.0, x0 / W), max(0.0, y0 / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                                    idx_map.append((start_raw, end_raw, rect))
                            agg_norm, norm2raw = _normalize_with_map(agg_raw)
                            _OCR_CACHE[cache_key] = (agg_norm, norm2raw, idx_map, W, H)
                            used_docai = True
                    except Exception:
                        used_docai = False
                if not used_docai:
                    # Fallback to Cloud Vision
                    img = _vision.Image(content=img_bytes)
                    features = [_vision.Feature(type_=_vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
                    resp = await client.batch_annotate_images(requests=[_vision.AnnotateImageRequest(image=img, features=features)])
                    annotation = resp.responses[0]
                    fta = annotation.full_text_annotation
                    if fta and getattr(fta, 'pages', None):
                        page = fta.pages[0]
                        W = float(page.width or 1)
                        H = float(page.height or 1)
                        tokens = []
                        for block in page.blocks:
                            for para in block.paragraphs:
                                for word in para.words:
                                    t = "".join([s.text for s in word.symbols])
                                    poly = word.bounding_box
                                    xs = [v.x for v in poly.vertices]
                                    ys = [v.y for v in poly.vertices]
                                    x0, x1 = min(xs), max(xs)
                                    y0, y1 = min(ys), max(ys)
                                    rect = (max(0.0, x0 / W), max(0.0, (y0) / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                                    tokens.append((t, rect))
                        agg = []
                        raw_idx_map = []  # positions in raw aggregated string
                        pos0 = 0
                        for t, rect in tokens:
                            if not t:
                                continue
                            if agg:
                                agg.append(' ')
                                pos0 += 1
                            agg.append(t)
                            s0 = pos0
                            pos0 += len(t)
                            raw_idx_map.append((s0, pos0, rect))
                        agg_raw = ''.join(agg)
                        agg_norm, norm2raw = _normalize_with_map(agg_raw)
                        _OCR_CACHE[cache_key] = (agg_norm, norm2raw, raw_idx_map, W, H)
                cached = _OCR_CACHE.get(cache_key)
                if cached:
                    agg_norm, norm2raw, idx_map, W, H = cached
                    # Prefer the normalized phrase that matched best
                    mpos = -1
                    mend = -1
                    if best_phrase_norm:
                        mpos = agg_norm.find(best_phrase_norm)
                        if mpos >= 0:
                            mend = mpos + len(best_phrase_norm)
                    if mpos < 0 and q_norm:
                        mpos = agg_norm.find(q_norm)
                        if mpos >= 0:
                            mend = mpos + len(q_norm)
                    if mpos < 0 and q_tokens:
                        # Try best-scored window against OCR
                        found2 = _best_scored_window(q_tokens, q_salient, agg_norm)
                        if found2:
                            mpos, mend, _, _ = found2
                    if mpos >= 0:
                        # map normalized positions to raw aggregated positions
                        s_raw = norm2raw[mpos] if mpos < len(norm2raw) else 0
                        e_raw = norm2raw[mend-1] + 1 if mend-1 < len(norm2raw) else s_raw
                        # Compute a single union bounding box over all tokens in range
                        x_min = y_min = 1.0
                        x_max = y_max = 0.0
                        found_any = False
                        for s0, e0, rect in idx_map:
                            if e0 <= s_raw:
                                continue
                            if s0 >= e_raw:
                                break
                            x, y, w, h = rect
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x + w)
                            y_max = max(y_max, y + h)
                            found_any = True
                        if found_any:
                            # Optional small padding
                            pad = 0.005
                            x_min = max(0.0, x_min - pad)
                            y_min = max(0.0, y_min - pad)
                            x_max = min(1.0, x_max + pad)
                            y_max = min(1.0, y_max + pad)
                            box = schemas.AnchorBox(x=x_min, y=y_min, w=max(0.0, x_max - x_min), h=max(0.0, y_max - y_min))
                            match.boxes = [box]
                            match.strategy = (match.strategy or "") + "+ocr"
        except Exception:
            pass

    return schemas.LocateResponse(matches=[match])


async def _prewarm_scanned_pages_ocr(analysis_id: int, page_images: list[str], limit: int = 3) -> None:
    """Precompute OCR token caches for the first few scanned pages to reduce first-click latency.
    Best-effort and silent on failure.
    """
    try:
        from google.cloud import vision as _vision
        client = _vision.ImageAnnotatorAsyncClient()
    except Exception:
        client = None
    # Basic loop; stop if cache already populated
    tasks = []
    max_i = min(limit, len(page_images))
    for pidx in range(max_i):
        if (int(analysis_id), pidx) in _OCR_CACHE:
            continue
        data_uri = page_images[pidx]
        img_bytes: bytes | None = None
        if data_uri.startswith('data:image'):
            try:
                b64 = data_uri.split(',', 1)[1]
                img_bytes = base64.b64decode(b64)
            except Exception:
                img_bytes = None
        elif data_uri.startswith('http://') or data_uri.startswith('https://'):
            try:
                r = requests.get(data_uri, timeout=5)
                r.raise_for_status()
                img_bytes = r.content
            except Exception:
                img_bytes = None
        if not img_bytes:
            continue
        # Try Document AI first
        try:
            processor_id = os.environ.get("DOCAI_PROCESSOR_ID")
            location = os.environ.get("DOCAI_LOCATION", "us")
            project_id = os.environ.get("DOCAI_PROJECT_ID")
            if not project_id:
                try:
                    creds, default_project = google.auth.default()
                    if default_project:
                        project_id = default_project
                except Exception:
                    project_id = None
            if documentai is not None and processor_id and project_id:
                da_client_sync = documentai.DocumentProcessorServiceClient()
                name = da_client_sync.processor_path(project_id, location, processor_id)
                raw_document = documentai.RawDocument(content=img_bytes, mime_type="image/png")
                req = documentai.ProcessRequest(name=name, raw_document=raw_document)
                resp = da_client_sync.process_document(request=req)
                doc = getattr(resp, 'document', None)
                if doc and getattr(doc, 'text', None) is not None:
                    agg_raw = doc.text or ''
                    try:
                        page0 = doc.pages[0]
                        dim = getattr(page0, 'dimension', None)
                        W = float(getattr(dim, 'width', 1.0) or 1.0)
                        H = float(getattr(dim, 'height', 1.0) or 1.0)
                    except Exception:
                        W = H = 1.0
                        page0 = None
                    idx_map = []
                    if page0 is not None:
                        for token in getattr(page0, 'tokens', []) or []:
                            layout = getattr(token, 'layout', None)
                            if not layout:
                                continue
                            ta = getattr(layout, 'text_anchor', None)
                            segs = getattr(ta, 'text_segments', []) if ta else []
                            if not segs:
                                continue
                            start_raw = int(getattr(segs[0], 'start_index', 0) or 0)
                            end_raw = int(getattr(segs[0], 'end_index', 0) or 0)
                            bp = getattr(layout, 'bounding_poly', None)
                            rect = (0.0, 0.0, 0.0, 0.0)
                            if bp is not None:
                                nvs = getattr(bp, 'normalized_vertices', None)
                                if nvs:
                                    xs = [v.x for v in nvs]
                                    ys = [v.y for v in nvs]
                                    x0, x1 = min(xs), max(xs)
                                    y0, y1 = min(ys), max(ys)
                                    rect = (max(0.0, x0), max(0.0, y0), max(0.0, (x1 - x0)), max(0.0, (y1 - y0)))
                                else:
                                    vs = getattr(bp, 'vertices', None) or []
                                    if vs:
                                        xs = [v.x for v in vs]
                                        ys = [v.y for v in vs]
                                        x0, x1 = min(xs), max(xs)
                                        y0, y1 = min(ys), max(ys)
                                        rect = (max(0.0, x0 / W), max(0.0, y0 / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                            idx_map.append((start_raw, end_raw, rect))
                    agg_norm, norm2raw = _normalize_with_map(agg_raw)
                    _OCR_CACHE[(int(analysis_id), pidx)] = (agg_norm, norm2raw, idx_map, W, H)
                    continue
        except Exception:
            pass
        # Vision fallback
        try:
            if client is None:
                continue
            img = _vision.Image(content=img_bytes)
            features = [_vision.Feature(type_=_vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
            resp = await client.batch_annotate_images(requests=[_vision.AnnotateImageRequest(image=img, features=features)])
            annotation = resp.responses[0]
            fta = annotation.full_text_annotation
            if not fta or not getattr(fta, 'pages', None):
                continue
            page = fta.pages[0]
            W = float(page.width or 1)
            H = float(page.height or 1)
            tokens = []
            for block in page.blocks:
                for para in block.paragraphs:
                    for word in para.words:
                        t = "".join([s.text for s in word.symbols])
                        poly = word.bounding_box
                        xs = [v.x for v in poly.vertices]
                        ys = [v.y for v in poly.vertices]
                        x0, x1 = min(xs), max(xs)
                        y0, y1 = min(ys), max(ys)
                        rect = (max(0.0, x0 / W), max(0.0, (y0) / H), max(0.0, (x1 - x0) / W), max(0.0, (y1 - y0) / H))
                        tokens.append((t, rect))
            agg = []
            raw_idx_map = []
            pos0 = 0
            for t, rect in tokens:
                if not t:
                    continue
                if agg:
                    agg.append(' ')
                    pos0 += 1
                agg.append(t)
                s0 = pos0
                pos0 += len(t)
                raw_idx_map.append((s0, pos0, rect))
            agg_raw = ''.join(agg)
            agg_norm, norm2raw = _normalize_with_map(agg_raw)
            _OCR_CACHE[(int(analysis_id), pidx)] = (agg_norm, norm2raw, raw_idx_map, W, H)
        except Exception:
            continue
