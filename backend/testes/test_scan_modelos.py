import os

import scan_modelos as sm

TAM = sm.MINIMO + 123


def _prep(tmp_path, monkeypatch):
    models = tmp_path / "ComfyUI" / "models"
    cat = [{"id": "krea2", "nome": "Krea 2", "arquivos": [
        {"pasta": "diffusion_models", "subpasta": "Krea", "arquivo": "krea2.safetensors", "tamanho": TAM}]}]
    monkeypatch.setattr(sm.pacotes, "carregar", lambda: cat)
    monkeypatch.setattr(sm.instalador, "destino", lambda a: models / a["pasta"] / a["subpasta"] / a["arquivo"])
    return models


def _arquivo(p, tam):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.truncate(tam)
    return p


def test_renomeado_vira_hardlink(tmp_path, monkeypatch):
    models = _prep(tmp_path, monkeypatch)
    _arquivo(tmp_path / "meus" / "krea_v2_renomeado.safetensors", TAM)
    _arquivo(tmp_path / "meus" / "outra_versao_fp8.safetensors", TAM + 999)
    r = sm.escanear(str(tmp_path / "meus"))
    alvo = models / "diffusion_models" / "Krea" / "krea2.safetensors"
    assert [v["modo"] for v in r["vinculados"]] == ["hardlink"] and alvo.stat().st_size == TAM
    assert os.path.samefile(alvo, tmp_path / "meus" / "krea_v2_renomeado.safetensors")
    assert [n["arquivo"] for n in r["nao_reconhecidos"]] == ["outra_versao_fp8.safetensors"]


def test_ja_instalado_nao_mexe(tmp_path, monkeypatch):
    models = _prep(tmp_path, monkeypatch)
    _arquivo(models / "diffusion_models" / "Krea" / "krea2.safetensors", TAM)
    r = sm.escanear(str(models))
    assert not r["vinculados"] and len(r["ja_tinha"]) == 1


def test_pasta_inexistente(tmp_path):
    try:
        sm.escanear(str(tmp_path / "nao"))
        assert False
    except ValueError:
        pass
