"""A pagina da interface nao pode ficar guardada no navegador: depois do Update a pessoa
via a versao velha (16/11/2026). So vale com a interface compilada (frontend/dist)."""
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import app as A  # noqa: E402


@pytest.mark.skipif(not (A.ESTATICOS / "index.html").exists(), reason="interface nao compilada")
def test_pagina_sempre_confere_com_o_servidor():
    c = TestClient(A.app, base_url="http://127.0.0.1:8600")
    for rota in ("/", "/index.html", "/image/zimage"):
        r = c.get(rota, headers={"Sec-Fetch-Site": "same-origin"})
        assert r.status_code == 200, (rota, r.status_code)
        assert r.headers.get("cache-control") == "no-cache", rota
