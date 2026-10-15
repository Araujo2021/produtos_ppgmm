import json
from db import get_work_by_key, upsert_work, find_existing_work
from normalization import canonical_key, norm_name, match_author_to_docentes
from config_docentes import DOCENTES

def parse_scriptlattes_json(json_content):
    touched = 0
    errors = []
    
    try:
        data = json.loads(json_content)
        dono_nome = data.get("nome_completo", "")
        
        dono_identificado = None
        if dono_nome:
            target_dono = norm_name(dono_nome)
            for d in DOCENTES:
                if norm_name(d["nome"]) == target_dono:
                    dono_identificado = d["nome"]
                    break
                    
        prod = data.get("producao_bibliografica", {})
        artigos = prod.get("artigos_periodicos", [])
        
        if not artigos:
            return 0, ["Nenhum artigo encontrado no arquivo JSON deste pesquisador."]
            
        for art in artigos:
            titulo = str(art.get("titulo", "")).strip()
            if not titulo: continue
            
            try:
                ano = int(art.get("ano", 0))
            except:
                ano = 0
                
            doi = str(art.get("doi", "")).strip()
            if doi.startswith("http"):
                doi = doi.split("doi.org/")[-1]
                
            periodico = str(art.get("revista", "")).strip()
            
            autores_str = str(art.get("autores", ""))
            was_split_by_semicolon = False
            if ";" in autores_str:
                lista_autores = [a.strip() for a in autores_str.split(";") if a.strip()]
                was_split_by_semicolon = True
            else:
                chunks = [a.strip() for a in autores_str.split(",") if a.strip()]
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
                
            docentes_identificados = []
            if dono_identificado:
                docentes_identificados.append(dono_identificado)
                
            for a in lista_autores:
                matches = match_author_to_docentes(a, DOCENTES)
                for m in matches:
                    if m not in docentes_identificados:
                        docentes_identificados.append(m)

            if not docentes_identificados:
                docentes_identificados = ["Desconhecido"]
                
            key = canonical_key(titulo, doi)
            existing = find_existing_work(titulo, doi, ano)
            if existing:
                # Se a obra existente não tinha DOI e esta nova tem, atualiza!
                if doi and not existing.get("doi"):
                    existing["doi"] = doi
                    existing["canonical_key"] = key
                    existing["url"] = f"https://doi.org/{doi}"

                docs = set(existing.get("docentes", []))
                docs.update(docentes_identificados)
                if len(docs) > 1 and "Desconhecido" in docs:
                    docs.remove("Desconhecido")
                existing["docentes"] = sorted(docs)
                
                srcs = set(existing.get("sources", []))
                srcs.add("scriptLattes")
                existing["sources"] = sorted(srcs)
                
                # Adota a versão do Lattes (sobrescreve se já existir, para não duplicar formatos diferentes)
                if lista_autores:
                    existing["authors"] = lista_autores
                
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
                    "url": f"https://doi.org/{doi}" if doi else None,
                    "authors": lista_autores,
                    "docentes": docentes_identificados,
                    "sources": ["scriptLattes"],
                }
                upsert_work(w)
            touched += 1
            
    except Exception as e:
        errors.append(f"Erro ao processar arquivo JSON: {e}")
        
    return touched, errors
