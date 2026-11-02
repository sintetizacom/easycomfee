import pytest

from voz import tags_omnivoice


@pytest.mark.parametrize("texto, tags", [
    ("Powerful deep male voice, dramatic movie trailer delivery, slow and intense", "male, low pitch"),
    ("Warm middle-aged male narrator, deep and calm, documentary style", "male, middle-aged, low pitch"),
    ("Young energetic female host, bright and friendly, fast pace", "female, young adult, high pitch"),
    ("Soft gentle female voice, close whisper, calm and intimate", "female, whisper"),
    ("Elderly man with a raspy voice, slow storyteller, slight British accent", "male, elderly, british accent"),
    ("female, young adult, moderate pitch, whisper", "female, young adult, moderate pitch, whisper"),
    ("male, middle-aged, very low pitch", "male, middle-aged, very low pitch"),
    ("dramatic and intense", ""),
])
def test_descricao_livre_vira_itens_do_omnivoice(texto, tags):
    assert tags_omnivoice(texto) == tags
