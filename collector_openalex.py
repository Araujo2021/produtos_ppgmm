import requests, time
from urllib.parse import quote
from normalization import norm_name, canonical_key

BASE = "https://api.openalex.org"
UA = "Produtos-PPGMM/1.0 (academic dashboard)"

def _get(url, params=None, timeout=30):
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.json()

def resolve_author(name, openalex_id=None, orcid=None):
    if openalex_id:
        try:
            # allow passing full URL or just the ID
            short_id = openalex_id.split("/")[-1]
            return _get(f"{BASE}/authors/{short_id}")
        except:
            pass
    if orcid:
        try:
            short_orcid = orcid.split("/")[-1]
            return _get(f"{BASE}/authors/orcid:{short_orcid}")
        except:
            pass

    data = _get(f"{BASE}/authors", {"search": name, "per-page": 5})
    results = data.get("results", [])
    if not results:
        return None
    # Prefer exact-ish display name, then most cited/work-rich result.
    target = norm_name(name)
    scored = []
    for a in results:
        disp = norm_name(a.get("display_name",""))
        exact = int(disp == target)
        scored.append((exact, a.get("works_count",0), a.get("cited_by_count",0), a))
    scored.sort(key=lambda x:(x[0],x[1],x[2]), reverse=True)
    return scored[0][3]

def search_author_candidates(name):
    data = _get(f"{BASE}/authors", {"search": name, "per-page": 10})
    results = data.get("results", [])
    cands = []
    for a in results:
        inst = a.get("last_known_institution")
        inst_name = inst.get("display_name") if inst else "Instituição desconhecida"
        cands.append({
            "id": a.get("id"),
            "display_name": a.get("display_name"),
            "institution": inst_name,
            "works_count": a.get("works_count", 0)
        })
    return cands

def fetch_author_works(author_openalex_id, min_year=2025):
    short_id = author_openalex_id.rsplit("/",1)[-1]
    cursor = "*"
    out = []
    while cursor:
        data = _get(f"{BASE}/works", {
            "filter": f"author.id:{short_id},from_publication_date:{min_year}-01-01",
            "per-page": 100,
            "cursor": cursor,
            "sort": "publication_date:desc",
        })
        out.extend(data.get("results", []))
        cursor = data.get("meta",{}).get("next_cursor")
        if not data.get("results"):
            break
        time.sleep(0.08)
    return out

def parse_work(w):
    title = w.get("title") or "(sem título)"
    doi = w.get("doi")
    if doi:
        doi = doi.replace("https://doi.org/","")
    authors = [a.get("author",{}).get("display_name","") for a in w.get("authorships",[])]
    source = ((w.get("primary_location") or {}).get("source") or {})
    journal = source.get("display_name")
    url = doi and f"https://doi.org/{doi}" or w.get("id")
    return {
        "canonical_key": canonical_key(title, doi),
        "title": title,
        "year": int(w.get("publication_year") or 0),
        "doi": doi,
        "journal": journal,
        "work_type": w.get("type"),
        "cited_by": int(w.get("cited_by_count") or 0),
        "openalex_id": w.get("id"),
        "url": url,
        "authors": authors,
        "sources": ["OpenAlex"],
    }
