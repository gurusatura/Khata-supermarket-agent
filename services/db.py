import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Returns a new psycopg connection. Caller is responsible for closing it."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in .env")
    return psycopg.connect(db_url)
