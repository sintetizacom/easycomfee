"""EasyComfee MCP (opcional) vista do Config Models: estado, instalacao com um clique e o
JSON para colar em qualquer cliente. Mesmo molde de bridge.py, mas separado dele.
"""
import importlib.util
import pathlib
import subprocess
import sys
import threading

PASTA = pathlib.Path(__file__).resolve().parent.parent / "easycomfee-mcp"
SERVIDOR = PASTA / "server"
PYTHON = SERVIDOR / ".venv" / "Scripts" / "python.exe"
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ESTADO = {"instalando": False, "erro": "", "etapa": ""}
_trava = threading.Lock()


def _config():
    """O escrever_config.py do MCP (so biblioteca padrao): clientes e registro."""
    spec = importlib.util.spec_from_file_location("easycomfee_mcp_config", SERVIDOR / "escrever_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def estado() -> dict:
    if not PASTA.is_dir():
        return {"disponivel": False}
    cfg = _config()
    return {"disponivel": True, "instalado": PYTHON.exists() and _importa_mcp(), "config": cfg.texto_config(),
            "clientes": [{"nome": n, "registrado": cfg.registrado(a)} for n, a in cfg.clientes()],
            **ESTADO}


def _rodar(args, etapa):
    ESTADO["etapa"] = etapa
    r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=900,
                       creationflags=_SEM_JANELA)
    if r.returncode:
        raise RuntimeError(f"{etapa}: {(r.stderr or r.stdout).strip()[-400:]}")


def _instalar(clientes: list[str]):
    try:
        if not PYTHON.exists():
            # sys._base_executable: o Python de verdade, nao o do .venv do app.
            _rodar([getattr(sys, "_base_executable", sys.executable), "-m", "venv",
                    str(SERVIDOR / ".venv")], "Creating the Python environment")
        if not _importa_mcp():
            _rodar([str(PYTHON), "-m", "pip", "install", "-q", "-r",
                    str(SERVIDOR / "requirements.txt")], "Installing the server")
        if clientes:
            _rodar([str(PYTHON), str(SERVIDOR / "escrever_config.py"), "--registrar", ",".join(clientes)],
                   "Adding it to your AI app")
        ESTADO["erro"] = ""
    except Exception as e:  # mostrado no card; o usuario pode tentar de novo
        ESTADO["erro"] = str(e)
    finally:
        ESTADO["instalando"], ESTADO["etapa"] = False, ""


def _importa_mcp() -> bool:
    r = subprocess.run([str(PYTHON), "-c", "import mcp, httpx"], capture_output=True,
                       creationflags=_SEM_JANELA)
    return r.returncode == 0


def instalar(clientes: list[str]) -> bool:
    """Comeca em segundo plano; False se ja estiver instalando."""
    with _trava:
        if ESTADO["instalando"]:
            return False
        ESTADO.update(instalando=True, erro="", etapa="Starting")
    threading.Thread(target=_instalar, args=(clientes,), daemon=True).start()
    return True
