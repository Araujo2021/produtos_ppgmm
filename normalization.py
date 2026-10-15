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
