import pytest

import minhas_vozes


def test_voz_do_design_guarda_descricao_e_seed():
    v = minhas_vozes.voz_de({"modelo": "voz", "modo_voz": "criar", "instrucao_voz": "warm male", "seed": 7}, " Joao ", "voz_1.flac", "editor")
    assert (v["nome"], v["tipo"], v["instrucao"], v["seed"]) == ("Joao", "criar", "warm male", 7)
    assert v["amostra"] == {"nome": "voz_1.flac", "subpasta": "editor"}


def test_voz_do_clone_guarda_a_gravacao():
    v = minhas_vozes.voz_de({"modelo": "voz", "modo_voz": "clonar", "referencia_voz": "refaudio_ab.wav", "transcricao_voz": "oi"}, "Eu", "v.flac", "editor")
    assert (v["referencia"], v["transcricao"]) == ("refaudio_ab.wav", "oi")


@pytest.mark.parametrize("p", [{"modelo": "voz", "modo_voz": "narrar"}, {"modelo": "musica"},
                               {"modelo": "voz", "modo_voz": "clonar", "referencia_voz": "../x.wav"}])
def test_recusa_o_que_nao_e_design_nem_clone(p):
    with pytest.raises(ValueError):
        minhas_vozes.voz_de(p, "x", "a.flac", "editor")


def test_salvar_listar_remover(tmp_path, monkeypatch):
    monkeypatch.setattr(minhas_vozes, "ARQUIVO", tmp_path / "v.json")
    v = minhas_vozes.salvar(minhas_vozes.voz_de({"modelo": "voz", "modo_voz": "criar", "instrucao_voz": "a", "seed": 1}, "A", "a.flac", ""))
    assert [x["id"] for x in minhas_vozes.listar()] == [v["id"]]
    assert minhas_vozes.remover(v["id"]) and minhas_vozes.listar() == []
