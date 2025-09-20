# In app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

DATABASE_URL = "sqlite:///./chimera_app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
    # Lightweight SQLite migration for new columns
    try:
        with engine.begin() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info('analysis_meta')").fetchall()]
            if 'risk_reason' not in cols:
                conn.exec_driver_sql("ALTER TABLE analysis_meta ADD COLUMN risk_reason TEXT")
            if 'page_images_json' not in cols:
                conn.exec_driver_sql("ALTER TABLE analysis_meta ADD COLUMN page_images_json TEXT")
            # Ensure timeline_events table exists
            conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS timeline_events (id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL, date TEXT NOT NULL, label TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL)")
    except Exception:
        # Best-effort migration; avoid crashing app startup
        pass