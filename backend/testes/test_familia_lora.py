"""familia_lora: reconhece a familia de uma LoRA so pelo cabecalho do safetensors."""
import familia_lora as f


def _cab(chaves: dict, meta: dict | None = None) -> dict:
    cab = {k: {"dtype": "BF16", "shape": forma} for k, forma in chaves.items()}
    if meta:
        cab["__metadata__"] = meta
    return cab


def test_metadados_mandam():
    assert f.familia(_cab({"x.lora_A.weight": [16, 3]}, {"ss_base_model_version": "zimage"})) == "zimage"
    assert f.familia(_cab({"x.lora_A.weight": [16, 3]}, {"ss_base_model_version": "flux2_klein_9b"})) == "flux2_klein9"
    assert f.familia(_cab({"x.lora_A.weight": [16, 3]}, {"ss_base_model_version": "sdxl_base_v1-0"})) == "sdxl"


def test_kohya_sd15_sdxl_flux1():
    sd15 = {"lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_down.weight": [8, 768]}
    sdxl = {"lora_unet_input_blocks_4_1_transformer_blocks_0_attn2_to_k.lora_down.weight": [8, 2048]}
    flux = {"lora_unet_double_blocks_0_img_attn_qkv.lora_down.weight": [8, 3072]}
    assert f.familia(_cab(sd15)) == "sd15"
    assert f.familia(_cab(sdxl)) == "sdxl"
    assert f.familia(_cab(flux)) == "flux1"


def test_estrutura_dos_modelos_do_app():
    assert f.familia(_cab({"diffusion_model.layers.0.attention.to_q.lora_A.weight": [32, 3840]})) == "zimage"
    assert f.familia(_cab({"diffusion_model.blocks.0.attn.wq.lora_A.weight": [32, 6144]})) == "krea2"
    assert f.familia(_cab({"diffusion_model.double_blocks.0.img_attn.qkv.lora_A.weight": [32, 4096]})) == "flux2_klein9"
    assert f.familia(_cab({"diffusion_model.blocks.0.attn.qkv_proj.lora_A.weight": [32, 5376]})) == "minimax_h3"


def test_ltx_usa_a_largura_do_video_e_nao_a_do_som():
    # LoRA de som do LTX 2.3 22B: audio_attn1 tem 2048, o video tem 4096.
    cab = _cab({"diffusion_model.transformer_blocks.0.audio_attn1.to_q.lora_A.weight": [32, 2048],
                "diffusion_model.transformer_blocks.0.attn1.to_q.lora_A.weight": [32, 4096]})
    assert f.familia(cab) == "ltx22b"
    assert f.familia(_cab({"diffusion_model.transformer_blocks.0.attn1.to_q.lora_A.weight": [32, 2048]})) == "ltx2b"


def test_fora_do_modelo_e_desconhecida():
    assert f.familia(_cab({"text_encoders.model.layers.0.mlp.down_proj.lora_A.weight": [8, 2048]})) == "texto"
    assert f.familia(_cab({"video_context": [1, 4096]})) == "nenhuma"
    assert f.familia(_cab({"algo.estranho.lora_A.weight": [8, 999]})) is None


def test_cada_modelo_local_tem_familia():
    import presets
    for modelo in presets.SIMPLE:
        assert f.FAMILIAS_DO_MODELO.get(modelo), modelo
