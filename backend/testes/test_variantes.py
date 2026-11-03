import variantes as v


class P:
    def __init__(self, variante=""):
        self.variante = variante


def _grafo():
    return {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Flux3/flux3_image_klein_bf16.safetensors"}},
            "amostra": {"class_type": "KSampler", "inputs": {"steps": 25, "cfg": 3.5, "sampler_name": "euler"}}}


def test_rapida_troca_arquivo_e_ajustes(monkeypatch):
    monkeypatch.setattr(v, "achar_flux3", lambda: {"base": "Flux3/a.safetensors", "rapida": "outra/b.safetensors"})
    g = _grafo(); v.aplicar(g, P("rapida"))
    assert g["unet"]["inputs"]["unet_name"] == "outra/b.safetensors"
    assert g["amostra"]["inputs"] == {"steps": 15, "cfg": 1.0, "sampler_name": "er_sde"}


def test_so_a_destilada_instalada_usa_ela(monkeypatch):
    monkeypatch.setattr(v, "achar_flux3", lambda: {"rapida": "x.safetensors"})
    g = _grafo(); v.aplicar(g, P(""))
    assert g["unet"]["inputs"]["unet_name"] == "x.safetensors" and g["amostra"]["inputs"]["steps"] == 15


def test_base_mantem_ajustes(monkeypatch):
    monkeypatch.setattr(v, "achar_flux3", lambda: {"base": "Flux3/a.safetensors"})
    g = _grafo(); v.aplicar(g, P("rapida"))
    assert g["amostra"]["inputs"]["steps"] == 25 and g["unet"]["inputs"]["unet_name"] == "Flux3/a.safetensors"
