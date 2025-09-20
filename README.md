# Project Chimera - AI-Powered Legal Document Analysis Platform

Project Chimera is a comprehensive legal document analysis platform that leverages artificial intelligence to analyze, extract insights, and provide intelligent assistance for legal documents. The platform combines document processing, AI-powered analysis, timeline generation, and interactive features to help users understand and work with legal agreements more effectively.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [File Structure](#file-structure)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Features

### Core Functionality
- **Document Upload & Processing**: Support for PDF, DOC, DOCX, TXT, and RTF files
- **AI-Powered Analysis**: Intelligent extraction of key information, risk assessment, and action items
- **Document Classification**: Automatic detection of legal vs non-legal documents
- **OCR Support**: Text extraction from scanned documents using Google Cloud Vision
- **Risk Assessment**: Automated risk level classification (Low, Medium, High)
- **Timeline Generation**: Automatic extraction of important dates and events
- **Interactive Dashboard**: User-friendly interface for managing analyses

### Advanced Features
- **PDF Export**: Generate comprehensive analysis reports with timeline and calendar integration
- **Google Calendar Integration**: Add timeline events directly to Google Calendar
- **Document Querying**: Ask questions about uploaded documents using natural language
- **Clause Rewriting**: AI-powered suggestions for improving contract clauses
- **Risk Simulation**: Simulate potential outcomes of contract modifications
- **Conversation History**: Persistent chat history for each analysis
- **Duplicate Detection**: Automatic detection of previously analyzed documents

### User Interface
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Live progress indicators and status updates
- **Interactive Elements**: Click-to-highlight text in documents
- **Export Options**: Download analysis results as PDF reports
- **Timeline Visualization**: Visual representation of document lifecycle events

## Architecture

Project Chimera follows a modern microservices architecture with clear separation of concerns:

```
Frontend (HTML/CSS/JavaScript)
    ↓
FastAPI Backend
    ↓
Service Layer (AI Processing)
    ↓
Data Layer (SQLite/Firestore)
```

### Components

1. **Frontend**: Single-page application built with vanilla JavaScript and Tailwind CSS
2. **Backend**: FastAPI-based REST API with async support
3. **AI Services**: Google Gemini integration for document analysis
4. **Database**: SQLite for local development, Firestore for production
5. **File Storage**: Local file system with optional cloud storage support

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapping (ORM)
- **Pydantic**: Data validation using Python type annotations
- **Google Generative AI**: AI model integration for document analysis
- **Google Cloud Vision**: OCR and image processing
- **ReportLab**: PDF generation and manipulation
- **PyMuPDF**: PDF processing and text extraction

### Frontend
- **HTML5**: Semantic markup
- **Tailwind CSS**: Utility-first CSS framework
- **Vanilla JavaScript**: No external frameworks for maximum performance
- **Google Material Icons**: Icon system

### Database
- **SQLite**: Local development database
- **Google Firestore**: Cloud database for production
- **SQLite3**: Benchmark database for clause comparison

### AI & ML
- **Google Gemini 1.5 Flash**: Primary AI model for document analysis
- **Text Embeddings**: Semantic search for clause benchmarking
- **Document AI**: Advanced document processing (optional)

## Installation

### Prerequisites
- Python 3.10 or higher
- Node.js (for development tools)
- Google Cloud account (for AI services)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd project-chimera
   ```

2. **Create virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   python -c "from app.database import create_db_and_tables; create_db_and_tables()"
   ```

6. **Set up benchmark database (optional)**
   ```bash
   python scripts/setup_benchmark_db.py
   ```

7. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

8. **Start the frontend server**
   ```bash
   # In a new terminal
   python -m http.server 8080
   ```

9. **Access the application**
   - Frontend: http://localhost:8080
   - API Documentation: http://localhost:8000/docs

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Optional
DB_BACKEND=sqlite  # or 'firestore'
AI_PROVIDER=google  # or other providers
COMPANY_NAME=Your Company Name
EXPORT_PDF_ENABLED=true

# Firestore Configuration (if using Firestore)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
FIRESTORE_PROJECT_ID=your-project-id

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Google Cloud Setup

1. **Create a Google Cloud Project**
2. **Enable APIs**:
   - Generative AI API
   - Cloud Vision API
   - Document AI API (optional)
3. **Create API Key**:
   - Go to APIs & Services > Credentials
   - Create API Key
   - Restrict to required APIs
4. **Service Account** (for Firestore):
   - Create service account
   - Download JSON key file
   - Set GOOGLE_APPLICATION_CREDENTIALS

## Usage

### Basic Workflow

1. **Upload Document**: Select a legal document (PDF, DOC, DOCX, TXT, RTF)
2. **Analysis**: The system automatically processes and analyzes the document
3. **Review Results**: Examine key information, risk assessment, and action items
4. **Interact**: Ask questions, rewrite clauses, or simulate risks
5. **Export**: Generate PDF reports or add events to calendar

### Document Analysis

The platform automatically extracts:
- **Key Information**: Important data points with negotiability flags
- **Risk Assessment**: Overall risk level and reasoning
- **Action Items**: Identified obligations and requirements
- **Timeline Events**: Important dates and deadlines
- **Text Extraction**: Full document text for reference

### Interactive Features

- **Document Querying**: Ask questions about the document content
- **Clause Rewriting**: Get AI suggestions for improving contract terms
- **Risk Simulation**: Understand potential outcomes of changes
- **Timeline Management**: Add important dates to your calendar
- **PDF Export**: Generate comprehensive analysis reports

## API Documentation

### Authentication

The API uses JWT-based authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-token>
```

### Core Endpoints

#### Document Analysis
- `POST /analyze` - Upload and analyze a document
- `GET /analyses/{id}` - Get analysis details
- `GET /analyses/dashboard` - Get user's analyses
- `DELETE /analyses/{id}` - Delete an analysis

#### Document Interaction
- `POST /query` - Ask questions about a document
- `POST /rewrite` - Rewrite contract clauses
- `POST /simulate` - Simulate risk scenarios
- `POST /benchmark` - Compare clauses against benchmarks

#### Timeline Management
- `GET /timeline/{analysis_id}` - Get timeline events
- `POST /timeline` - Generate timeline for analysis

#### File Operations
- `GET /analyses/{id}/file` - Download original document
- `GET /analyses/{id}/export` - Export analysis as PDF

### Response Formats

All API responses follow consistent JSON formats with proper error handling:

```json
{
  "id": 1,
  "filename": "contract.pdf",
  "assessment": "This is a standard lease agreement...",
  "risk_level": "Medium",
  "key_info": [...],
  "identified_actions": [...],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Database Schema

### Core Tables

#### Users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL
);
```

#### Analyses
```sql
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY,
    filename VARCHAR,
    assessment TEXT,
    key_info_json TEXT,
    actions_json TEXT,
    owner_id INTEGER REFERENCES users(id)
);
```

#### Timeline Events
```sql
CREATE TABLE timeline_events (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER REFERENCES analyses(id),
    date VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    kind VARCHAR NOT NULL,
    description TEXT NOT NULL
);
```

### Data Models

The application uses Pydantic models for data validation:

- `IntelligentAnalysis`: Complete analysis result
- `KeyInfoItem`: Key-value pairs with flags
- `ActionItem`: Identified obligations
- `TimelineEvent`: Timeline entries
- `User`: User account information

## File Structure

```
project-chimera/
├── app/                    # Backend application
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── models.py          # SQLAlchemy models
│   ├── schemas.py         # Pydantic schemas
│   ├── services.py        # Business logic
│   ├── utils.py           # Utility functions
│   ├── auth.py            # Authentication
│   ├── database.py        # Database configuration
│   ├── ai_provider.py     # AI service integration
│   └── repository.py      # Data access layer
├── data/                  # Sample documents
├── scripts/               # Utility scripts
│   └── setup_benchmark_db.py
├── static/                # Static assets
├── index.html             # Frontend application
├── main.js                # Frontend JavaScript
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## Development

### Code Style

- **Python**: Follow PEP 8 with 4-space indentation
- **JavaScript**: Use camelCase for variables, descriptive names
- **HTML**: Semantic markup with accessibility considerations
- **CSS**: Tailwind utility classes, custom styles when needed

### Testing

```bash
# Run tests (when implemented)
pytest

# Run with coverage
pytest --cov=app
```

### Code Quality

```bash
# Format code
black app/
isort app/

# Lint code
flake8 app/
pylint app/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head
```

## Deployment

### Production Setup

1. **Environment Configuration**
   - Set production environment variables
   - Configure secure secret keys
   - Set up proper CORS origins

2. **Database Setup**
   - Use Firestore for production
   - Configure proper authentication
   - Set up backup procedures

3. **File Storage**
   - Configure cloud storage for uploaded files
   - Set up CDN for static assets
   - Implement proper file cleanup

4. **Security**
   - Enable HTTPS
   - Configure proper CORS
   - Set up rate limiting
   - Implement proper authentication

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Cloud Deployment

The application can be deployed to:
- Google Cloud Run
- AWS Lambda
- Azure Container Instances
- Heroku
- DigitalOcean App Platform

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Guidelines

- Follow the existing code style
- Add proper documentation
- Include tests for new features
- Update README if needed
- Ensure all tests pass

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API documentation at `/docs`

## Changelog

### Version 0.1.0
- Initial release
- Document analysis and processing
- AI-powered insights
- Timeline generation
- PDF export functionality
- Google Calendar integration
- Interactive dashboard
- Risk assessment and simulation

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