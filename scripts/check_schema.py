import os, psycopg
from dotenv import load_dotenv

load_dotenv()
with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'khata_txns_txn_type_check';")
        res = cur.fetchone()
        if res: print("khata_txns_txn_type_check:", res[0])
