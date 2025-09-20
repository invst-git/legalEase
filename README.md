# legalEase - AI-Powered Legal Document Analysis Platform

A comprehensive AI-powered platform for analyzing legal documents, identifying risks, and providing intelligent insights to help users understand complex legal agreements.

## Overview

legalEase (internally known as Project Chimera) is a legal document analysis platform that leverages cutting-edge AI technology to help users understand, analyze, and negotiate legal documents with confidence. The platform combines document processing, risk assessment, and intelligent Q&A capabilities to democratize legal document comprehension.

## Key Features

### Document Analysis & Processing
- **Multi-format Support**: PDF, DOCX, TXT files [1](#0-0) 
- **Advanced OCR**: Document AI and Vision API integration for scanned documents [2](#0-1) 
- **Intelligent Text Extraction**: Handles both digital and scanned documents seamlessly

### AI-Powered Analysis
- **Risk Assessment**: Automated risk level classification (High/Medium/Low) with detailed justifications
- **Key Information Extraction**: Identifies and structures important clauses and terms
- **Action Items**: Automatically detects obligations and required actions
- **Clause Oracle**: Interactive Q&A system powered by Vertex AI [3](#0-2) 

### Advanced Features
- **Risk Simulation**: Scenario-based analysis of potential consequences
- **Clause Rewriting**: AI-generated alternative phrasings for negotiation
- **Timeline Generation**: Automatic extraction of key dates and deadlines
- **PDF Export**: Comprehensive analysis reports with original document attachment
- **Real-time Chat**: Vertex AI-powered conversational interface for document queries

##  Architecture

### Backend Stack
- **Framework**: FastAPI with Python [4](#0-3) 
- **AI Services**: 
  - Google Gemini 1.5 Flash for document analysis [5](#0-4) 
  - Vertex AI for chat functionality [6](#0-5) 
- **Database**: Dual backend architecture
  - SQLite for local development [7](#0-6) 
  - Firestore for cloud deployment [8](#0-7) 
- **Storage**: Google Cloud Storage for file management [9](#0-8) 

### Frontend Stack
- **UI Framework**: Vanilla JavaScript with Tailwind CSS [10](#0-9) 
- **Architecture**: Single-page application with responsive design
- **Real-time Updates**: WebSocket-like interactions for analysis progress

### Database Configuration

The platform supports dual database backends:

**Firestore Configuration (Production)**:
```bash
DB_BACKEND=firestore
GCP_PROJECT=your-project-id
FIRESTORE_DATABASE=your-database-id  # optional
GCS_BUCKET=your-storage-bucket
```

**SQLite Configuration (Development)**:
```bash
# No configuration needed - uses local SQLite file
``` [11](#0-10) 

## Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud Project with enabled APIs:
  - Firestore API
  - Cloud Storage API
  - Document AI API
  - Vision API
  - Vertex AI API

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/legalEase.git
   cd legalEase
   ```

2. **Set up Python environment** [12](#0-11) 
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # Unix/macOS
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file with the following:
   ```env
   # AI Configuration
   GOOGLE_API_KEY=your-gemini-api-key
   VERTEX_PROJECT=your-gcp-project-id
   VERTEX_LOCATION=us-central1
   VERTEX_MODEL=gemini-1.5-pro
   
   # Database Configuration (Firestore)
   DB_BACKEND=firestore
   GCP_PROJECT=your-project-id
   FIRESTORE_DATABASE=your-database-id
   GCS_BUCKET=your-storage-bucket
   
   # OCR Configuration
   DOCAI_PROCESSOR_ID=your-processor-id
   DOCAI_LOCATION=us
   DOCAI_PROJECT_ID=your-project-id
   
   # Optional
   COMPANY_NAME="Your Company"
   EXPORT_PDF_ENABLED=true
   ```

5. **Run the application** [13](#0-12) 
   ```bash
   # Start the API server
   uvicorn app.main:app --reload --port 8000
   
   # In a separate terminal, serve the frontend
   python -m http.server 8080
   ```

6. **Access the application**
   Open http://localhost:8080 in your browser

### Development Setup

For local development with SQLite:
```bash
# Remove or comment out Firestore environment variables
# DB_BACKEND=sqlite  # or leave empty
```

##  Configuration

### AI Provider Configuration

**Vertex AI Setup** (for Clause Oracle): [14](#0-13) 
- Requires `VERTEX_PROJECT`, `VERTEX_LOCATION`, and `VERTEX_MODEL` environment variables
- Uses JSON response format for structured AI responses
- Supports multiple Gemini model variants

**Gemini API Setup** (for document analysis): [5](#0-4) 
- Requires `GOOGLE_API_KEY` environment variable
- Uses Gemini 1.5 Flash model for fast document processing

### Database Backend Selection

The application automatically selects the database backend based on the `DB_BACKEND` environment variable: [15](#0-14) 

- **Firestore**: Set `DB_BACKEND=firestore` for production deployment
- **SQLite**: Leave empty or set to any other value for local development

### Security Configuration

The application includes comprehensive security settings for AI model safety: [16](#0-15) 

##  Project Structure

```
legalEase/
├── app/                    # FastAPI backend
│   ├── main.py            # API routes and application setup
│   ├── models.py          # SQLAlchemy database models
│   ├── schemas.py         # Pydantic request/response models
│   ├── services.py        # Business logic and AI integration
│   ├── database.py        # SQLite database configuration
│   ├── repository.py      # Firestore operations
│   ├── ai_provider.py     # Vertex AI integration
│   ├── auth.py            # Authentication utilities
│   └── utils.py           # Helper functions and PDF processing
├── scripts/               # Utility scripts
├── data/                  # Sample files and local storage
├── index.html            # Frontend application
├── main.js               # Frontend JavaScript
├── requirements.txt      # Python dependencies
``` [17](#0-16) 

## 🔧 API Endpoints

### Document Analysis
- `POST /analyze` - Upload and analyze legal documents
- `GET /analyses/{id}` - Retrieve full analysis results
- `GET /analyses/dashboard` - List user's saved analyses
- `DELETE /analyses/{id}` - Delete an analysis

### AI Services
- `POST /query` - Clause Oracle Q&A endpoint
- `POST /simulate` - Risk simulation for specific clauses
- `POST /rewrite` - Generate alternative clause phrasings
- `POST /benchmark` - Compare clauses against standards

### File Management
- `GET /analyses/{id}/file` - Access original document
- `GET /analyses/{id}/export` - Export analysis as PDF

### Timeline & Reminders
- `GET /timeline/{id}` - Retrieve document timeline
- `POST /reminders` - Set up deadline reminders

## Testing

Run the test suite: [18](#0-17) 
```bash
pip install pytest httpx
pytest -q
```

## Deployment

### Google Cloud Platform
1. Set up Firestore database
2. Configure Cloud Storage bucket
3. Enable required APIs (Document AI, Vision, Vertex AI)
4. Deploy using Cloud Run or Compute Engine
5. Set environment variables for production

### Local Development
The application supports local development with SQLite and minimal configuration requirements.

## Security

- **Authentication**: JWT-based user authentication [19](#0-18) 
- **Data Privacy**: Configurable data retention and deletion
- **AI Safety**: Comprehensive safety filters for content analysis
- **File Security**: Secure file upload and storage with type validation

## Contributing

Please refer to the development guidelines in `AGENTS.md` for:
- Code style conventions [20](#0-19) 
- Testing requirements [21](#0-20) 
- Commit message standards [22](#0-21) 

##  License

This project is proprietary software. All rights reserved.

##  Support

For technical support and documentation, please refer to the internal wiki or contact the development team.

---

**Note**: This application requires active Google Cloud services and API keys for full functionality. Ensure proper configuration of all services before deployment.

### Citations

**File:** app/main.py (L17-21)
```python
app = FastAPI(
    title="Project Chimera",
    description="An AI-powered legal document analysis and co-pilot.",
    version="0.1.0",
)
```

**File:** app/main.py (L41-59)
```python
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
```

**File:** app/main.py (L92-104)
```python
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
```

**File:** app/services.py (L28-29)
```python
DB_BACKEND = os.getenv("DB_BACKEND", "").lower()
AI_PROVIDER = os.getenv("AI_PROVIDER", "").lower()
```

**File:** app/services.py (L32-37)
```python
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception:
    print("Error: GOOGLE_API_KEY not found or invalid.")
    model = None
```

**File:** app/services.py (L39-46)
```python
# Define safety settings appropriate for analyzing professional/legal documents
# This reduces the chance of false positives on dense legal text.
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}
```

**File:** app/services.py (L65-100)
```python
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
```

**File:** app/ai_provider.py (L8-64)
```python
def generate_oracle_json(prompt: str) -> dict:
    """Generate a JSON response for Clause Oracle via Vertex AI.

    Expects env vars:
      - VERTEX_PROJECT
      - VERTEX_LOCATION
      - VERTEX_MODEL (default: gemini-1.5-pro)

    Returns a dict with keys: "answer", "citation".
    Raises on initialization errors; caller should handle fallbacks.
    """
    # Lazy imports to avoid hard dependency when not enabled
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig

    project = os.getenv("VERTEX_PROJECT")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    model_name = os.getenv("VERTEX_MODEL", "gemini-1.5-pro")

    if not project:
        raise RuntimeError("VERTEX_PROJECT env var is required for Vertex AI provider")

    vertexai.init(project=project, location=location)
    model = GenerativeModel(model_name)

    gen_cfg = GenerationConfig(response_mime_type="application/json")
    response = model.generate_content(prompt, generation_config=gen_cfg)

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        # Fallback: try candidates -> content -> parts
        try:
            candidates = getattr(response, "candidates", []) or []
            for c in candidates:
                parts = getattr(getattr(c, "content", None), "parts", []) or []
                for p in parts:
                    t = getattr(p, "text", "")
                    if t:
                        text = t.strip()
                        break
                if text:
                    break
        except Exception:
            pass

    # Ensure JSON object contract
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Non-object JSON")
    except Exception:
        data = {"answer": text or "", "citation": ""}

    # Guarantee keys
    data.setdefault("answer", "")
    data.setdefault("citation", "")
    return data
```

**File:** app/database.py (L6-9)
```python
DATABASE_URL = "sqlite:///./chimera_app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**File:** app/repository.py (L14-16)
```python
def is_firestore_enabled() -> bool:
    return (os.getenv("DB_BACKEND", "").lower() == "firestore") and firestore is not None

```

**File:** app/repository.py (L18-31)
```python
def _fs_client():
    if firestore is None:
        raise RuntimeError("google-cloud-firestore not installed/configured")
    project = os.getenv("GCP_PROJECT")
    db_id = os.getenv("FIRESTORE_DATABASE")
    # Let client pick up GOOGLE_APPLICATION_CREDENTIALS automatically
    if db_id:
        try:
            return firestore.Client(project=project, database=db_id) if project else firestore.Client(database=db_id)
        except TypeError:
            # Older library versions may not support the database kwarg; fallback to default database
            return firestore.Client(project=project) if project else firestore.Client()
    return firestore.Client(project=project) if project else firestore.Client()

```

**File:** app/repository.py (L33-41)
```python
def _st_client_bucket():
    if storage is None:
        raise RuntimeError("google-cloud-storage not installed/configured")
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET env var is required when using Firestore backend")
    st = storage.Client()
    bucket = st.bucket(bucket_name)
    return st, bucket
```

**File:** index.html (L19-44)
```html
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: { sans: ["Open Sans", "ui-sans-serif", "system-ui"], title: ["Lato", "ui-sans-serif"] },
          colors: {
            primary: {
              "50": "#f3f1ff",
              "100": "#e9e5ff",
              "200": "#d5cfff",
              "300": "#b7a9ff",
              "400": "#9478ff",
              "500": "#7341ff",
              "600": "#631bff",
              "700": "#611bf8",
              "800": "#4607d0",
              "900": "#3c08aa",
              "950": "#220174",
              DEFAULT: "#611bf8",
            },
          },
        },
      },
    };
  </script>
```



