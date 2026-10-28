"""Configuracao comum do pytest para os testes do backend.

- Poe a pasta backend/ no sys.path: alguns arquivos importam config, pacotes
  etc. sem ajustar o caminho e so funcionavam rodados de dentro dela.
- Os arquivos de "contratos" (test_video, test_edicao...) anotam as falhas em
  uma lista `_falhas` em vez de usar assert, para o main() listar todas de uma
  vez. Rodados pelo pytest, isso passava calado; aqui cada teste que anotar
  falha nova e reprovado com elas.
"""
import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    falhas = getattr(item.module, "_falhas", None)
    antes = len(falhas) if isinstance(falhas, list) else 0
    resultado = yield
    if isinstance(falhas, list) and len(falhas) > antes:
        novas = falhas[antes:]
        del falhas[antes:]
        if resultado.excinfo is None:
            resultado.force_exception(AssertionError(chr(10).join(novas)))
