import time
from config_docentes import DOCENTES
from collector_openalex import _get, parse_work, BASE
from normalization import norm_name
from db import init_db, load_works, upsert_work, get_mappings, conn
from collector_crossref import enrich_by_doi

MIN_YEAR = 2025

def get_all_db_works():
    with conn() as c:
        rows = c.execute("SELECT * FROM works").fetchall()
    return [dict(r) for r in rows]

def update_all(progress=None):
    init_db()
    works_in_db = get_all_db_works()
    total = len(works_in_db)
    if total == 0:
        return {"registros_processados": 0, "identidades": [], "erros": ["Nenhum registro encontrado no banco para atualizar. Sincronize com a planilha primeiro."]}
    
    touched = 0
    errors = []
    
    for i, row in enumerate(works_in_db, 1):
        try:
            if progress:
                progress(i/total, f"Atualizando: {row['title'][:30]}...")
                
            updated = False
            doi = row.get("doi")
            title = row.get("title")
            
            # Tenta OpenAlex pelo DOI
            if doi:
                try:
                    data = _get(f"{BASE}/works/doi:{doi}")
                    parsed = parse_work(data)
                    row["cited_by"] = max(row.get("cited_by", 0), parsed.get("cited_by", 0))
                    if not row.get("journal") and parsed.get("journal"):
                        row["journal"] = parsed["journal"]
                    if not row.get("url") and parsed.get("url"):
                        row["url"] = parsed["url"]
                    if not row.get("openalex_id") and parsed.get("openalex_id"):
                        row["openalex_id"] = parsed["openalex_id"]
                    updated = True
                except Exception as e:
                    pass
                    
            # Se não tem DOI, tenta OpenAlex pelo título
            if not updated and title:
                try:
                    data = _get(f"{BASE}/works", {"search": title, "per-page": 1})
                    if data.get("results"):
                        cand = data["results"][0]
                        # Verifica se o título bate razoavelmente bem
                        if cand.get("title") and norm_name(cand["title"]) == norm_name(title):
                            parsed = parse_work(cand)
                            row["cited_by"] = max(row.get("cited_by", 0), parsed.get("cited_by", 0))
                            if not row.get("journal") and parsed.get("journal"):
                                row["journal"] = parsed["journal"]
                            if not row.get("doi") and parsed.get("doi"):
                                row["doi"] = parsed["doi"]
                            if not row.get("url") and parsed.get("url"):
                                row["url"] = parsed["url"]
                            if not row.get("openalex_id") and parsed.get("openalex_id"):
                                row["openalex_id"] = parsed["openalex_id"]
                            updated = True
                except:
                    pass
            
            # Tenta Crossref pelo DOI (para complementar journal/url)
            if row.get("doi"):
                cr = enrich_by_doi(row["doi"])
                if cr:
                    if cr.get("journal"): row["journal"] = cr["journal"]
                    if cr.get("crossref_url") and not row.get("url"): row["url"] = cr["crossref_url"]
                    updated = True
                    
            if updated:
                import json
                row["authors"] = json.loads(row["authors_json"])
                row["docentes"] = json.loads(row["docentes_json"])
                row["sources"] = json.loads(row["sources_json"])
                upsert_work(row)
                touched += 1
                
            time.sleep(0.08) # Evita limite de taxa do OpenAlex
            
        except Exception as e:
            errors.append(f"Erro ao atualizar {row.get('title')}: {e}")
            
    return {"registros_processados": touched, "identidades": [], "erros": errors}
