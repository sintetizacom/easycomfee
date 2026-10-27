"""Configuracao da maquina: onde esta o ComfyUI e por qual endereco falar com ele.

Le `config.json` na raiz do projeto (copiar de `config.example.json`). Cada
chave tambem pode vir de uma variavel de ambiente com o mesmo nome em
maiusculas, que tem prioridade. Nada aqui depende da maquina do autor.
"""
import json
import os
import pathlib
from urllib.parse import urlparse

RAIZ = pathlib.Path(__file__).parent.parent
ARQUIVO = RAIZ / "config.json"


def _ler() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


_ARQ = _ler()


def _valor(chave: str, padrao: str = "") -> str:
    return os.environ.get(chave.upper()) or _ARQ.get(chave) or padrao


# Endereco do ComfyUI. Local por padrao.
COMFY_URL = _valor("comfy_url", "http://127.0.0.1:8188").rstrip("/")
# Segundo motor (Flux 3). Sem configuracao, e o mesmo motor.
COMFY_URL_FLUX3 = _valor("comfy_url_flux3", COMFY_URL).rstrip("/")
COMFY_WS = COMFY_URL.replace("http", "ws", 1) + "/ws"
COMFY_PORTA = urlparse(COMFY_URL).port or 8188

# Pasta do ComfyUI (a que contem main.py). Vazia quando o motor e remoto.
COMFY_DIR = pathlib.Path(_valor("comfy_dir")) if _valor("comfy_dir") else None
# Onde esta o CODIGO do ComfyUI que roda (custom_nodes e o Python dele). Quase
# sempre e o proprio comfy_dir; difere quando o motor sobe de uma instalacao e
# usa as pastas input/output de outra (--input-directory/--output-directory).
COMFY_CODIGO_DIR = (pathlib.Path(_valor("comfy_codigo_dir"))
                    if _valor("comfy_codigo_dir") else COMFY_DIR)
COMFY_DIR_FLUX3 = (pathlib.Path(_valor("comfy_dir_flux3"))
                   if _valor("comfy_dir_flux3") else COMFY_DIR)


def _pasta(chave: str, sub: str) -> pathlib.Path:
    if _valor(chave):
        return pathlib.Path(_valor(chave))
    return (COMFY_DIR / sub) if COMFY_DIR else (RAIZ / "dados" / sub)


COMFY_ENTRADA = _pasta("comfy_entrada", "input")
COMFY_SAIDA = _pasta("comfy_saida", "output")

# Ambientes opcionais fora do ComfyUI (separar faixas, trocar voz).
SEPARADOR_DIR = pathlib.Path(_valor("separador_dir", str(RAIZ / "extras" / "separador")))
APPLIO_DIR = pathlib.Path(_valor("applio_dir", str(RAIZ / "extras" / "applio")))

# Porta deste app (a interface e a API).
APP_PORTA = int(_valor("app_porta", "8600"))

# Para onde o instalador baixa os modelos. Padrao: a pasta models do ComfyUI.
MODELOS_DIR = (pathlib.Path(_valor("modelos_dir")) if _valor("modelos_dir")
               else (COMFY_DIR / "models" if COMFY_DIR else RAIZ / "dados" / "models"))
# Token do Hugging Face, so para repositorios que exigem login. Opcional.
HF_TOKEN = _valor("hf_token")


def ssl_sistema():
    """Certificados do sistema operacional para conexoes externas (Hugging
    Face, Comfy Cloud). Antivirus e proxies que inspecionam HTTPS instalam o
    proprio certificado no sistema, e o pacote certifi nao o conhece."""
    import ssl
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()

# Para onde o app manda quem precisa de creditos ou assinatura da Comfy Cloud.
# Um lugar so: e aqui que entra um link de afiliado.
LINK_RECARGA = _valor("link_recarga", "https://cloud.comfy.org")

# Versao do concurso: so modelos de pesos abertos, sem nos de parceiro nem
# APIs fechadas (categoria "Open Weights Only"). "0" no config.json libera.
SO_MODELOS_ABERTOS = str(_valor("so_modelos_abertos", "1")).lower() not in ("0", "false", "nao", "no")
# Modos que existem no codigo mas nao vao para a versao publica.
MODELOS_OCULTOS = set(_ARQ.get("modelos_ocultos", ["kroma_foto"]))


def _python_do_comfy():
    """O Python do ComfyUI, para instalar as dependencias dos nos extras.
    Procura os lugares que os instaladores comuns usam."""
    if _valor("comfy_python"):
        return pathlib.Path(_valor("comfy_python"))
    d = COMFY_CODIGO_DIR
    if not d:
        return None
    # O venv do proprio ComfyUI primeiro: o instalador de desktop tem um
    # standalone-env SEM torch ao lado, e o que roda e o .venv.
    for c in (d / ".venv" / "Scripts" / "python.exe",
              d / "venv" / "Scripts" / "python.exe",
              d / ".venv" / "bin" / "python",
              d / "venv" / "bin" / "python",
              d.parent / "python_embeded" / "python.exe",
              d.parent / "standalone-env" / "python.exe"):
        if c.exists():
            return c
    return None


COMFY_PYTHON = _python_do_comfy()
