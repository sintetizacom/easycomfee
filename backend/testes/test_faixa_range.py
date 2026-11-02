from app import _faixa_pedida


def test_faixas_do_cabecalho_range():
    assert _faixa_pedida("bytes=0-", 100) == (0, 99)
    assert _faixa_pedida("bytes=10-19", 100) == (10, 19)
    assert _faixa_pedida("bytes=90-500", 100) == (90, 99)
    assert _faixa_pedida("bytes=-10", 100) == (90, 99)
    assert _faixa_pedida("bytes=200-", 100) is None
    assert _faixa_pedida(None, 100) is None
    assert _faixa_pedida("bytes=-", 100) is None
