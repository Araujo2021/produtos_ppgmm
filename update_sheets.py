import re

with open('importer_sheets.py', 'r') as f:
    content = f.read()

content = content.replace(
    'last_names = [norm_name(d["nome"]).split()[-1] for d in DOCENTES]',
    '''all_parts = []
            for d in DOCENTES:
                all_parts.extend([p for p in norm_name(d["nome"]).split() if p not in {'de','da','do','das','dos'}])'''
)

old_fallback = """                # Se o chunk só tem 1 palavra ("FARIA"), é seguro se for único.
                if len(chunk_parts) == 1:
                    if was_split_by_semicolon:
                        last_n = chunk_parts[0]
                        if len(last_n) > 3 and last_names.count(last_n) == 1:
                            for d in DOCENTES:
                                if d["nome"] not in docentes_identificados and norm_name(d["nome"]).split()[-1] == last_n:
                                    docentes_identificados.append(d["nome"])
                                
                elif len(chunk_parts) > 1:
                    first_word = chunk_parts[0]
                    last_word = chunk_parts[-1]
                    
                    if len(first_word) > 3 and last_names.count(first_word) == 1:
                        for d in DOCENTES:
                            dn_parts = [p for p in norm_name(d["nome"]).split() if p not in {"de", "da", "do", "das", "dos"}]
                            if d["nome"] not in docentes_identificados and dn_parts[-1] == first_word:
                                prof_initials = [p[0] for p in dn_parts[:-1]]
                                author_initials = [p[0] for p in chunk_parts[1:]]
                                if author_initials and prof_initials and all(a == p for a, p in zip(author_initials, prof_initials)):
                                    docentes_identificados.append(d["nome"])
                                    
                    if len(last_word) > 3 and last_names.count(last_word) == 1:
                        for d in DOCENTES:
                            dn_parts = [p for p in norm_name(d["nome"]).split() if p not in {"de", "da", "do", "das", "dos"}]
                            if d["nome"] not in docentes_identificados and dn_parts[-1] == last_word:
                                prof_initials = [p[0] for p in dn_parts[:-1]]
                                author_initials = [p[0] for p in chunk_parts[:-1]]
                                if author_initials and prof_initials and all(a == p for a, p in zip(author_initials, prof_initials)):
                                    docentes_identificados.append(d["nome"])"""

new_fallback = """                # Fallback Universal
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
                                        docentes_identificados.append(d["nome"])"""

if old_fallback in content:
    content = content.replace(old_fallback, new_fallback)
    with open('importer_sheets.py', 'w') as f:
        f.write(content)
    print("importer_sheets.py successfully updated!")
else:
    print("Old fallback not found in sheets!")
