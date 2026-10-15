import pandas as pd
from pathlib import Path
from db import get_work_by_key, upsert_work
from normalization import canonical_key, norm_name
from config_docentes import DOCENTES

CSV_DIR = Path("csv")

def get_docente_name(raw_name):
    target = norm_name(raw_name)
    for d in DOCENTES:
        dn = norm_name(d["nome"])
        if dn == target:
            return d["nome"]
        ap = target.split()
        dp = dn.split()
        if len(ap) >= 2 and len(dp) >= 2 and ap[0] == dp[0] and ap[-1] == dp[-1]:
            return d["nome"]
    return raw_name

def import_all_csvs(progress=None):
    if not CSV_DIR.exists():
        return {"registros_processados": 0, "erros": ["Pasta csv não encontrada."]}
    
    files = list(CSV_DIR.glob("*.csv"))
    if not files:
        return {"registros_processados": 0, "erros": ["Nenhum arquivo CSV encontrado na pasta."]}
    
    touched = 0
    errors = []
    
    for i, file_path in enumerate(files, 1):
        try:
            if progress:
                progress(i / len(files), f"Lendo {file_path.name}")
            
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                try:
                    ano = int(row.get("ano_publicacao", 0))
                except:
                    ano = 0
                
                titulo = str(row.get("titulo_publicacao", "")).strip()
                if not titulo or titulo.lower() == "nan":
                    continue
                
                doi = str(row.get("doi", "")).strip()
                if doi.lower() == "nan": doi = ""
                
                periodico = str(row.get("periodico", "")).strip()
                if periodico.lower() == "nan": periodico = ""
                
                raw_nome = str(row.get("nome", "")).strip()
                if raw_nome.lower() == "nan": raw_nome = ""
                docente = get_docente_name(raw_nome) if raw_nome else "Desconhecido"
                
                key = canonical_key(titulo, doi)
                
                existing = get_work_by_key(key)
                if existing:
                    docs = set(existing.get("docentes", []))
                    docs.add(docente)
                    existing["docentes"] = sorted(docs)
                    
                    srcs = set(existing.get("sources", []))
                    srcs.add("Lattes/CSV")
                    existing["sources"] = sorted(srcs)
                    
                    auths = existing.get("authors", [])
                    if docente not in auths:
                        auths.append(docente)
                    existing["authors"] = auths
                    
                    upsert_work(existing)
                else:
                    w = {
                        "canonical_key": key,
                        "title": titulo,
                        "year": ano,
                        "doi": doi if doi else None,
                        "journal": periodico if periodico else None,
                        "work_type": "article",
                        "cited_by": 0,
                        "openalex_id": None,
                        "url": None,
                        "authors": [docente],
                        "docentes": [docente],
                        "sources": ["Lattes/CSV"],
                    }
                    upsert_work(w)
                touched += 1
        except Exception as e:
            errors.append(f"Erro no arquivo {file_path.name}: {e}")
            
    return {"registros_processados": touched, "erros": errors}
