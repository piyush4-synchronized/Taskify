"""
db.py — Database connection helper for Taskify.
Uses PostgreSQL if DATABASE_URL is set (Production)
Otherwise, falls back to SQLite for zero-setup local development.
"""

import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taskify.db")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- PostgreSQL Wrapper ---
# These wrapper classes allow us to use psycopg2 with the exact same API
# as sqlite3, including `?` parameter substitution and `lastrowid`

class PostgresWrapperCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None
        
    def execute(self, query, params=()):
        # Convert SQLite `?` placeholders to Postgres `%s`
        pg_query = query.replace("?", "%s")
        is_insert = pg_query.strip().upper().startswith("INSERT")
        
        # To simulate SQLite's lastrowid, we append 'RETURNING id' if it's an insert
        if is_insert and "RETURNING id" not in pg_query.upper() and "RETURNING" not in pg_query.upper():
            pg_query += " RETURNING id"
            
        self._cursor.execute(pg_query, params)
        
        if is_insert:
            row = self._cursor.fetchone()
            if row:
                self.lastrowid = row['id']
                
    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

class PostgresWrapperConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresWrapperCursor(self._conn.cursor())

    def execute(self, query, params=()):
        cursor = self.cursor()
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db():
    """Return a new database connection (PostgreSQL or SQLite)."""
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return PostgresWrapperConnection(conn)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row        # enables dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # enforce foreign keys
        return conn


def init_db():
    """
    Initialize the database tables if they don't exist.
    Called once on application startup.
    """
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                priority VARCHAR(50) DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
                category VARCHAR(50) DEFAULT 'Personal',
                due_date TIMESTAMP,
                status INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✓ PostgreSQL Database initialized successfully.")
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
                category TEXT DEFAULT 'Personal',
                due_date TEXT,
                status INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✓ SQLite Database initialized successfully.")
