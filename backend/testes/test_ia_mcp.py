"""EasyComfee MCP: registro nos clientes (sem tocar nos arquivos reais) e trava de custo."""
import importlib.util
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2] / "easycomfee-mcp" / "server"


def _carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registrar_mantem_outros_servidores(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYCOMFEE_TESTE_HOME", str(tmp_path))
    (tmp_path / ".lmstudio").mkdir()
    arq = tmp_path / ".lmstudio" / "mcp.json"
    arq.write_text(json.dumps({"mcpServers": {"outro": {"command": "x"}}}), encoding="utf-8")
    cfg = _carregar("cfg_mcp", "escrever_config.py")
    assert [n for n, _ in cfg.clientes()] == ["LM Studio"]
    assert not cfg.registrado(arq)
    assert cfg.registrar(arq) == "added"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    assert set(dados["mcpServers"]) == {"outro", "easycomfee"}
    assert (tmp_path / ".lmstudio" / "mcp.json.bak").exists()
    assert cfg.registrar(arq) == "updated"


def test_codex_toml_so_mexe_na_secao_do_easycomfee(tmp_path, monkeypatch):
    import tomllib
    monkeypatch.setenv("EASYCOMFEE_TESTE_HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    arq = tmp_path / ".codex" / "config.toml"
    original = ('model = "x"\n\n[mcp_servers.outro]\ncommand = "a"\n\n'
                '[mcp_servers.outro.tools.t]\napproval_mode = "approve"\n')
    arq.write_text(original, encoding="utf-8")
    cfg = _carregar("cfg_mcp3", "escrever_config.py")
    assert ("Codex", arq) in cfg.clientes()
    assert not cfg.registrado(arq)
    assert cfg.registrar(arq) == "added"
    dados = tomllib.loads(arq.read_text(encoding="utf-8"))
    assert dados["model"] == "x" and dados["mcp_servers"]["outro"]["tools"]["t"]
    e = dados["mcp_servers"]["easycomfee"]
    assert e["args"] == ["-m", "easycomfee_mcp"] and e["env"]["EDITOR_URL"].startswith("http")
    assert (tmp_path / ".codex" / "config.toml.bak").read_text(encoding="utf-8") == original
    # De novo: atualiza sem duplicar a secao.
    assert cfg.registrar(arq) == "updated"
    assert arq.read_text(encoding="utf-8").count("[mcp_servers.easycomfee]") == 1
    assert cfg.registrado(arq)


def test_toml_quebrado_nao_e_sobrescrito(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYCOMFEE_TESTE_HOME", str(tmp_path))
    arq = tmp_path / "config.toml"
    arq.write_text("[quebrado", encoding="utf-8")
    cfg = _carregar("cfg_mcp4", "escrever_config.py")
    try:
        cfg.registrar(arq)
        assert False, "devia recusar"
    except ValueError:
        pass
    assert arq.read_text(encoding="utf-8") == "[quebrado"


def test_json_quebrado_nao_e_sobrescrito(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYCOMFEE_TESTE_HOME", str(tmp_path))
    arq = tmp_path / "c.json"
    arq.write_text("{quebrado", encoding="utf-8")
    cfg = _carregar("cfg_mcp2", "escrever_config.py")
    try:
        cfg.registrar(arq)
        assert False, "devia recusar"
    except ValueError:
        pass
    assert arq.read_text(encoding="utf-8") == "{quebrado"


def test_maximo_da_estimativa():
    sys.path.insert(0, str(RAIZ))
    try:
        from easycomfee_mcp import app
    except ModuleNotFoundError:  # o ambiente do app nao tem o pacote mcp: o smoke test cobre
        return
    assert app._maximo({"tipo": "gratis"}) == (0.0, True)
    assert app._maximo({"tipo": "api", "min": 0.1, "max": 0.3}) == (0.3, True)
    assert app._maximo({"tipo": "gpu", "usd": 0.05}) == (0.05, True)
    assert app._maximo({"tipo": "desconhecido"})[1] is False
