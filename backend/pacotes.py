"""Catalogo de pacotes de modelos (catalogo/pacotes.json) e o que ja esta instalado.

Cada pacote lista os arquivos de que um modo precisa, com a origem no Hugging
Face e a pasta do ComfyUI onde ficam. A conferencia pergunta ao proprio
ComfyUI (GET /models/<pasta>), que ja enxerga o extra_model_paths.yaml.
"""
import json

import httpx

import comfy
import config

CATALOGO = config.RAIZ / "catalogo" / "pacotes.json"


def carregar() -> list[dict]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))["pacotes"]


def relativo(arq: dict) -> str:
    """O nome que os grafos usam: subpasta/arquivo, dentro da pasta do tipo."""
    return f"{arq['subpasta']}/{arq['arquivo']}" if arq["subpasta"] else arq["arquivo"]


def url_download(arq: dict) -> str | None:
    if not arq.get("repo"):
        return None  # sem origem publica: so instalacao manual
    return f"https://huggingface.co/{arq['repo']}/resolve/main/{arq['caminho']}"


def _norm(nome: str) -> str:
    return nome.replace("\\", "/").lower()


def _mesmo_tamanho(pasta: str, nome_comfy: str, esperado: int) -> bool:
    """Confere o tamanho quando o arquivo esta na pasta de modelos que conhecemos.
    Numa pasta extra (extra_model_paths.yaml) nao da para medir: vale o nome."""
    d = config.MODELOS_DIR / pasta / nome_comfy.replace("\\", "/")
    return not d.is_file() or not esperado or d.stat().st_size == esperado


def achar_em_outro_lugar(arq: dict, nomes_comfy: list[str]) -> str | None:
    """Quem ja usa ComfyUI pode ter o arquivo em outra subpasta (ex.: ltx.safetensors
    na raiz, e nao em LTX/2.5/). Mesmo nome e mesmo tamanho: usa o dele, sem baixar
    de novo. Devolve o nome como o ComfyUI lista (o que os grafos precisam pedir)."""
    alvo = arq["arquivo"].lower()
    for n in nomes_comfy:
        if _norm(n).rsplit("/", 1)[-1] == alvo and _mesmo_tamanho(arq["pasta"], n, arq.get("tamanho", 0)):
            return n
    return None


_MAPA = {"quando": 0.0, "mapa": {}}


async def mapa_local() -> dict[str, str]:
    """Nome que os grafos pedem (normalizado) -> nome real no ComfyUI da pessoa,
    so para arquivos do catalogo que estao em outra subpasta. Cache de 60 s."""
    import time
    import instalador
    if time.time() - _MAPA["quando"] < 60:
        return _MAPA["mapa"]
    arquivos = [a for p in carregar() for a in p["arquivos"] if a["pasta"] not in instalador.PASTAS_SEGUNDO_MOTOR]
    listas = await _listar_pastas_cruas({a["pasta"] for a in arquivos}) or {}
    mapa = {}
    for a in arquivos:
        nomes = listas.get(a["pasta"], [])
        if _norm(relativo(a)) in {_norm(n) for n in nomes}:
            continue
        achado = achar_em_outro_lugar(a, nomes)
        if achado:
            mapa[_norm(relativo(a))] = achado
    _MAPA.update(quando=time.time(), mapa=mapa)
    return mapa


async def ajustar_grafo(grafo: dict) -> dict:
    """Troca, nos nos do grafo, nomes de modelo do catalogo pelo lugar onde o
    arquivo esta de fato no ComfyUI da pessoa (ver achar_em_outro_lugar)."""
    mapa = await mapa_local()
    if not mapa:
        return grafo
    for no in grafo.values():
        for k, v in no.get("inputs", {}).items():
            if isinstance(v, str) and _norm(v) in mapa:
                no["inputs"][k] = mapa[_norm(v)]
    return grafo


async def _listar_pastas_cruas(pastas: set[str]) -> dict[str, list[str]] | None:
    """Como o ComfyUI lista (com barra invertida no Windows), sem normalizar."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            saida = {}
            for pasta in pastas:
                r = await c.get(f"{comfy.BASE_PRINCIPAL}/models/{pasta}")
                r.raise_for_status()
                saida[pasta] = r.json()
            return saida
    except Exception:
        return None


async def _listar_pastas(pastas: set[str]) -> dict[str, set[str]] | None:
    """Caminhos (subpasta/arquivo, com barra normal) que o motor enxerga em cada pasta.

    O caminho inteiro importa: os grafos pedem "LTX/2.5/arquivo", e um arquivo
    certo na subpasta errada faria a geracao ser recusada pelo ComfyUI."""
    vistos = {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            for pasta in pastas:
                r = await c.get(f"{comfy.BASE_PRINCIPAL}/models/{pasta}")
                r.raise_for_status()
                vistos[pasta] = {n.replace("\\", "/") for n in r.json()}
    except Exception:
        return None
    return vistos


async def situacao() -> dict:
    import maquina
    perfil = maquina.salvo()
    disco = maquina._disco_livre()
    pacotes = carregar()
    import instalador
    especiais = instalador.PASTAS_SEGUNDO_MOTOR
    vistos = await _listar_pastas({a["pasta"] for p in pacotes for a in p["arquivos"]} - especiais)
    saida = []
    for p in pacotes:
        arquivos = []
        for a in p["arquivos"]:
            if a["pasta"] in especiais:
                # O motor nao lista esta pasta: confere o arquivo no disco.
                instalado = instalador.destino(a).exists()
            else:
                instalado = None if vistos is None else relativo(a) in vistos.get(a["pasta"], set())
            encontrado = None
            if instalado is False and vistos is not None and a["pasta"] not in especiais:
                encontrado = achar_em_outro_lugar(a, sorted(vistos.get(a["pasta"], set())))
                instalado = bool(encontrado)
            arquivos.append(a | {"instalado": instalado, "url": url_download(a),
                                 **({"encontrado": encontrado.replace("\\", "/")} if encontrado else {})})
        obrigatorios = [a for a in arquivos if not a["opcional"]]
        # Um arquivo pode estar em varios pacotes (o VAE do FLUX 2 esta em tres);
        # o que falta conta uma vez so por pacote, e o instalador nao baixa duas vezes.
        faltando = [a for a in arquivos if a["instalado"] is False]
        import instalador_nos
        nos = [n for n in instalador_nos.situacao() if "base" in n["pacotes"] or p["id"] in n["pacotes"]]
        saida.append({k: v for k, v in p.items() if k != "arquivos"} | {
            "nos": [{"nome": n["nome"], "instalado": n["instalado"]} for n in nos],
            "arquivos": arquivos,
            "pronto": None if vistos is None else all(a["instalado"] for a in obrigatorios),
            "tamanho_total": sum(a["tamanho"] for a in arquivos),
            "tamanho_faltando": sum(a["tamanho"] for a in faltando),
            "nesta_maquina": maquina.avaliar(p["requisitos"], perfil, disco,
                                             sum(a["tamanho"] for a in faltando) / 1024 ** 3),
            "manual": [a["rotulo"] for a in arquivos if a.get("sem_origem") and a["instalado"] is not True],
        })
    return {"motor_respondendo": vistos is not None, "pacotes": saida, "maquina": perfil}
