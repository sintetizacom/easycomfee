"""Achar modelos que a pessoa ja tem (Config Models > Scan for models I already have).

Varre uma pasta, compara cada arquivo com o catalogo pelo TAMANHO exato em bytes (o mesmo
arquivo, mesmo renomeado ou em outra subpasta) e pelo nome, e cria, na pasta de modelos
do ComfyUI, um vinculo com o nome que o app espera:
- hardlink quando esta no mesmo disco (nao ocupa espaco, funciona sempre);
- link simbolico em outro disco (o Windows pode exigir o Modo de desenvolvedor).
Versoes diferentes (fp8 x bf16, GGUF) tem outro tamanho e nao sao reconhecidas sozinhas:
voltam em "nao_reconhecidos" para tratar caso a caso.
"""
import os
import pathlib

import instalador
import pacotes

EXT = (".safetensors", ".ckpt", ".pth", ".gguf", ".onnx", ".bin", ".pt")
PULAR = {"windows", "$recycle.bin", "program files", "program files (x86)", "programdata",
         "node_modules", ".git", ".venv", "venv", "__pycache__", "site-packages"}
MINIMO = 20_000_000  # abaixo de ~20 MB nao e peso de modelo que o catalogo tenha


def _arquivos(raiz: pathlib.Path):
    pilha = [raiz]
    while pilha:
        pasta = pilha.pop()
        try:
            with os.scandir(pasta) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name.lower() not in PULAR and not e.name.startswith("."):
                                pilha.append(pathlib.Path(e.path))
                        elif e.name.lower().endswith(EXT):
                            tam = e.stat().st_size
                            if tam >= MINIMO:
                                yield pathlib.Path(e.path), tam
                    except OSError:
                        continue
        except OSError:
            continue


def _vincular(origem: pathlib.Path, alvo: pathlib.Path) -> str:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(origem, alvo)
        return "hardlink"
    except OSError:
        os.symlink(origem, alvo)  # outro disco; pode exigir o Modo de desenvolvedor
        return "symlink"


def escanear(pasta: str) -> dict:
    raiz = pathlib.Path(pasta)
    if not raiz.is_dir():
        raise ValueError("That folder does not exist.")
    catalogo = [(p, a) for p in pacotes.carregar() for a in p["arquivos"] if a.get("tamanho")]
    por_tamanho: dict[int, list] = {}
    for p, a in catalogo:
        por_tamanho.setdefault(a["tamanho"], []).append((p, a))

    vinculados, ja_tinha, falhas, nao_reconhecidos = [], [], [], []
    vistos = set()
    for arq, tam in _arquivos(raiz):
        casos = por_tamanho.get(tam, [])
        if not casos:
            nao_reconhecidos.append({"arquivo": arq.name, "gb": round(tam / 1e9, 2)})
            continue
        for p, a in casos:
            chave = (a["pasta"], a["subpasta"], a["arquivo"])
            if chave in vistos:
                continue
            vistos.add(chave)
            alvo = instalador.destino(a)
            item = {"pacote": p["nome"], "arquivo": a["arquivo"], "de": str(arq)}
            try:
                if alvo.exists() and alvo.stat().st_size == tam:
                    ja_tinha.append(item)
                    continue
                if alvo.exists() or alvo.is_symlink():
                    falhas.append(item | {"motivo": "a different file with that name is already there"})
                    continue
                if alvo.resolve() == arq.resolve():
                    ja_tinha.append(item)
                    continue
                vinculados.append(item | {"modo": _vincular(arq, alvo)})
            except OSError as e:
                falhas.append(item | {"motivo": ("Windows refused a link to another drive. Turn on Developer Mode, "
                                                 "or move the file to the same drive as ComfyUI.")
                                      if getattr(e, "winerror", None) == 1314 else str(e)[:200]})
    # O mapa de nomes do app (pacotes.mapa_local) relê a lista do ComfyUI na proxima consulta.
    pacotes._MAPA["quando"] = 0.0
    nao_reconhecidos.sort(key=lambda x: -x["gb"])
    return {"vinculados": vinculados, "ja_tinha": ja_tinha, "falhas": falhas,
            "nao_reconhecidos": nao_reconhecidos[:60]}
