import relatorio


def test_limpar_tira_chaves_e_tokens():
    t = relatorio.limpar("key sk-abcdefghijklmnop123 token hf_ABCDEFGHIJKLMNOPQR Bearer abcdefghijklmnopqrstuv")
    assert "sk-abc" not in t and "hf_ABC" not in t and "abcdefghijklmnopqrstuv" not in t
