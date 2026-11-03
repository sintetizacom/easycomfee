"""A pasta onde a pessoa quer os resultados (Config Models > Where results are saved).

Quem grava o arquivo e o ComfyUI (na pasta "output" dele); o EasyComfee copia cada resultado
para esta pasta. Padrao: <EasyComfee>/output. Fica em config.json ("pasta_resultados").
"""
import json
import os
import pathlib
import subprocess

import config

ARQUIVO = config.RAIZ / "config.json"


def _cfg() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def escolhida() -> bool:
    """A pessoa escolheu uma pasta (entao a copia vale para qualquer instalacao)."""
    return bool(_cfg().get("pasta_resultados"))


def atual() -> pathlib.Path:
    return pathlib.Path(_cfg().get("pasta_resultados") or config.RAIZ / "output")


def salvar(pasta: str) -> pathlib.Path:
    p = pathlib.Path(pasta).expanduser()
    if not p.is_absolute():
        raise ValueError("Choose a full folder path.")
    p.mkdir(parents=True, exist_ok=True)
    dados = _cfg()
    dados["pasta_resultados"] = p.as_posix()
    ARQUIVO.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def escolher() -> str | None:
    """Abre a janela de pasta do Windows (o servidor roda no mesmo PC). None = cancelou."""
    import tkinter
    from tkinter import filedialog
    raiz = tkinter.Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)
    try:
        pasta = filedialog.askdirectory(parent=raiz, initialdir=str(atual()),
                                        title="Where should EasyComfee save your results?")
    finally:
        raiz.destroy()
    return pasta or None


def abrir() -> None:
    p = atual()
    p.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(p)  # Windows Explorer
    else:
        subprocess.Popen(["xdg-open", str(p)])
