import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import sys

def init_db():
    urls_to_try = [
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://postgres:1234@localhost:5432/postgres",
        "postgresql://postgres:root@localhost:5432/postgres",
        "postgresql://postgres:admin@localhost:5432/postgres",
        "postgresql://postgres:@localhost:5432/postgres",
    ]
    
    connected_url = None
    conn = None
    for url in urls_to_try:
        try:
            conn = psycopg2.connect(url)
            connected_url = url
            print(f"Successfully connected with: {url}")
            break
        except Exception as e:
            # print(f"Failed {url}: {e}")
            pass
            
    if not conn:
        print("Could not connect to PostgreSQL with default passwords. Please check postgres password.")
        sys.exit(1)
        
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'moneymove'")
    exists = cur.fetchone()
    if not exists:
        cur.execute("CREATE DATABASE moneymove")
        print("Database 'moneymove' created successfully.")
    else:
        print("Database 'moneymove' already exists.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    init_db()
