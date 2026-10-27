# coding: utf-8
"""Renderiza o mapa do Anygles NUM PROCESSO SO SEU, e sai.

POR QUE SUBPROCESSO, e nao a chamada direta que seria obvia:

  - solto, num processo novo, o `pyrender` roda nesta maquina: testado, render
    e `delete()` passam, inclusive chamados de dentro de uma thread;
  - DENTRO do ComfyUI, o mesmo codigo morre em `renderer.delete()` com
    "Attempt to retrieve context when no valid context".

Testei a hipotese obvia — que o ComfyUI executa nos em thread de trabalho e
contexto OpenGL e preso a thread — e ela NAO explica: em processo novo, dentro
de thread, funciona. Sobra interacao com o que ja esta carregado no processo do
servidor, que tem mais de vinte nos customizados. Nao fui atras de qual: um
contexto OpenGL vazando num servidor que fica dias no ar e pior que o custo de
abrir um processo, e isolar resolve a classe inteira de problema em vez de uma
instancia dela.

Entra por um .npz, sai um .png. Sao poucos megabytes de vertices e faces, e o
processo leva ~1 a 3 s — desprezivel perto da amostragem que vem depois.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# O pyrender so escolhe o caminho de desktop (pyglet) quando esta variavel esta
# AUSENTE. Qualquer valor diferente de "egl"/"osmesa" cai no `raise ValueError`
# dele, entao apagar e o unico caminho — e o `sam3d_normal.py`, que sera
# importado logo abaixo, define "egl" por conta propria ao carregar.
os.environ.pop("PYOPENGL_PLATFORM", None)

import numpy as np


def _carrega_render(origem: Path):
    """Importa `_render` do pacote do autor PELO CAMINHO.

    A pasta tem hifen no nome, entao nao da para importar por nome. E a funcao
    e importada, nao copiada, de proposito: o mapa que o LoRA consome tem
    PROFUNDIDADE no canal azul, nao a normal Z, e reescrever isso a mao e
    convidar uma divergencia silenciosa na proxima versao deles.
    """
    caminho = origem / "sam3d_normal.py"
    spec = importlib.util.spec_from_file_location("_anygles_render", caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    # O modulo deles faz setdefault("PYOPENGL_PLATFORM", "egl") ao carregar.
    os.environ.pop("PYOPENGL_PLATFORM", None)
    return mod._render


def principal(entrada: str, saida: str, origem: str) -> int:
    d = np.load(entrada)
    render = _carrega_render(Path(origem))
    imagem = render(
        d["vertices"], d["faces"], d["camera"], float(d["focal"]),
        int(d["largura"]), int(d["altura"]), float(d["escala"]), d["deslocamento"],
    )
    imagem.save(saida)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1], sys.argv[2], sys.argv[3]))
