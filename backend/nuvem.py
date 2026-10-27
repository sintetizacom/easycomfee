"""O que so a Comfy Cloud precisa, antes do envio e depois do fim.

Antes: conferir se cada no e cada arquivo de modelo do grafo existem la (sem
isso a nuvem recusaria o envio, ou pior, cobraria e falharia), trocar o nome
do modelo pelo que a nuvem usa (la os arquivos ficam soltos, sem a nossa
subpasta LTX/2.5/) e subir as entradas que o app gravou na pasta input.

Depois: baixar as saidas para a pasta output, com um prefixo proprio, para o
resto do app ler do disco como sempre e sem sobrescrever um arquivo local.
"""
import pathlib
import time

import httpx

import chaves
import config

BASE = "https://cloud.comfy.org/api"
EXTENSOES_MODELO = (".safetensors", ".pth", ".onnx", ".ckpt", ".gguf", ".pt", ".bin", ".sft")

_cache = {"em": 0.0, "nos": set(), "modelos": {}}
_enviados: dict[tuple[str, float], str] = {}


class IndisponivelNaNuvem(Exception):
    """O grafo usa algo que a Comfy Cloud nao tem."""


def _cliente(timeout: float = 120) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, timeout=timeout, follow_redirects=True,
                             headers={"X-API-Key": chaves.chave() or ""},
                             verify=config.ssl_sistema())


def _opcoes(info: dict) -> set[str]:
    nomes = set()
    for no in info.values():
        for grupo in ("required", "optional"):
            for spec in no.get("input", {}).get(grupo, {}).values():
                if isinstance(spec, list) and spec and isinstance(spec[0], list):
                    nomes.update(x for x in spec[0] if isinstance(x, str))
                elif (isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict)
                      and isinstance(spec[1].get("options"), list)):
                    nomes.update(x for x in spec[1]["options"] if isinstance(x, str))
    return nomes


def _arquivo(nome: str) -> str:
    return nome.replace("\\", "/").split("/")[-1]


async def capacidades(forcar: bool = False) -> tuple[set[str], dict[str, str]]:
    """Nos e modelos da nuvem: (nomes de no, arquivo -> nome que a nuvem usa).
    A lista tem ~10 MB; guarda por uma hora."""
    if forcar or time.time() - _cache["em"] > 3600 or not _cache["nos"]:
        async with _cliente() as c:
            r = await c.get("/object_info")
            r.raise_for_status()
            info = r.json()
        _cache.update(em=time.time(), nos=set(info),
                      modelos={_arquivo(n): n for n in _opcoes(info)
                               if n.lower().endswith(EXTENSOES_MODELO)})
    return _cache["nos"], _cache["modelos"]


# Arquivos que so existem aqui por um contorno local, e o equivalente que a
# nuvem tem. O "_so_texto" e um recorte do checkpoint do LTX 2.3 feito porque
# ler o checkpoint inteiro no codificador derrubava o motor DESTA maquina; a
# nuvem tem o checkpoint original.
# Nome daqui -> nome na nuvem. O Creative Lab do LTX 2.5 nao esta la, mas as
# mesmas IC-LoRAs do 2.3 estao (e o exemplo oficial do 2.5 ja usa as do 2.3).
SUBSTITUTOS = {"ltx-2.3-22b-dev-fp8_so_texto.safetensors": "ltx-2.3-22b-dev-fp8.safetensors",
               **{f"ltx-2.5-22b-ic-lora-{n}.safetensors": f"ltx-2.3-22b-ic-lora-{n}.safetensors"
                  for n in ("day-to-night-0.9", "clean-plate-1.0", "water-simulation-0.9",
                            "deblur-0.9", "decompression-0.9", "colorization-0.9")}}


def _na_nuvem(nome: str) -> str:
    a = _arquivo(nome)
    return SUBSTITUTOS.get(a, a)


def conferir(grafo: dict, nos: set[str], modelos: dict[str, str]) -> list[str]:
    """O que falta na nuvem para este grafo (vazio = roda la)."""
    faltam = []
    for no in grafo.values():
        if no["class_type"] not in nos:
            faltam.append(f"no {no['class_type']}")
        for v in no["inputs"].values():
            if isinstance(v, str) and v.lower().endswith(EXTENSOES_MODELO) and _na_nuvem(v) not in modelos:
                faltam.append(f"modelo {_na_nuvem(v)}")
    return sorted(set(faltam))


async def _subir(c: httpx.AsyncClient, caminho: pathlib.Path) -> str:
    chave = (str(caminho), caminho.stat().st_mtime)
    if chave not in _enviados:
        with open(caminho, "rb") as f:
            r = await c.post("/upload/image", files={"image": (caminho.name, f)},
                             data={"overwrite": "true", "type": "input"})
        r.raise_for_status()
        corpo = r.json()
        _enviados[chave] = f"{corpo['subfolder']}/{corpo['name']}" if corpo.get("subfolder") else corpo["name"]
    return _enviados[chave]


async def preparar(grafo: dict) -> dict:
    """Copia do grafo pronta para a nuvem, ou IndisponivelNaNuvem."""
    nos, modelos = await capacidades()
    faltam = conferir(grafo, nos, modelos)
    if faltam:
        raise IndisponivelNaNuvem("Este modo ainda não roda na Comfy Cloud. Falta: " + ", ".join(faltam[:6]))
    pronto = {}
    async with _cliente(300) as c:
        for nid, no in grafo.items():
            entradas = {}
            for k, v in no["inputs"].items():
                if isinstance(v, str) and v.lower().endswith(EXTENSOES_MODELO):
                    v = modelos[_na_nuvem(v)]
                elif isinstance(v, str) and v and len(v) < 260:
                    local = config.COMFY_ENTRADA / v
                    if local.is_file():
                        v = await _subir(c, local)
                entradas[k] = v
            pronto[nid] = {**no, "inputs": entradas}
    return pronto


async def trazer_saidas(prompt_id: str, saidas: dict) -> dict:
    """Baixa cada arquivo de saida para COMFY_SAIDA e devolve as saidas com os
    nomes locais. Prefixo "nuvem_<id>_" para nunca sobrescrever um arquivo
    gerado localmente com o mesmo nome."""
    novas = {}
    async with _cliente(600) as c:
        for nid, saida in saidas.items():
            nova = dict(saida)
            for chave, itens in saida.items():
                if not isinstance(itens, list) or not itens or not isinstance(itens[0], dict) or "filename" not in itens[0]:
                    continue
                lista = []
                for it in itens:
                    sub = it.get("subfolder", "")
                    nome = f"nuvem_{prompt_id[:8]}_{it['filename']}"
                    destino = config.COMFY_SAIDA / sub / nome
                    if it.get("type", "output") == "output" and not destino.exists():
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        r = await c.get("/view", params={"filename": it["filename"], "subfolder": sub,
                                                         "type": it.get("type", "output")})
                        r.raise_for_status()
                        parcial = destino.with_name(destino.name + ".part")
                        parcial.write_bytes(r.content)
                        parcial.replace(destino)
                    lista.append({**it, "filename": nome} if it.get("type", "output") == "output" else it)
                nova[chave] = lista
            novas[nid] = nova
    return novas


_compat = {"em": 0.0, "dados": None}


async def compatibilidade() -> dict:
    """O que roda na nuvem, montando o grafo real de cada modelo e efeito e
    conferindo contra a lista da nuvem. Nada e enviado nem cobrado."""
    import presets
    import workflows
    nos, modelos = await capacidades()
    if _compat["dados"] and _compat["em"] >= _cache["em"]:
        return _compat["dados"]

    def ok(montar) -> bool:
        try:
            g = montar()
        except Exception:
            return False
        g = g[0] if isinstance(g, tuple) else g
        return not conferir(g, nos, modelos)

    dados = {
        "imagem": {m: ok(lambda m=m: workflows.gerar_simples(m, "x", "", 1, 1024, 1024))
                   for m in presets.SIMPLE},
        "efeitos_video": {k: bool(e.get("lora")) and ok(
                              lambda e=e: workflows.em_base_ltx23(
                                  workflows.transformar_video("x.mp4", e["lora"], "x", 49, 544, 960)))
                          for k, e in presets.VIDEO_TRANSFORMAR["efeitos"].items()},
        "video": {"ltx": ok(lambda: workflows.gerar_video_ltx("x", 1, 768, 432, 2)),
                  "ltx_flf": ok(lambda: workflows.gerar_video_ltx_flf("x", 1, "a.png", "b.png"))},
    }
    _compat.update(em=_cache["em"], dados=dados)
    return dados
