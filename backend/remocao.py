"""Botao Remove do Config Models: tira do disco os arquivos de um pacote.

So arquivos que nenhum OUTRO pacote instalado usa (o VAE e o codificador de
texto do LTX, por exemplo, estao em mais de um pacote) e so no lugar onde o
instalador os grava (instalador.destino). Vao para a Lixeira do Windows, nunca
apagados de vez: a pasta de modelos e a do ComfyUI da pessoa, que pode usar o
mesmo arquivo em outros workflows e querer de volta.
"""
import ctypes
import os
import pathlib
import shutil

import config
import instalador
import pacotes


def _instalados(p: dict) -> list[pathlib.Path]:
    return [d for a in p["arquivos"] if (d := instalador.destino(a)).is_file()]


def plano(id_pacote: str) -> dict:
    """O que sai, o que fica (e por que) e quanto espaco volta. Nao mexe em nada."""
    todos = pacotes.carregar()
    alvo = next((p for p in todos if p["id"] == id_pacote), None)
    if alvo is None:
        raise KeyError(id_pacote)
    # Arquivo de outro pacote que continua instalado fica. "Instalado" = tem no disco
    # algum arquivo PROPRIO (nao dividido com o alvo); senao um pacote nunca baixado,
    # que so "tem" o VAE em comum, seguraria a remocao a toa.
    do_alvo = {instalador.destino(a) for a in alvo["arquivos"]}
    em_uso: dict[pathlib.Path, list[str]] = {}
    for p in todos:
        if p["id"] == id_pacote or not (set(_instalados(p)) - do_alvo):
            continue
        for a in p["arquivos"]:
            em_uso.setdefault(instalador.destino(a), []).append(p["nome"])
    sai, fica = [], []
    for a in alvo["arquivos"]:
        d = instalador.destino(a)
        if not d.is_file():
            continue
        item = {"rotulo": a["rotulo"], "arquivo": a["arquivo"], "tamanho": d.stat().st_size}
        (fica if d in em_uso else sai).append(item | ({"usado_por": em_uso[d]} if d in em_uso else {}))
    return {"pacote": alvo["nome"], "sai": sai, "fica": fica,
            "libera": sum(i["tamanho"] for i in sai)}


def _para_lixeira(caminho: pathlib.Path) -> None:
    """Lixeira do Windows (SHFileOperation com FOF_ALLOWUNDO). Fora do Windows,
    move para models/_removed, que a pessoa apaga quando quiser."""
    if os.name == "nt":
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                        ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                        ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]
        # FO_DELETE=3; FOF_ALLOWUNDO|FOF_NOCONFIRMATION|FOF_SILENT|FOF_NOERRORUI = 0x40|0x10|0x4|0x400
        op = SHFILEOPSTRUCTW(None, 3, str(caminho) + "\0", None, 0x454, 0, None, None)
        if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) or caminho.exists():
            raise RuntimeError(f"Could not move {caminho.name} to the Recycle Bin.")
        return
    destino = config.MODELOS_DIR / "_removed" / caminho.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(caminho), destino)


def remover(id_pacote: str) -> dict:
    if instalador.ESTADO["ativo"]:
        raise RuntimeError("Wait for the current download to finish.")
    p = plano(id_pacote)
    todos = {a["arquivo"]: a for x in pacotes.carregar() if x["id"] == id_pacote for a in x["arquivos"]}
    for item in p["sai"]:
        _para_lixeira(instalador.destino(todos[item["arquivo"]]))
    return p
