import requests
import pandas as pd
from db import get_work_by_key, upsert_work
from normalization import canonical_key, norm_name
from config_docentes import DOCENTES
import io

# Link direto para o formato CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVCjQNGSDkgU-ykkzfwtX_eiD2uKp51LRQoaMba74z4ZruH0NxBaqIiHUp6ycgfOmx8PWqeEfEzLKO/pub?output=csv"

def import_from_sheets(progress=None):
    touched = 0
    errors = []
    
    if progress:
        progress(0.2, "Baixando dados da planilha...")
        
    try:
        r = requests.get(SHEET_URL, allow_redirects=True, timeout=30)
        r.raise_for_status()
        
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = df.columns.str.strip()
        
        if progress:
            progress(0.5, "Processando dados recebidos...")
            
        for _, row in df.iterrows():
            try:
                ano = int(row.get("Ano da publicação", 0))
            except:
                ano = 0
                
            titulo = str(row.get("Título do artigo", "")).strip()
            if not titulo or titulo.lower() == "nan":
                continue
                
            doi_link = str(row.get("DOI (Se exisitir) ou link do artigo", "")).strip()
            if doi_link.lower() == "nan": doi_link = ""
            
            periodico = str(row.get("Nome do jornal", "")).strip()
            if periodico.lower() == "nan": periodico = ""
            
            autores = str(row.get("Nome dos autores (separados por vírgula)", "")).strip()
            if autores.lower() == "nan" or not autores:
                autores = ""
                
            was_split_by_semicolon = False
            if ";" in autores:
                lista_autores = [a.strip() for a in autores.split(";") if a.strip()]
                was_split_by_semicolon = True
            else:
                chunks = [a.strip() for a in autores.split(",") if a.strip()]
                lista_autores = []
                i = 0
                while i < len(chunks):
                    c = chunks[i]
                    merge_next = False
                    if i + 1 < len(chunks):
                        next_c = chunks[i+1]
                        next_parts = next_c.split()
                        if next_parts and all(len(p.replace('.', '')) <= 2 for p in next_parts):
                            merge_next = True
                        elif " " not in c.strip():
                            merge_next = True
                    if merge_next:
                        lista_autores.append(c + ", " + chunks[i+1])
                        i += 2
                    else:
                        lista_autores.append(c)
                        i += 1
            
            email = str(row.get("Endereço de e-mail", "")).strip().lower()
            email_parts = email.split("@")[0].replace("_", ".").split(".") if email else []
            
            docentes_identificados = []
            
            # 1. Tenta identificar pelo email (muito mais preciso se for o dono da linha)
            if email_parts:
                for d in DOCENTES:
                    dn = norm_name(d["nome"])
                    if all(part in dn.split() for part in email_parts if len(part) > 2):
                        docentes_identificados.append(d["nome"])
            
            # 2. Tenta identificar pela lista de autores
            for a in lista_autores:
                target = norm_name(a)
                # Tira coisas como 'de ', 'da ' para ajudar no match do sobrenome
                target_clean = " ".join([p for p in target.split() if p not in {"de", "da", "do", "das", "dos"}])
                for d in DOCENTES:
                    dn = norm_name(d["nome"])
                    if dn == target:
                        docentes_identificados.append(d["nome"])
                    else:
                        ap = target_clean.split()
                        dp = dn.split()
                        if len(ap) >= 2 and len(dp) >= 2:
                            if ap[0] == dp[0] and ap[-1] == dp[-1]:
                                docentes_identificados.append(d["nome"])
                            elif ap == dp[:len(ap)]:
                                docentes_identificados.append(d["nome"])
                            else:
                                valid_ap = [w for w in ap if len(w) > 2]
                                if len(valid_ap) >= 2 and all(w in dp for w in valid_ap):
                                    docentes_identificados.append(d["nome"])
                            
            # 3. Tenta identificar cruzando as partes do nome com a string inteira de autores
            # Resolve o problema de nomes no formato "SOBRENOME, NOME" misturados por vírgula
            autores_norm_split = norm_name(autores).split()
            for d in DOCENTES:
                if d["nome"] in docentes_identificados:
                    continue
                dn_parts = [p for p in norm_name(d["nome"]).split() if len(p) > 2]
                if dn_parts and all(p in autores_norm_split for p in dn_parts):
                    docentes_identificados.append(d["nome"])
            
            # 4. Fallback radical para formato "SOBRENOME, INICIAIS"
            # Conta a frequência dos últimos sobrenomes
            all_parts = []
            for d in DOCENTES:
                all_parts.extend([p for p in norm_name(d["nome"]).split() if p not in {'de','da','do','das','dos'}])
            for a in lista_autores:
                chunk_parts = [p for p in norm_name(a).split() if p not in {"de", "da", "do", "das", "dos"}]
                if not chunk_parts: continue
                target_clean = " ".join(chunk_parts)
                
                # Fallback Universal
                unique_parts_in_chunk = [p for p in chunk_parts if len(p) > 3 and all_parts.count(p) == 1]
                for up in unique_parts_in_chunk:
                    for d in DOCENTES:
                        if d["nome"] in docentes_identificados: continue
                        dn_parts = [p for p in norm_name(d["nome"]).split() if p not in {"de", "da", "do", "das", "dos"}]
                        if up in dn_parts:
                            prof_missing_parts = [p for p in dn_parts if p not in chunk_parts]
                            prof_expected_initials = [p[0] for p in prof_missing_parts]
                            author_provided_initials = [p for p in chunk_parts if len(p) <= 2]
                            
                            if author_provided_initials:
                                if all(x == y for x, y in zip(author_provided_initials, prof_expected_initials)):
                                    docentes_identificados.append(d["nome"])
                            else:
                                if len(chunk_parts) == 1:
                                    if was_split_by_semicolon:
                                        docentes_identificados.append(d["nome"])
                                else:
                                    other_words = [p for p in chunk_parts if len(p) > 2 and p != up]
                                    if all(w in dn_parts for w in other_words):
                                        docentes_identificados.append(d["nome"])
                    
            docentes_identificados = list(set(docentes_identificados))
            if not docentes_identificados:
                docentes_identificados = ["Desconhecido"]
                
            key = canonical_key(titulo, doi_link)
            
            existing = get_work_by_key(key)
            if existing:
                docs = set(existing.get("docentes", []))
                docs.update(docentes_identificados)
                if len(docs) > 1 and "Desconhecido" in docs:
                    docs.remove("Desconhecido")
                existing["docentes"] = sorted(docs)
                
                srcs = set(existing.get("sources", []))
                srcs.add("Planilha")
                existing["sources"] = sorted(srcs)
                
                # Se já existe, não sobrescreve a lista de autores (para priorizar o formato do Lattes)
                if not existing.get("authors"):
                    existing["authors"] = lista_autores
                
                upsert_work(existing)
            else:
                w = {
                    "canonical_key": key,
                    "title": titulo,
                    "year": ano,
                    "doi": doi_link if doi_link else None,
                    "journal": periodico if periodico else None,
                    "work_type": "article",
                    "cited_by": 0,
                    "openalex_id": None,
                    "url": doi_link if doi_link.startswith("http") else None,
                    "authors": lista_autores,
                    "docentes": docentes_identificados,
                    "sources": ["Planilha"],
                }
                upsert_work(w)
            touched += 1
            
    except Exception as e:
        errors.append(f"Erro ao acessar/processar a planilha: {e}")
        
    return {"registros_processados": touched, "erros": errors}
