# In scripts/setup_benchmark_db.py
import sqlite3
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

print("Setting up the benchmark database...")

# --- Configuration ---
load_dotenv()
DB_FILE = "benchmark.db"
TABLE_NAME = "clauses"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# --- Mock Data ---
mock_clauses = [
    {"clause_type": "Security Deposit", "text": "Tenant shall pay a security deposit equivalent to one (1) month's rent.", "category": "Standard"},
    {"clause_type": "Security Deposit", "text": "Tenant shall pay a security deposit equivalent to three (3) months' rent.", "category": "Strict (Landlord Favorable)"},
    {"clause_type": "Security Deposit", "text": "The security deposit shall be returned within 15 days of lease termination.", "category": "Lenient (Tenant Favorable)"},
    {"clause_type": "Termination", "text": "Either party may terminate this agreement with 30 days written notice.", "category": "Standard"},
    {"clause_type": "Termination", "text": "Landlord may terminate this agreement with 7 days notice. Tenant may terminate with 60 days notice.", "category": "Strict (Landlord Favorable)"},
    {"clause_type": "Termination", "text": "Tenant may terminate this agreement at any time with 30 days written notice.", "category": "Lenient (Tenant Favorable)"},
]

# --- Database Operations ---
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"Removed existing database file: {DB_FILE}")

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Create table with a column for the vector embedding
cursor.execute(f'''
CREATE TABLE {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clause_type TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    embedding TEXT NOT NULL
)
''')
print(f"Table '{TABLE_NAME}' created successfully.")

# --- Generate Embeddings and Insert Data ---
print(f"Generating embeddings for {len(mock_clauses)} mock clauses...")
texts_to_embed = [item['text'] for item in mock_clauses]
result = genai.embed_content(model='models/text-embedding-004',
                             content=texts_to_embed,
                             task_type="RETRIEVAL_DOCUMENT")

for i, item in enumerate(mock_clauses):
    embedding_json = json.dumps(result['embedding'][i])
    cursor.execute(f'''
    INSERT INTO {TABLE_NAME} (clause_type, text, category, embedding)
    VALUES (?, ?, ?, ?)
    ''', (item['clause_type'], item['text'], item['category'], embedding_json))

conn.commit()
conn.close()

print(f"Successfully inserted {len(mock_clauses)} records into the database.")
print("Database setup complete.")