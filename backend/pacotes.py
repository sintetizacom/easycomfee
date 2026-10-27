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
            arquivos.append(a | {"instalado": instalado, "url": url_download(a)})
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
