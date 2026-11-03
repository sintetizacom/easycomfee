import workflows


def test_rascunho_usa_o_modelo_draft_em_480p_e_le_o_id():
    g = workflows.gerar_video_api("seedance", "x", 1, "texto", "16:9", "1080p", 5, rascunho=True)
    e = g["gera"]["inputs"]
    assert (e["model"], e["model.resolution"]) == ("Seedance 2.5 Draft", "480p")
    assert g["rascunho"]["inputs"]["source"] == ["gera", 1]


def test_sem_rascunho_nada_muda():
    g = workflows.gerar_video_api("seedance", "x", 1, "texto", "16:9", "1080p", 5)
    assert g["gera"]["inputs"]["model"] == "Seedance 2.5" and "rascunho" not in g


def test_final_a_partir_do_rascunho():
    g = workflows.seedance_final("abc-123")
    assert g["gera"]["class_type"] == "ByteDance2DraftToFinalVideoNode"
    assert g["gera"]["inputs"]["draft_task_id"] == "abc-123"
