"""Versoes de um mesmo modelo (a chave "Version" nas abas Image e Music).

FLUX 3 Image Klein: o arquivo da versao base e o da destilada tem quase o mesmo tamanho e,
conforme quem baixou, ate o mesmo nome; a versao e reconhecida pelo TAMANHO exato (bytes do
repositorio oficial black-forest-labs/flux-3-image-klein-comfy).
- base: a que o app sempre usou (25 passos, CFG 3,5);
- rapida: a destilada, com os ajustes do template oficial (15 passos, CFG 1, er_sde).
O grafo e montado como sempre e depois ajustado aqui (aplicar), entao vale para gerar,
editar com referencias e o Orbit.

ACE-Step 1.5: Turbo (padrao) ou XL Turbo; ver musica.resolver(preferir_alt=...).
"""
import os
import pathlib
import time

import config

FLUX3 = {
    # bf16 primeiro, depois int8 (mais leve); vale a primeira que existir neste PC.
    "base": {"bytes": (11_076_957_072, 5_807_427_339), "rotulo": "Quality · base"},
    "rapida": {"bytes": (11_097_404_512, 5_827_874_779), "rotulo": "Fast · distilled",
               "steps": 15, "cfg": 1.0, "sampler": "er_sde"},
}
FLUX3_NOME_BASE = "flux3_image_klein_bf16.safetensors"  # o nome que os grafos pedem
_CACHE = {"quando": 0.0, "achados": {}}


def achar_flux3() -> dict[str, str]:
    """{versao: nome relativo em diffusion_models} das versoes do FLUX 3 neste PC."""
    if time.time() - _CACHE["quando"] < 60:
        return _CACHE["achados"]
    raiz = pathlib.Path(config.MODELOS_DIR) / "diffusion_models"
    por_tamanho = {b: (k, i) for k, v in FLUX3.items() for i, b in enumerate(v["bytes"])}
    melhor: dict[str, tuple[int, str]] = {}
    if raiz.is_dir():
        for p in raiz.rglob("*.safetensors"):
            try:
                achado = por_tamanho.get(p.stat().st_size)
            except OSError:
                continue
            if achado and (achado[0] not in melhor or achado[1] < melhor[achado[0]][0]):
                melhor[achado[0]] = (achado[1], str(p.relative_to(raiz)).replace("/", os.sep))
    achados = {k: v[1] for k, v in melhor.items()}
    _CACHE.update(quando=time.time(), achados=achados)
    return achados


def disponiveis() -> dict:
    achados = achar_flux3()
    return {"flux3": [{"id": k, "rotulo": v["rotulo"], "instalada": k in achados} for k, v in FLUX3.items()]}


def aplicar(g: dict, pedido) -> None:
    """Troca o FLUX 3 do grafo pela versao pedida (ou pela que existir) e acerta os ajustes."""
    unets = [n for n in g.values() if n.get("class_type") == "UNETLoader"
             and str(n["inputs"].get("unet_name", "")).replace("\\", "/").split("/")[-1] == FLUX3_NOME_BASE]
    if not unets:
        return
    achados = achar_flux3()
    pedida = getattr(pedido, "variante", "") or "base"
    versao = pedida if pedida in achados else ("base" if "base" in achados else next(iter(achados), None))
    if versao is None:
        return  # nenhuma reconhecida pelo tamanho: o grafo fica como esta
    for n in unets:
        n["inputs"]["unet_name"] = achados[versao]
    ajustes = FLUX3[versao]
    if "steps" not in ajustes:
        return
    for n in g.values():
        e = n.get("inputs", {})
        if "steps" in e and isinstance(e["steps"], int):
            e["steps"] = ajustes["steps"]
        if "cfg" in e and isinstance(e["cfg"], (int, float)):
            e["cfg"] = ajustes["cfg"]
        if "sampler_name" in e and isinstance(e["sampler_name"], str):
            e["sampler_name"] = ajustes["sampler"]
