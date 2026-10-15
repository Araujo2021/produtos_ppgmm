import sqlite3, json, re
from pathlib import Path
from rapidfuzz import fuzz

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

def _row_to_work(row):
    d = dict(row)
    d["authors"] = json.loads(d.pop("authors_json"))
    d["docentes"] = json.loads(d.pop("docentes_json"))
    d["sources"] = json.loads(d.pop("sources_json"))
    return d

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
        return _row_to_work(row)
    return None

def find_existing_work(title, doi=None, year=None):
    from normalization import clean_doi, clean_title, likely_same_title
    c_doi = clean_doi(doi)
    c_title = clean_title(title)
    
    with conn() as c:
        # 1. Se tem DOI, busca direto por DOI
        if c_doi:
            row = c.execute("SELECT * FROM works WHERE canonical_key = ? OR doi = ?", (f"doi:{c_doi}", c_doi)).fetchone()
            if row:
                return _row_to_work(row)
            base_doi = c_doi[:-2] if c_doi.endswith("-w") else c_doi
            row = c.execute("SELECT * FROM works WHERE doi LIKE ? OR doi LIKE ?", (f"{base_doi}%", f"{c_doi}%")).fetchone()
            if row:
                return _row_to_work(row)

        # 2. Busca por título normalizado / limpo
        rows = c.execute("SELECT * FROM works").fetchall()
        for r in rows:
            other_title = clean_title(r["title"])
            if other_title == c_title:
                return _row_to_work(r)

        # 3. Fuzzy match no mesmo ano para títulos com pequenas variações
        if year:
            for r in rows:
                if abs(r["year"] - year) <= 1:
                    other_title = clean_title(r["title"])
                    if ("part" in other_title or "part" in c_title) and other_title != c_title:
                        continue
                    if likely_same_title(other_title, c_title, threshold=94):
                        return _row_to_work(r)

    return None

def deduplicate_all_works():
    from normalization import clean_doi, clean_title, likely_same_title
    with conn() as c:
        rows = c.execute("SELECT * FROM works ORDER BY id ASC").fetchall()
    
    works = []
    for r in rows:
        d = dict(r)
        d["authors"] = json.loads(d["authors_json"])
        d["docentes"] = json.loads(d["docentes_json"])
        d["sources"] = json.loads(d["sources_json"])
        d["clean_title"] = clean_title(d["title"])
        d["clean_doi"] = clean_doi(d.get("doi"))
        works.append(d)
        
    if not works:
        return 0, 0
        
    parent = list(range(len(works)))
    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    def are_duplicate(w1, w2):
        d1 = w1["clean_doi"]
        d2 = w2["clean_doi"]
        
        # Se ambas têm DOI:
        if d1 and d2:
            if d1 == d2:
                return True
            if len(d1) > 10 and len(d2) > 10 and (d1.startswith(d2) or d2.startswith(d1)):
                return True
            return False

        # Se pelo menos uma não tem DOI:
        c1 = w1["clean_title"]
        c2 = w2["clean_title"]
        if c1 == c2:
            return True
            
        if abs(w1["year"] - w2["year"]) <= 1:
            if ("part" in c1 or "part" in c2) and c1 != c2:
                return False
            words1 = set(c1.split())
            words2 = set(c2.split())
            if words1 and words2:
                overlap = len(words1 & words2) / max(len(words1), len(words2))
                if overlap >= 0.7:
                    if fuzz.ratio(c1, c2) >= 94:
                        return True
        return False

    # Indexação por Clean Title
    title_map = {}
    for i, w in enumerate(works):
        ct = w["clean_title"]
        if ct:
            title_map.setdefault(ct, []).append(i)

    for ct, idxs in title_map.items():
        for k in range(len(idxs)-1):
            if are_duplicate(works[idxs[k]], works[idxs[k+1]]):
                union(idxs[k], idxs[k+1])

    # Indexação por DOI
    doi_map = {}
    for i, w in enumerate(works):
        cd = w["clean_doi"]
        if cd:
            doi_map.setdefault(cd, []).append(i)
            base_doi = cd[:-2] if cd.endswith("-w") else cd
            doi_map.setdefault(base_doi, []).append(i)

    for cd, idxs in doi_map.items():
        for k in range(len(idxs)-1):
            if are_duplicate(works[idxs[k]], works[idxs[k+1]]):
                union(idxs[k], idxs[k+1])

    # Fuzzy dentro do mesmo ano para obras sem DOI
    by_year = {}
    for i, w in enumerate(works):
        if not w["clean_doi"]:
            by_year.setdefault(w["year"], []).append(i)

    for year, no_doi_idxs in by_year.items():
        all_year_idxs = [idx for idx, w in enumerate(works) if abs(w["year"] - year) <= 1]
        for i in no_doi_idxs:
            for j in all_year_idxs:
                if i != j and find(i) != find(j):
                    if are_duplicate(works[i], works[j]):
                        union(i, j)

    # Coletar clusters
    clusters_map = {}
    for i in range(len(works)):
        r = find(i)
        clusters_map.setdefault(r, []).append(works[i])

    clusters = [group for group in clusters_map.values() if len(group) > 1]
    to_delete_ids = []
    to_update_works = []

    for c in clusters:
        def score(w):
            s = 0
            if w.get("doi"): s += 50
            if w.get("canonical_key", "").startswith("doi:"): s += 30
            known_docs = [d for d in w.get("docentes", []) if d != "Desconhecido"]
            s += len(known_docs) * 10
            if len(w.get("authors", [])) > 0: s += 5
            return s

        c_sorted = sorted(c, key=score, reverse=True)
        primary = c_sorted[0]
        duplicates = c_sorted[1:]

        merged_docentes = set(primary.get("docentes", []))
        merged_sources = set(primary.get("sources", []))
        merged_doi = primary.get("doi")
        merged_url = primary.get("url")

        for dup in duplicates:
            to_delete_ids.append(dup["id"])
            merged_docentes.update(dup.get("docentes", []))
            merged_sources.update(dup.get("sources", []))
            if not merged_doi and dup.get("doi"):
                merged_doi = dup["doi"]
            if not merged_url and dup.get("url"):
                merged_url = dup["url"]

        if len(merged_docentes) > 1 and "Desconhecido" in merged_docentes:
            merged_docentes.remove("Desconhecido")

        primary["docentes"] = sorted(merged_docentes)
        primary["sources"] = sorted(merged_sources)
        if merged_doi:
            primary["doi"] = merged_doi
            clean_d = clean_doi(merged_doi)
            primary["canonical_key"] = f"doi:{clean_d}"
            primary["url"] = f"https://doi.org/{clean_d}"

        to_update_works.append(primary)

    if to_delete_ids:
        with conn() as c_db:
            for primary in to_update_works:
                c_db.execute("""
                    UPDATE works SET 
                        canonical_key = ?,
                        doi = ?,
                        url = ?,
                        docentes_json = ?,
                        sources_json = ?,
                        authors_json = ?
                    WHERE id = ?
                """, (
                    primary["canonical_key"],
                    primary.get("doi"),
                    primary.get("url"),
                    json.dumps(primary["docentes"], ensure_ascii=False),
                    json.dumps(primary["sources"], ensure_ascii=False),
                    json.dumps(primary["authors"], ensure_ascii=False),
                    primary["id"]
                ))

            for dup_id in to_delete_ids:
                c_db.execute("DELETE FROM works WHERE id = ?", (dup_id,))

    return len(clusters), len(to_delete_ids)

def reidentify_all_works():
    from normalization import match_author_to_docentes
    from config_docentes import DOCENTES
    
    with conn() as c:
        rows = c.execute("SELECT id, authors_json, docentes_json FROM works").fetchall()
        
    updated = 0
    with conn() as c:
        for r in rows:
            authors = json.loads(r["authors_json"])
            docentes = json.loads(r["docentes_json"])
            
            new_docentes = set(docentes)
            for a in authors:
                for doc in match_author_to_docentes(a, DOCENTES):
                    new_docentes.add(doc)
                    
            if "Desconhecido" in new_docentes and len(new_docentes) > 1:
                new_docentes.remove("Desconhecido")
                
            sorted_docs = sorted(new_docentes)
            if sorted_docs != docentes:
                c.execute("UPDATE works SET docentes_json = ? WHERE id = ?", (json.dumps(sorted_docs, ensure_ascii=False), r["id"]))
                updated += 1
                
    return updated

def load_works(min_year=2025):
    with conn() as c:
        rows = c.execute("SELECT * FROM works WHERE year>=? ORDER BY year DESC, title", (min_year,)).fetchall()
    out = []
    for r in rows:
        out.append(_row_to_work(r))
    return out

def stats():
    with conn() as c:
        n = c.execute("SELECT COUNT(*) n FROM works").fetchone()["n"]
        y = c.execute("SELECT MAX(updated_at) x FROM works").fetchone()["x"]
    return n, y
