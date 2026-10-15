import requests
import time

UA = "Produtos-PPGMM/1.0 (academic dashboard)"

_CACHE = {}

def enrich_by_doi(doi):
    if not doi:
        return {}
    if doi in _CACHE:
        return _CACHE[doi]
        
    url = "https://api.crossref.org/works/" + doi
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA})
        if r.status_code != 200:
            _CACHE[doi] = {}
            return {}
        m = r.json().get("message", {})
        container = m.get("container-title") or []
        res = {
            "journal": container[0] if container else None,
            "publisher": m.get("publisher"),
            "crossref_url": m.get("URL"),
        }
        _CACHE[doi] = res
        time.sleep(0.1) # respect rate limit slightly
        return res
    except Exception:
        _CACHE[doi] = {}
        return {}
