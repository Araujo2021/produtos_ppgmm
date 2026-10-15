import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).with_name("produtos.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    doi TEXT,
    journal TEXT,
    work_type TEXT,
    cited_by INTEGER DEFAULT 0,
    openalex_id TEXT,
    url TEXT,
    authors_json TEXT NOT NULL,
    docentes_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_works_year ON works(year);
CREATE INDEX IF NOT EXISTS idx_works_doi ON works(doi);

CREATE TABLE IF NOT EXISTS author_mapping (
    nome TEXT PRIMARY KEY,
    openalex_id TEXT,
    display_name TEXT,
    institution TEXT
);
"""

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.executescript(SCHEMA)

def get_mappings():
    with conn() as c:
        rows = c.execute("SELECT * FROM author_mapping").fetchall()
    return {r["nome"]: dict(r) for r in rows}

def save_mapping(nome, openalex_id, display_name, institution):
    with conn() as c:
        c.execute("""
        INSERT INTO author_mapping(nome, openalex_id, display_name, institution)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(nome) DO UPDATE SET
            openalex_id=excluded.openalex_id,
            display_name=excluded.display_name,
            institution=excluded.institution
        """, (nome, openalex_id, display_name, institution))

def clear_db():
    with conn() as c:
        c.execute("DELETE FROM works")

def upsert_work(w):
    with conn() as c:
        c.execute("""
        INSERT INTO works(
            canonical_key,title,year,doi,journal,work_type,cited_by,
            openalex_id,url,authors_json,docentes_json,sources_json,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(canonical_key) DO UPDATE SET
            title=excluded.title,
            year=excluded.year,
            doi=COALESCE(excluded.doi, works.doi),
            journal=COALESCE(excluded.journal, works.journal),
            work_type=COALESCE(excluded.work_type, works.work_type),
            cited_by=MAX(excluded.cited_by, works.cited_by),
            openalex_id=COALESCE(excluded.openalex_id, works.openalex_id),
            url=COALESCE(excluded.url, works.url),
            authors_json=excluded.authors_json,
            docentes_json=excluded.docentes_json,
            sources_json=excluded.sources_json,
            updated_at=CURRENT_TIMESTAMP
        """, (
            w["canonical_key"], w["title"], w["year"], w.get("doi"),
            w.get("journal"), w.get("work_type"), w.get("cited_by",0),
            w.get("openalex_id"), w.get("url"),
            json.dumps(w.get("authors",[]), ensure_ascii=False),
            json.dumps(w.get("docentes",[]), ensure_ascii=False),
            json.dumps(w.get("sources",[]), ensure_ascii=False),
        ))

def get_work_by_key(key):
    with conn() as c:
        row = c.execute("SELECT * FROM works WHERE canonical_key=?", (key,)).fetchone()
    if row:
        d = dict(row)
        d["authors"] = json.loads(d.pop("authors_json"))
        d["docentes"] = json.loads(d.pop("docentes_json"))
        d["sources"] = json.loads(d.pop("sources_json"))
        return d
    return None

def load_works(min_year=2025):
    with conn() as c:
        rows = c.execute("SELECT * FROM works WHERE year>=? ORDER BY year DESC, title", (min_year,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["authors"] = json.loads(d.pop("authors_json"))
        d["docentes"] = json.loads(d.pop("docentes_json"))
        d["sources"] = json.loads(d.pop("sources_json"))
        out.append(d)
    return out

def stats():
    with conn() as c:
        n = c.execute("SELECT COUNT(*) n FROM works").fetchone()["n"]
        y = c.execute("SELECT MAX(updated_at) x FROM works").fetchone()["x"]
    return n, y
