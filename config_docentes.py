import time
import io
import requests
import pandas as pd

# Planilha Google Sheets do PPGMM contendo os docentes
SHEET_ID = "1TzSV0f0FjKjLKSlnGLiDZspDHEMbXVZ9-4p3aRvF3Zw"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Lista de reserva (Fallback) caso a planilha esteja sem conexão
DOCENTES_FALLBACK = [
    {"nome": "ABÍLIO LEMOS CARDOSO JÚNIOR", "lattes": "http://lattes.cnpq.br/6917845268623003"},
    {"nome": "ALDO HENRIQUE DE SOUZA MEDEIROS", "lattes": "http://lattes.cnpq.br/2515109720775692"},
    {"nome": "ALEXANDRE MIRANDA ALVES", "lattes": "http://lattes.cnpq.br/9791718459590574"},
    {"nome": "ALEXEI DERIGLAZOV", "lattes": "http://lattes.cnpq.br/4611908594979062"},
    {"nome": "ALINE VILELA ANDRADE", "lattes": "http://lattes.cnpq.br/0620002058872668"},
    {"nome": "ALONSO SEPÚLVEDA CASTELLANOS", "lattes": "http://lattes.cnpq.br/3015162536500942"},
    {"nome": "ANDERSON LUIS ALBUQUERQUE DE ARAUJO", "lattes": "http://lattes.cnpq.br/0149879668454764"},
    {"nome": "ANTONIO CARLOS FERNANDES", "lattes": "http://lattes.cnpq.br/7334805996142405"},
    {"nome": "CAMILA BORELLI ZELLER", "lattes": "http://lattes.cnpq.br/6671405481844657"},
    {"nome": "CATARINA MENDES DE JESUS", "lattes": "http://lattes.cnpq.br/1004373523973506"},
    {"nome": "CÍCERO FERNANDES DE CARVALHO", "lattes": "http://lattes.cnpq.br/7254493537063903"},
    {"nome": "CLÉCIO DA SILVA FERREIRA", "lattes": "http://lattes.cnpq.br/7842524715253287"},
    {"nome": "DIOGO DA SILVA MACHADO", "lattes": "http://lattes.cnpq.br/9328110145513702"},
    {"nome": "EDUARD TOON", "lattes": "http://lattes.cnpq.br/5171484988159554"},
    {"nome": "FÁBIO RODRIGUES PEREIRA", "lattes": "http://lattes.cnpq.br/6080944492177131"},
    {"nome": "FABIO SCALCO DIAS", "lattes": "http://lattes.cnpq.br/3015017337118202"},
    {"nome": "GERALDO MÁRCIO DE AZEVEDO BOTELHO", "lattes": "http://lattes.cnpq.br/6734011684397258"},
    {"nome": "GRIGORI CHAPIRO", "lattes": "http://lattes.cnpq.br/0311818140902541"},
    {"nome": "GUILHERME CHAUD TIZZIOTTI", "lattes": "http://lattes.cnpq.br/4902161699668371"},
    {"nome": "HUGO DANILO FERNÁNDEZ SARE", "lattes": "http://lattes.cnpq.br/6376119804316926"},
    {"nome": "JACSON SIMSEN", "lattes": "http://lattes.cnpq.br/1268167759247908"},
    {"nome": "LAÍS MOREIRA DOS SANTOS", "lattes": "http://lattes.cnpq.br/2696689057636216"},
    {"nome": "LUIS FERNANDO DE OSÓRIO MELLO", "lattes": "http://lattes.cnpq.br/1959557670325055"},
    {"nome": "LUIZ FERNANDO DE OLIVEIRA FARIA", "lattes": "http://lattes.cnpq.br/4816866372904602"},
    {"nome": "MAICON SONEGO", "lattes": "http://lattes.cnpq.br/4425077751075680"},
    {"nome": "MARIZA STEFANELLO SIMSEN", "lattes": "http://lattes.cnpq.br/0789877452144510"},
    {"nome": "REMY DE PAIVA SANCHIS", "lattes": "http://lattes.cnpq.br/1582551703060830"},
    {"nome": "RICK ANTONIO RISCHTER", "lattes": "http://lattes.cnpq.br/0008831051908517"},
    {"nome": "RODOLFO COLLEGARI", "lattes": "http://lattes.cnpq.br/1839122732302908"},
    {"nome": "ROSANA SUELLI DA MOTTA JAFELICE", "lattes": "http://lattes.cnpq.br/4014114406515905"},
    {"nome": "VICTOR GONZALO LOPEZ NEUMANN", "lattes": "http://lattes.cnpq.br/4039676977357623"},
    {"nome": "VINÍCIUS VIEIRA FÁVARO", "lattes": "http://lattes.cnpq.br/1260415192839593"},
    {"nome": "WILLIAN VERSOLATI FRANÇA", "lattes": "http://lattes.cnpq.br/5600531171701209"},
]

_CACHED_DOCENTES = None
_LAST_FETCH = 0
CACHE_TTL = 300  # 5 minutos

def get_docentes(force_reload=False):
    global _CACHED_DOCENTES, _LAST_FETCH
    now = time.time()
    
    if not force_reload and _CACHED_DOCENTES and (now - _LAST_FETCH < CACHE_TTL):
        return _CACHED_DOCENTES

    try:
        resp = requests.get(SHEET_URL, timeout=5)
        if resp.status_code == 200:
            df = pd.read_csv(io.StringIO(resp.text))
            docentes = []
            for _, row in df.iterrows():
                nome = str(row.get("Nome") or "").strip().upper()
                if nome in ["ALEXEI DERIGLAZOVI", "ALEXEI A. DERIGLAZOV", "ALEXEI A DERIGLAZOV"]:
                    nome = "ALEXEI DERIGLAZOV"
                lattes = str(row.get("Lattes") or "").strip()
                if not nome or nome == "NAN":
                    continue
                if lattes.endswith(".0"):
                    lattes = lattes[:-2]
                if lattes and not lattes.lower() == "nan" and not lattes.startswith("http"):
                    lattes = f"http://lattes.cnpq.br/{lattes}"
                elif lattes.lower() == "nan":
                    lattes = ""
                docentes.append({"nome": nome, "lattes": lattes})
            
            if docentes:
                _CACHED_DOCENTES = docentes
                _LAST_FETCH = now
                return _CACHED_DOCENTES
    except Exception as e:
        print(f"[config_docentes] Aviso: Não foi possível obter docentes da planilha ({e}). Usando dados salvos.")

    if _CACHED_DOCENTES:
        return _CACHED_DOCENTES
    return DOCENTES_FALLBACK

def __getattr__(name):
    if name == "DOCENTES":
        return get_docentes()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
