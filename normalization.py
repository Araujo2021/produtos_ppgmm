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

def canonical_key(title, doi=None):
    if doi:
        d = doi.lower().strip()
        d = d.replace("https://doi.org/","").replace("http://doi.org/","").replace("doi:","").strip()
        return "doi:" + d
    return "title:" + hashlib.sha1(norm_text(title).encode("utf-8")).hexdigest()

def likely_same_title(a, b, threshold=94):
    return fuzz.ratio(norm_text(a), norm_text(b)) >= threshold
