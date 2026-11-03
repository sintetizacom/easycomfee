import musica


def _info(unet, clip2):
    lista = lambda *n: {"input": {"required": {}}}
    info = {n: {"input": {"required": {}}} for n in musica.MODELOS["ace-step15"]["nos"] + ["KSampler", "VAEDecodeAudio", "SaveAudio"]}
    info["UNETLoader"] = {"input": {"required": {"unet_name": [[unet]]}}}
    info["DualCLIPLoader"] = {"input": {"required": {"clip_name1": [["qwen_0.6b_ace15.safetensors"]], "clip_name2": [[clip2]]}}}
    info["VAELoader"] = {"input": {"required": {"vae_name": [["ace_1.5_vae.safetensors"]]}}}
    return info


def test_reconhece_o_turbo_comum():
    r = musica.resolver(_info("acestep_v1.5_turbo.safetensors", "qwen_1.7b_ace15.safetensors"), "ace-step15")
    assert r["disponivel"] and r["pesos"]["unet"] == "acestep_v1.5_turbo.safetensors"


def test_reconhece_o_xl_turbo():
    r = musica.resolver(_info("ACE/acestep_v1.5_xl_turbo_bf16.safetensors", "qwen_4b_ace15.safetensors"), "ace-step15")
    assert r["disponivel"] and r["pesos"]["clip2"] == "qwen_4b_ace15.safetensors"


def test_sem_nenhum_diz_o_que_falta():
    r = musica.resolver(_info("outro.safetensors", "qwen_4b_ace15.safetensors"), "ace-step15")
    assert not r["disponivel"] and "acestep_v1.5_turbo.safetensors" in r["motivo"]
