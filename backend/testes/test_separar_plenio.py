import json

import separacao


def test_grafo_plenio_tem_uma_faixa_por_saida_e_o_rest_vai_em_outros():
    g = separacao.grafo_plenio("refaudio_x.mp3")
    assert g["entrada"]["inputs"]["audio"] == "refaudio_x.mp3"
    assert g["modelo"]["inputs"]["kind.model"] == separacao.MODELO_PLENIO
    for faixa in separacao.FAIXAS_PLENIO:
        strips = json.loads(g[f"mix_{faixa}"]["inputs"]["mix"])["strips"]
        assert strips[faixa] == {"solo": True}
        assert ("rest" in strips) == (faixa == "other")
        assert g[f"salva_{faixa}"]["inputs"]["audio"] == [f"mix_{faixa}", 0]
