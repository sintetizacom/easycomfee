"""Versoes de um mesmo modelo, pensadas para quem nao sabe o que e VRAM (02/11/2026).

Na tela ha uma chave so, igual em todos os modelos: "Faster" / "Best quality". O app
escolhe sozinho, pela maquina confirmada em Config Models (maquina.salvo):
- a versao padrao de cada modelo;
- o arquivo mais leve (int8) ou o completo (bf16) do FLUX 3, quando os dois existem;
- e esconde a versao que nao cabe na placa (o ACE-Step XL pede ~12 GB).

FLUX 3 Image Klein: base e destilada tem quase o mesmo tamanho e, conforme quem baixou,
ate o mesmo nome; a versao e reconhecida pelo TAMANHO exato (repositorio oficial
black-forest-labs/flux-3-image-klein-comfy). O grafo e montado como sempre e ajustado
aqui (aplicar): vale para gerar, editar com referencias e o Orbit.
- base ("Best quality"): 25 passos, CFG 3,5;
- rapida ("Faster"): a destilada, com os ajustes do template oficial (15 passos, CFG 1, er_sde).
ACE-Step 1.5: turbo ("Faster") ou xl ("Best quality"); ver musica.resolver(preferir_alt=...).
"""
import os
import pathlib
import time

import config

FLUX3 = {
    # (bf16, int8): o app prefere um ou outro pela placa (preferir_leve).
    "base": {"bytes": (11_076_957_072, 5_807_427_339)},
    "rapida": {"bytes": (11_097_404_512, 5_827_874_779), "steps": 15, "cfg": 1.0, "sampler": "er_sde"},
}
FLUX3_NOME_BASE = "flux3_image_klein_bf16.safetensors"  # o nome que os grafos pedem
ROTULOS = {"flux3": {"rapida": "Faster", "base": "Best quality"},
           "ace-step15": {"turbo": "Faster", "xl": "Best quality"}}
ACE_XL_VRAM = 12  # medido em 02/11/2026: pico de 12,2 GB numa placa de 16 GB
LEVE_ABAIXO_DE = 14  # placa com menos que isso: o arquivo int8 do FLUX 3, se existir
_CACHE = {"quando": 0.0, "achados": {}, "leve": None}


def vram() -> float | None:
    """A memoria da placa confirmada em Config Models (None: ainda nao confirmada)."""
    try:
        import maquina
        v = (maquina.salvo() or {}).get("vram_gb")
        return float(v) if v else None
    except Exception:
        return None


def preferir_leve() -> bool:
    v = vram()
    return v is not None and v < LEVE_ABAIXO_DE


def achar_flux3() -> dict[str, str]:
    """{versao: nome relativo em diffusion_models} das versoes do FLUX 3 neste PC."""
    leve = preferir_leve()
    if time.time() - _CACHE["quando"] < 60 and _CACHE["leve"] == leve:
        return _CACHE["achados"]
    raiz = pathlib.Path(config.MODELOS_DIR) / "diffusion_models"
    ordem = (1, 0) if leve else (0, 1)  # qual arquivo vence quando ha bf16 e int8
    por_tamanho = {b: (k, ordem.index(i)) for k, v in FLUX3.items() for i, b in enumerate(v["bytes"])}
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
    _CACHE.update(quando=time.time(), achados=achados, leve=leve)
    return achados


def padrao(modelo: str, instaladas: set[str]) -> str:
    """A versao que o app usa quando a pessoa nao escolheu: a melhor que cabe na placa."""
    if modelo == "ace-step15":
        v = vram()
        return "xl" if "xl" in instaladas and (v is None or v >= ACE_XL_VRAM + 2) else "turbo"
    return "base" if "base" in instaladas or not instaladas else "rapida"


def _lista(modelo: str, instaladas: set[str], cabe=lambda _id: True) -> dict:
    itens = [{"id": i, "rotulo": r, "instalada": i in instaladas and cabe(i)} for i, r in ROTULOS[modelo].items()]
    return {"versoes": itens, "padrao": padrao(modelo, {i["id"] for i in itens if i["instalada"]})}


def disponiveis(ace_turbo: bool = False, ace_xl: bool = False) -> dict:
    v = vram()
    r = {"flux3": _lista("flux3", set(achar_flux3()))}
    ace = {k for k, ok in (("turbo", ace_turbo), ("xl", ace_xl)) if ok}
    r["ace-step15"] = _lista("ace-step15", ace, cabe=lambda i: i != "xl" or v is None or v >= ACE_XL_VRAM)
    return r


def aplicar(g: dict, pedido) -> None:
    """Troca o FLUX 3 do grafo pela versao pedida (ou pela padrao) e acerta os ajustes."""
    unets = [n for n in g.values() if n.get("class_type") == "UNETLoader"
             and str(n["inputs"].get("unet_name", "")).replace("\\", "/").split("/")[-1] == FLUX3_NOME_BASE]
    if not unets:
        return
    achados = achar_flux3()
    pedida = getattr(pedido, "variante", "") or padrao("flux3", set(achados))
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
