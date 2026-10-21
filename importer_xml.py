import xml.etree.ElementTree as ET
from db import get_work_by_key, upsert_work
from normalization import canonical_key, norm_name, match_author_to_docentes
from config_docentes import DOCENTES

def parse_lattes_xml(xml_content, progress_callback=None):
    touched = 0
    errors = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Tenta descobrir o dono do currículo
        dono_nome = ""
        dados_gerais = root.find("DADOS-GERAIS")
        if dados_gerais is not None:
            dono_nome = dados_gerais.get("NOME-COMPLETO", "")
            
        dono_identificado = None
        if dono_nome:
            target_dono = norm_name(dono_nome)
            for d in DOCENTES:
                if norm_name(d["nome"]) == target_dono:
                    dono_identificado = d["nome"]
                    break

        prod_bib = root.find("PRODUCAO-BIBLIOGRAFICA")
        if prod_bib is None:
            return 0, ["Nenhuma PRODUCAO-BIBLIOGRAFICA encontrada no XML."]
            
        artigos = prod_bib.find("ARTIGOS-PUBLICADOS")
        if artigos is None:
            return 0, ["Nenhum ARTIGO-PUBLICADO encontrado no XML."]
            
        for art in artigos.findall("ARTIGO-PUBLICADO"):
            dados_basicos = art.find("DADOS-BASICOS-DO-ARTIGO")
            detalhes = art.find("DETALHAMENTO-DO-ARTIGO")
            
            if dados_basicos is None: continue
            
            titulo = str(dados_basicos.get("TITULO-DO-ARTIGO", "")).strip()
            if not titulo: continue
            
            try:
                ano = int(dados_basicos.get("ANO-DO-ARTIGO", 0))
            except:
                ano = 0
                
            doi = str(dados_basicos.get("DOI", "")).strip()
            
            periodico = ""
            if detalhes is not None:
                periodico = str(detalhes.get("TITULO-DO-PERIODICO-OU-REVISTA", "")).strip()
                
            # Extrair autores
            lista_autores = []
            for aut in art.findall("AUTORES-DO-ARTIGO"):
                nome_citacao = aut.get("NOME-PARA-CITACAO", "")
                nome_completo = aut.get("NOME-COMPLETO-DO-AUTOR", "")
                if nome_completo:
                    lista_autores.append(nome_completo.strip())
                elif nome_citacao:
                    lista_autores.append(nome_citacao.strip())
                    
            docentes_identificados = []
            if dono_identificado:
                docentes_identificados.append(dono_identificado)
                
            # Identifica os outros autores usando o padrão do normalization
            for a in lista_autores:
                for m in match_author_to_docentes(a, DOCENTES):
                    if m not in docentes_identificados:
                        docentes_identificados.append(m)
                                    
            if not docentes_identificados:
                docentes_identificados = ["Desconhecido"]
                
            key = canonical_key(titulo, doi)
            existing = get_work_by_key(key)
            if existing:
                docs = set(existing.get("docentes", []))
                docs.update(docentes_identificados)
                existing["docentes"] = sorted(docs)
                
                srcs = set(existing.get("sources", []))
                srcs.add("Lattes XML")
                existing["sources"] = sorted(srcs)
                
                auths = existing.get("authors", [])
                for a in lista_autores:
                    if a not in auths:
                        auths.append(a)
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
                    "url": f"https://doi.org/{doi}" if doi else None,
                    "authors": lista_autores,
                    "docentes": docentes_identificados,
                    "sources": ["Lattes XML"],
                }
                upsert_work(w)
            touched += 1
            
    except Exception as e:
        errors.append(f"Erro ao processar arquivo: {e}")
        
    return touched, errors
