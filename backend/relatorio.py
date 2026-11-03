"""Log do app e o relatorio para suporte (um .zip que a pessoa anexa a uma issue no GitHub).

- logs/easycomfee.log: avisos e erros do servidor, em arquivos que giram (no maximo ~5 MB).
- logs/install.log: o que o install.bat mostrou (ver install.bat e detectar_comfy.py).
- O relatorio junta os dois logs, um resumo do PC e as ultimas geracoes com erro.

Nada sai com segredo: a chave da Comfy Cloud e o token do Hugging Face nunca entram, e o
que parecer chave (sk-..., hf_..., Bearer ...) e o nome de usuario do Windows sao trocados.
"""
import io
import json
import logging
import logging.handlers
import os
import pathlib
import platform
import re
import subprocess
import sys
import time
import zipfile

import config

PASTA = config.RAIZ / "logs"
LOG_APP = PASTA / "easycomfee.log"
LOG_INSTALACAO = PASTA / "install.log"
ISSUES = "https://github.com/sintetizacom/easycomfee/issues/new"
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ligar_log() -> None:
    """Grava avisos e erros do servidor (e do uvicorn) em logs/easycomfee.log."""
    PASTA.mkdir(exist_ok=True)
    h = logging.handlers.RotatingFileHandler(LOG_APP, maxBytes=1_000_000, backupCount=4, encoding="utf-8")
    h.setLevel(logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for nome in ("", "uvicorn", "uvicorn.error", "easycomfee"):
        lg = logging.getLogger(nome)
        if not any(isinstance(x, logging.handlers.RotatingFileHandler) for x in lg.handlers):
            lg.addHandler(h)
        if lg.level == logging.NOTSET or lg.level > logging.WARNING:
            lg.setLevel(logging.WARNING)


def log() -> logging.Logger:
    return logging.getLogger("easycomfee")


_SEGREDOS = [
    (re.compile(r"\b(sk|ck|comfyui)-[A-Za-z0-9_\-]{12,}"), "<key>"),
    (re.compile(r"\bhf_[A-Za-z0-9]{12,}"), "<hf-token>"),
    (re.compile(r"(?i)(bearer|authorization|api[_-]?key|token)([\"':= ]+)[A-Za-z0-9_\-\.]{12,}"), r"\1\2<hidden>"),
]


def limpar(texto: str) -> str:
    """Tira chaves e o nome de usuario do Windows de um texto."""
    for padrao, troca in _SEGREDOS:
        texto = padrao.sub(troca, texto)
    casa = str(pathlib.Path.home())
    usuario = os.environ.get("USERNAME") or pathlib.Path.home().name
    for forma in {casa, casa.replace("\\", "/"), casa.replace("\\", "\\\\")}:
        texto = texto.replace(forma, "<home>")
    if usuario and len(usuario) > 2:
        texto = re.sub(rf"(?i)\b{re.escape(usuario)}\b", "<user>", texto)
    return texto


def _cmd(args: list[str]) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15, creationflags=_SEM_JANELA)
        return (r.stdout or r.stderr).strip()
    except Exception as e:  # programa ausente ou travado: o relatorio sai mesmo assim
        return f"({type(e).__name__})"


def resumo(estado_motor: dict, stats: dict | None) -> str:
    cfg = {}
    try:
        cfg = json.loads((config.RAIZ / "config.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        pass
    # So o que ajuda a diagnosticar; chaves e tokens nunca.
    seguro = {k: cfg.get(k) for k in ("comfy_dir", "comfy_url", "comfy_url_flux3", "comfy_iniciar",
                                       "modelos_dir", "app_porta") if k in cfg}
    linhas = [
        f"Report created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Windows: {platform.platform()}",
        f"EasyComfee Python: {sys.version.split()[0]}",
        f"Engine mode: {estado_motor.get('modo')}  (comfy responding: {estado_motor.get('respondendo')})",
        f"config.json (safe fields): {json.dumps(seguro, ensure_ascii=False)}",
        "GPU (nvidia-smi): " + _cmd(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
                                     "--format=csv,noheader"]),
        "Node: " + _cmd(["node", "--version"]),
        "ComfyUI system_stats: " + (json.dumps(stats, ensure_ascii=False)[:3000] if stats else "(not reachable)"),
    ]
    return limpar("\n".join(linhas))


def montar_zip(estado_motor: dict, stats: dict | None, erros: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.txt", resumo(estado_motor, stats))
        z.writestr("recent-errors.json", limpar(json.dumps(erros, ensure_ascii=False, indent=1)))
        arquivos = [LOG_INSTALACAO, LOG_APP] + sorted(PASTA.glob("easycomfee.log.*"))
        for arq in arquivos:
            if arq.is_file():
                z.writestr(f"logs/{arq.name}", limpar(arq.read_text(encoding="utf-8", errors="replace")[-2_000_000:]))
        z.writestr("README.txt", "Attach this file to a new issue at " + ISSUES + "\n"
                   "It has the setup and app logs, a summary of the PC and the last errors.\n"
                   "Keys, tokens and your Windows user name were removed.\n")
    return buf.getvalue()
