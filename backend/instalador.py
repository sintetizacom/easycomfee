"""Baixa os arquivos de um pacote do catalogo para a pasta de modelos.

Um download por vez, em segundo plano. Grava em <arquivo>.part e so renomeia
no fim, entao um arquivo pela metade nunca aparece para o ComfyUI; se o
download parar, a proxima tentativa continua de onde parou (cabecalho Range).
"""
import asyncio
import json
import pathlib
import struct
import time

import httpx

import chaves
import config
import pacotes

BLOCO = 4 * 1024 * 1024

ESTADO = {"pacote": None, "ativo": False, "arquivo": None, "baixado": 0,
          "total": 0, "feitos": 0, "quantos": 0, "velocidade": 0.0,
          "erro": None, "terminado_em": None}
_tarefa: asyncio.Task | None = None


# Pastas que so o segundo motor le, direto do disco (o no usa models_dir dele,
# nao a lista de pastas do ComfyUI): o Video Depth Anything.
PASTAS_SEGUNDO_MOTOR = {"videodepthanything"}


def destino(arq: dict) -> pathlib.Path:
    if arq["pasta"] in PASTAS_SEGUNDO_MOTOR and config.COMFY_DIR_FLUX3:
        return config.COMFY_DIR_FLUX3 / "models" / arq["pasta"] / arq["subpasta"] / arq["arquivo"]
    return config.MODELOS_DIR / arq["pasta"] / arq["subpasta"] / arq["arquivo"]


def _cabecalhos() -> dict:
    token = chaves.hf_token() or config.HF_TOKEN
    return {"Authorization": f"Bearer {token}"} if token else {}


class FaltaAceite(Exception):
    """O Hugging Face recusou: falta o token ou o aceite da licenca do repositorio."""


async def _baixar(cliente: httpx.AsyncClient, arq: dict, total_antes: int):
    final = destino(arq)
    parcial = final.with_name(final.name + ".part")
    final.parent.mkdir(parents=True, exist_ok=True)
    ja = parcial.stat().st_size if parcial.exists() else 0
    cab = _cabecalhos() | ({"Range": f"bytes={ja}-"} if ja else {})
    async with cliente.stream("GET", pacotes.url_download(arq), headers=cab) as r:
        if r.status_code == 200:
            ja = 0  # o servidor ignorou o Range: recomeca
        elif r.status_code in (401, 403):
            raise FaltaAceite(arq["repo"])
        elif r.status_code != 206:
            r.raise_for_status()
        inicio, base = time.monotonic(), ja
        with open(parcial, "ab" if ja else "wb") as f:
            async for pedaco in r.aiter_bytes(BLOCO):
                f.write(pedaco)
                ja += len(pedaco)
                ESTADO["baixado"] = total_antes + ja
                ESTADO["velocidade"] = (ja - base) / max(time.monotonic() - inicio, 1e-3)
    if ja != arq["tamanho"]:
        raise RuntimeError(f"{arq['arquivo']}: {ja} de {arq['tamanho']} bytes")
    parcial.replace(final)


def extrair_tensores(origem: pathlib.Path, final: pathlib.Path, prefixos: list[str]):
    """Copia de um .safetensors so os tensores cujos nomes comecam com um dos
    prefixos, com os metadados (o mapa de quantizacao filtrado aos que ficam).
    Le o formato direto (cabecalho JSON + bytes), sem torch nem safetensors."""
    with open(origem, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        cab = json.loads(f.read(n))
        base = 8 + n
        meta = cab.pop("__metadata__", {}) or {}
        ficam = sorted((k for k in cab if k.startswith(tuple(prefixos))),
                       key=lambda k: cab[k]["data_offsets"][0])
        if not ficam:
            raise RuntimeError(f"{origem.name}: nenhum tensor com os prefixos esperados")
        if "_quantization_metadata" in meta:
            q = json.loads(meta["_quantization_metadata"])
            q["layers"] = {k: v for k, v in q.get("layers", {}).items()
                           if any(t.startswith(k) for t in ficam)}
            meta["_quantization_metadata"] = json.dumps(q)
        novo, pos = {"__metadata__": meta}, 0
        for k in ficam:
            a, b = cab[k]["data_offsets"]
            novo[k] = {**cab[k], "data_offsets": [pos, pos + b - a]}
            pos += b - a
        texto = json.dumps(novo, separators=(",", ":")).encode()
        texto += b" " * (-len(texto) % 8)
        parcial = final.with_name(final.name + ".part")
        with open(parcial, "wb") as g:
            g.write(struct.pack("<Q", len(texto)) + texto)
            for k in ficam:
                a, b = cab[k]["data_offsets"]
                f.seek(base + a)
                resta = b - a
                while resta:
                    pedaco = f.read(min(BLOCO, resta))
                    g.write(pedaco)
                    resta -= len(pedaco)
    parcial.replace(final)


async def _instalar(lista: list[dict]):
    ESTADO.update(total=sum(a["tamanho"] for a in lista), baixado=0, feitos=0,
                  quantos=len(lista), erro=None, terminado_em=None, ativo=True,
                  repo_recusado=None)
    feito = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=120),
                                     follow_redirects=True, verify=config.ssl_sistema()) as c:
            for arq in lista:
                ESTADO["arquivo"] = arq["arquivo"]
                if arq.get("derivado"):
                    # Vem depois do arquivo de origem na lista (ver iniciar).
                    d = arq["derivado"]
                    await asyncio.to_thread(extrair_tensores, config.MODELOS_DIR / d["de"],
                                            destino(arq), d["prefixos"])
                else:
                    await _baixar(c, arq, feito)
                feito += arq["tamanho"]
                ESTADO["feitos"] += 1
    except FaltaAceite as e:
        repo = str(e)
        ESTADO["erro"] = (f"O Hugging Face pediu login para {repo}. Entre na sua conta, "
                          f"aceite a licenca em https://huggingface.co/{repo} e informe "
                          "o seu token de acesso abaixo." if not (chaves.hf_token() or config.HF_TOKEN)
                          else f"O token foi recusado para {repo}. Aceite a licenca em "
                          f"https://huggingface.co/{repo} com a mesma conta do token.")
        ESTADO["repo_recusado"] = repo
    except asyncio.CancelledError:
        ESTADO["erro"] = "Cancelado. O que ja baixou continua de onde parou."
    except Exception as e:
        ESTADO["erro"] = str(e)
    finally:
        ESTADO.update(ativo=False, arquivo=None, terminado_em=time.time())


async def iniciar(id_pacote: str, opcionais: bool) -> dict:
    global _tarefa
    if ESTADO["ativo"]:
        raise RuntimeError("Ja ha um download em andamento.")
    situacao = await pacotes.situacao()
    pacote = next((p for p in situacao["pacotes"] if p["id"] == id_pacote), None)
    if pacote is None:
        raise KeyError(id_pacote)
    # Sem o motor no ar, decide pelo disco.
    lista = [a for a in pacote["arquivos"]
             if (a.get("repo") or a.get("derivado"))  # sem origem: instalacao manual
             and (opcionais or not a["opcional"])
             and not (a["instalado"] or (a["instalado"] is None and destino(a).exists()))]
    # Os derivados por ultimo: precisam do arquivo de origem ja no disco.
    lista.sort(key=lambda a: bool(a.get("derivado")))
    ESTADO["pacote"] = id_pacote
    _tarefa = asyncio.create_task(_instalar(lista))
    return {"arquivos": len(lista), "bytes": sum(a["tamanho"] for a in lista)}


def cancelar():
    if _tarefa and not _tarefa.done():
        _tarefa.cancel()
