import genjutsu


def test_resolucao_padrao_e_escolhida():
    assert genjutsu.resolucao("wan22_replace", "") == "480p"
    assert genjutsu.resolucao("wan22_replace", "720p") == "720p"
    assert genjutsu.resolucao("wan22_replace", "1080p") == "480p"  # nao oferecida: volta ao padrao
    assert genjutsu.resolucao("kling_omni", "1080p") == "1080p"
    assert genjutsu.resolucao("kling_omni", "480p") == "720p"
    assert genjutsu.resolucao("aleph2", "720p") == ""


def test_tamanho_wan_720p():
    assert genjutsu.tamanho_wan(1920, 1080, "720p") == (1280, 720)
    assert genjutsu.tamanho_wan(1080, 1920, "720p") == (720, 1280)
    assert genjutsu.tamanho_wan(1920, 1080) == (832, 480)


def test_api_recebe_a_resolucao():
    g = genjutsu.grafo_api("higgsfield", "v.mp4", ["r.png"], "x", 1, 5, "16:9", "p", "1080p")
    assert g["gera"]["inputs"]["model.resolution"] == "1080p"
    g = genjutsu.grafo_api("kling_omni", "v.mp4", [], "x", 1, 5, "16:9", "p")
    assert g["gera"]["inputs"]["resolution"] == "720p"
