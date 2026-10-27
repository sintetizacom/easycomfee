"""Custo estimado de um grafo antes de enviar.

Cada no de API da Comfy traz no /object_info um `price_badge`: uma expressao
JSONata que o proprio ComfyUI usa para mostrar o preco no no, a partir dos
valores dos campos (widgets). Avaliar a MESMA expressao aqui da o mesmo numero
que a Comfy mostra, e acompanha sozinho as mudancas de preco dela.

Modelo aberto rodando na Comfy Cloud nao tem badge: cobra por segundo de GPU.
Ai a estimativa e o tempo previsto vezes a tarifa medida (presets).
"""
import time

import httpx
import jsonata

import comfy

_cache = {"em": 0.0, "base": None, "badges": {}}
_compiladas: dict[str, jsonata.Jsonata] = {}

# Tarifa da Comfy Cloud por segundo de GPU (medida; ver VIDEO_MINIMAX_NUVEM).
USD_POR_SEGUNDO_GPU = 0.001295


async def _badges() -> dict[str, dict]:
    base = comfy._base()
    if base != _cache["base"] or time.time() - _cache["em"] > 3600:
        async with comfy._cliente(60) as c:
            r = await c.get(f"{base}/object_info")
            r.raise_for_status()
        _cache.update(em=time.time(), base=base,
                      badges={k: v["price_badge"] for k, v in r.json().items()
                              if v.get("price_badge")})
    return _cache["badges"]


def _valor(resultado) -> tuple[float, float] | None:
    """(minimo, maximo) em US$ a partir do que a expressao devolve."""
    if not isinstance(resultado, dict):
        return None
    t = resultado.get("type")
    if t == "usd" and isinstance(resultado.get("usd"), (int, float)):
        return float(resultado["usd"]), float(resultado["usd"])
    if t == "range_usd":
        a, b = resultado.get("min_usd"), resultado.get("max_usd")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return float(a), float(b)
    if t == "list_usd" and isinstance(resultado.get("usd"), list) and resultado["usd"]:
        v = [float(x) for x in resultado["usd"] if isinstance(x, (int, float))]
        if v:
            return min(v), max(v)
    return None


async def de_api(grafo: dict) -> tuple[float, float] | None:
    """Soma dos precos dos nos de API do grafo; None se algum nao der para avaliar."""
    badges = await _badges()
    total_min = total_max = 0.0
    achou = False
    for no in grafo.values():
        badge = badges.get(no["class_type"])
        if not badge:
            continue
        achou = True
        expr = badge.get("expr", "")
        if expr not in _compiladas:
            _compiladas[expr] = jsonata.Jsonata(expr)
        # A interface do ComfyUI compara os valores em minusculas ("1k", "720p",
        # "nano banana 2"); sem isso as tabelas das expressoes nao casam.
        widgets = {k: (v.lower() if isinstance(v, str) else v)
                   for k, v in no["inputs"].items() if not isinstance(v, list)}
        entradas = {k: {"connected": True} for k, v in no["inputs"].items() if isinstance(v, list)}
        try:
            faixa = _valor(_compiladas[expr].evaluate({"widgets": widgets, "inputs": entradas,
                                                      "input_groups": {}}))
        except Exception:
            faixa = None
        if faixa is None:
            return None
        total_min += faixa[0]
        total_max += faixa[1]
    return (total_min, total_max) if achou else None


def de_gpu(segundos: float) -> float:
    return segundos * USD_POR_SEGUNDO_GPU
