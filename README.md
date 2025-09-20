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
