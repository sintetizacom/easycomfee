"""Receita de nodes: o grafo de cada resultado, guardado pelo nome do arquivo."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import grafos  # noqa: E402


def test_salva_e_le_por_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(grafos, "PASTA", tmp_path)
    g = {"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    grafos.salvar(g, [{"nome": "img_001.png", "subpasta": "editor"}])
    assert grafos.ler("editor", "img_001.png") == g
    assert grafos.ler("editor", "outra.png") is None


def test_nome_com_barras_nao_sai_da_pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(grafos, "PASTA", tmp_path / "grafos")
    grafos.salvar({"1": {}}, [{"nome": "../../fora.png", "subpasta": "../x"}])
    assert [p.parent for p in tmp_path.rglob("*.json")] == [tmp_path / "grafos"]
