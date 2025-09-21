# legalEase - AI-Powered Legal Document Analysis Platform

## Overview

legalEase is a sophisticated AI-powered legal document analysis platform that provides comprehensive document processing, analysis, and interactive features for legal professionals. The system combines advanced AI capabilities with a modern web interface to deliver intelligent document insights, risk assessment, and interactive legal tools.

## Architecture

### Backend (FastAPI)
The backend is built using FastAPI and follows a modular architecture:

- **`app/main.py`**: Main FastAPI application with comprehensive API endpoints
- **`app/models.py`**: SQLAlchemy database models for data persistence
- **`app/schemas.py`**: Pydantic schemas for request/response validation
- **`app/services.py`**: Core business logic and AI service integrations
- **`app/database.py`**: Database connection and session management
- **`app/utils.py`**: Utility functions for document processing and text manipulation
- **`app/ai_provider.py`**: AI service provider abstraction layer
- **`app/auth.py`**: Authentication and authorization services
- **`app/repository.py`**: Data access layer and repository pattern implementation

### Frontend
- **`index.html`**: Modern web interface with responsive design
- **`main.js`**: JavaScript client-side logic for API communication

### Database Architecture
- **Primary Storage**: Firestore for production data persistence
- **Fallback Storage**: SQLite for local development and backup scenarios
- **Data Models**: Comprehensive document, user, and analysis data structures

## Core Features

### Document Processing
- **Multi-format Support**: PDF, DOCX, TXT document processing
- **OCR Capabilities**: Text extraction from scanned documents
- **Content Analysis**: Intelligent document structure recognition
- **Metadata Extraction**: Automatic document information parsing

### AI-Powered Analysis
- **Risk Assessment**: Automated legal risk identification and scoring
- **Clause Analysis**: Intelligent contract clause detection and analysis
- **Timeline Generation**: Automatic legal timeline creation
- **Q&A System**: Interactive document question answering
- **Clause Rewriting**: AI-powered contract clause improvement suggestions

### Interactive Features
- **Risk Simulation**: Interactive risk scenario modeling
- **Document Comparison**: Side-by-side document analysis
- **Collaborative Analysis**: Multi-user document review capabilities
- **Export Options**: Multiple format export capabilities

## Technical Implementation

### AI Integration
The platform integrates multiple AI services:

- **Google Gemini**: Advanced language model for document analysis
- **Vertex AI**: Google Cloud AI services for specialized tasks
- **Document AI**: Google Cloud Document AI for OCR and document processing
- **Custom AI Providers**: Extensible AI service architecture

### Database Management
- **Firestore Integration**: Primary cloud database for production
- **SQLite Fallback**: Local database for development and backup
- **Data Synchronization**: Automatic data sync between storage systems
- **Migration Support**: Database schema migration capabilities

### Security Features
- **Authentication**: Secure user authentication system
- **Authorization**: Role-based access control
- **Data Encryption**: Secure data storage and transmission
- **API Security**: Comprehensive API endpoint protection

## Development Setup

### Prerequisites
- Python 3.10+
- Node.js (for frontend development)
- Google Cloud credentials (for AI services)
- SQLite (for local development)

### Installation
1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate virtual environment: `source venv/bin/activate` (Unix) or `.\venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Configure environment variables (see `env.example`)
6. Initialize database: `python scripts/setup_benchmark_db.py`

### Running the Application
- **Backend**: `uvicorn app.main:app --reload --port 8000`
- **Frontend**: `python -m http.server 8080`
- **Access**: Open `http://localhost:8080` in your browser

## API Endpoints

### Document Management
- `POST /api/documents/upload`: Upload and process documents
- `GET /api/documents/{id}`: Retrieve document details
- `GET /api/documents`: List all documents
- `DELETE /api/documents/{id}`: Delete document

### Analysis Services
- `POST /api/analyze/risk`: Perform risk analysis
- `POST /api/analyze/clauses`: Analyze document clauses
- `POST /api/analyze/timeline`: Generate legal timeline
- `POST /api/analyze/qa`: Document Q&A system

### Interactive Features
- `POST /api/simulate/risk`: Risk simulation
- `POST /api/rewrite/clause`: Clause rewriting
- `POST /api/compare/documents`: Document comparison

## Configuration

### Environment Variables
- `GOOGLE_API_KEY`: Google Cloud API key
- `GOOGLE_PROJECT_ID`: Google Cloud project ID
- `FIRESTORE_CREDENTIALS`: Firestore service account credentials
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Application secret key

### Database Configuration
- **Production**: Firestore cloud database
- **Development**: SQLite local database
- **Migration**: Automatic schema updates

## Testing

### Test Structure
- **API Tests**: FastAPI endpoint testing
- **Service Tests**: Business logic testing
- **Integration Tests**: End-to-end functionality testing
- **Performance Tests**: Load and stress testing

### Running Tests
```bash
pip install pytest httpx
pytest -q
```

## Deployment

### Docker Support
- **Dockerfile**: Containerized application deployment
- **docker-compose.yml**: Multi-service orchestration
- **nginx.conf**: Reverse proxy configuration

### Production Considerations
- **Environment Variables**: Secure configuration management
- **Database Migration**: Schema update procedures
- **Monitoring**: Application performance monitoring
- **Scaling**: Horizontal scaling capabilities


### Access Link
- **Deployed Link**: https://chimera-app-521628015031.asia-south1.run.app/

