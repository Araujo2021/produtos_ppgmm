import re, unicodedata, hashlib
from rapidfuzz import fuzz

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))

def norm_text(s):
    s = strip_accents((s or "").lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())

def norm_name(s):
    return norm_text(s)

def clean_doi(d):
    if not d:
        return ""
    d = str(d).lower().strip()
    d = d.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
    return d

def clean_title(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", s)
    return norm_text(s)

def canonical_key(title, doi=None):
    c_doi = clean_doi(doi)
    if c_doi:
        return "doi:" + c_doi
    return "title:" + hashlib.sha1(clean_title(title).encode("utf-8")).hexdigest()

def likely_same_title(a, b, threshold=94):
    c1 = clean_title(a)
    c2 = clean_title(b)
    if c1 == c2:
        return True
    return fuzz.ratio(c1, c2) >= threshold

def match_author_to_docentes(author_str, docentes_list=None):
    if docentes_list is None:
        from config_docentes import DOCENTES
        docentes_list = DOCENTES

    # Trata caso de nomes alternativos separados por " ou " no Lattes
    # Ex: "Mello, L. F. ou Fernando Mello, L."
    if " ou " in author_str:
        sub_authors = author_str.split(" ou ")
        res = []
        for sa in sub_authors:
            for m in match_author_to_docentes(sa, docentes_list):
                if m not in res:
                    res.append(m)
        return res

    a_clean = norm_name(author_str)
    a_parts = [p for p in a_clean.split() if p not in {'de','da','do','das','dos'}]
    if not a_parts:
        return []

    matched = []
    for d in docentes_list:
        d_name = d["nome"]
        d_clean = norm_name(d_name)
        d_parts = [p for p in d_clean.split() if p not in {'de','da','do','das','dos'}]
        if not d_parts:
            continue

        d_surname = d_parts[-1]
        d_firsts = d_parts[:-1]
        d_initials = [p[0] for p in d_firsts]

        # Regra de distinção explícita: Fábio Rodrigues Pereira vs Fabiano Pereira
        # PEREIRA, F. R. / PEREIRA, FÁBIO R. -> Fábio Rodrigues Pereira (docente do PPGMM)
        # PEREIRA, F. / FABIANO PEREIRA -> Fabiano Pereira (não é docente do PPGMM)
        if "pereira" in a_parts and d_surname == "pereira":
            if "fabiano" in a_parts:
                continue
            other_p = [p for p in a_parts if p != "pereira"]
            initials_p = [p for p in other_p if len(p) <= 2]
            words_p = [p for p in other_p if len(p) > 2]
            # Exige conter 'fabio' explicitamente ou a inicial 'r' (de Rodrigues)
            if "fabio" not in words_p and "r" not in initials_p and "rodrigues" not in words_p:
                continue

        # 1. Caso todas as partes do docente estejam no autor (ordem direta ou inversa)
        # Ex: "SIMSEN, JACSON" ou "JACSON SIMSEN"
        if all(p in a_parts for p in d_parts):
            matched.append(d_name)
            continue

        # 2. Caso o sobrenome esteja presente
        # Ex: "SIMSEN, J." ou "Simsen,J." ou "J. Simsen" ou "FERNANDES, ANTONIO C."
        if d_surname in a_parts:
            other_parts = [p for p in a_parts if p != d_surname]
            if other_parts:
                initials_in_author = [p for p in other_parts if len(p) <= 2]
                full_words_in_author = [p for p in other_parts if len(p) > 2]

                if full_words_in_author:
                    if all(w in d_firsts for w in full_words_in_author):
                        unwritten_firsts = [w for w in d_firsts if w not in full_words_in_author]
                        unwritten_initials = [w[0] for w in unwritten_firsts]
                        if not initials_in_author:
                            matched.append(d_name)
                            continue
                        elif len(initials_in_author) <= len(unwritten_initials):
                            if all(x == y for x, y in zip(initials_in_author, unwritten_initials)):
                                matched.append(d_name)
                                continue
                elif initials_in_author:
                    if all(x == y for x, y in zip(initials_in_author, d_initials)):
                        matched.append(d_name)
                        continue

        # 3. Caso o docente use nome do meio como citação (ex: LEMOS, NEUMANN)
        for part in d_firsts:
            if len(part) > 3 and part in a_parts:
                other_docs_with_part = [doc for doc in docentes_list if part in norm_name(doc["nome"]).split()]
                if len(other_docs_with_part) == 1:
                    other_a_parts = [p for p in a_parts if p != part]
                    expected_initials = [p[0] for p in d_parts if p != part]
                    author_initials = [p for p in other_a_parts if len(p) <= 2]
                    if author_initials:
                        if all(x == y for x, y in zip(author_initials, expected_initials)):
                            matched.append(d_name)
                            break
                    elif not other_a_parts:
                        matched.append(d_name)
                        break

    return matched
