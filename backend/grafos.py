"""Receita de nodes de cada resultado: o grafo do ComfyUI que gerou o arquivo.

O botao "Node recipe" do visualizador baixa este JSON (formato API do ComfyUI,
que se arrasta direto no canvas). Guardado por arquivo de saida, em
dados/grafos/<subpasta>__<nome>.json, na hora em que a geracao termina.
"""
import json
import pathlib
import re

import config

PASTA = config.RAIZ / "dados" / "grafos"


def _caminho(subpasta: str, nome: str) -> pathlib.Path:
    # Nome de arquivo seguro: nada de barras nem "..", so o que o motor gera.
    seguro = re.sub(r"[^A-Za-z0-9._-]", "_", f"{subpasta}__{nome}")
    return PASTA / f"{seguro}.json"


def salvar(grafo: dict, saidas: list[dict]) -> None:
    if not grafo:
        return
    PASTA.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(grafo, ensure_ascii=False, indent=1)
    for s in saidas:
        _caminho(s.get("subpasta", ""), s["nome"]).write_text(texto, encoding="utf-8")


def ler(subpasta: str, nome: str) -> dict | None:
    c = _caminho(subpasta, nome)
    return json.loads(c.read_text(encoding="utf-8")) if c.is_file() else None
