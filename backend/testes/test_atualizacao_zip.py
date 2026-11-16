"""Update numa instalacao feita pelo .zip do GitHub (sem .git): a versao vem de versao_publicada.txt."""
import atualizacao as a

SHA = "0123456789abcdef0123456789abcdef01234567"


def _pasta_zip(tmp_path, monkeypatch, conteudo):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "versao_publicada.txt").write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(a, "RAIZ", tmp_path)
    monkeypatch.setattr(a, "ARQ_VERSAO", tmp_path / "backend" / "versao_publicada.txt")


def test_zip_com_versao_oferece_update(tmp_path, monkeypatch):
    _pasta_zip(tmp_path, monkeypatch, SHA + "\n")
    monkeypatch.setattr(a, "_novos_no_github", lambda sha: 4 if sha == SHA else 0)
    d = a.estado(forcar=True)
    assert d["disponivel"] and d["novos"] == 4 and d["zip"] and d["versao"] == SHA[:7]


def test_zip_em_dia(tmp_path, monkeypatch):
    _pasta_zip(tmp_path, monkeypatch, SHA)
    monkeypatch.setattr(a, "_novos_no_github", lambda sha: 0)
    assert not a.estado(forcar=True)["disponivel"]


def test_sem_git_e_sem_versao_nao_oferece(tmp_path, monkeypatch):
    _pasta_zip(tmp_path, monkeypatch, "$Format:%H$\n")  # a pasta de desenvolvimento / copia comum
    d = a.estado(forcar=True)
    assert not d["disponivel"] and d["motivo"] == "not a git install"


def test_script_do_zip_baixa_e_continua_igual():
    assert "codeload.github.com/sintetizacom/easycomfee/zip" in a.BAT_ZIP and "git pull" not in a.BAT_ZIP
    assert "npm run build" in a.BAT_ZIP and "start.bat" in a.BAT_ZIP
    assert "git pull" not in a.SH_ZIP and "npm run build" in a.SH_ZIP
