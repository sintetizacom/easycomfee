"""LTX 2.5 em GGUF (placas AMD / 12 GB): sem o int8 instalado, o grafo usa o GGUF e o Gemma bf16."""
import variantes as v
import workflows as w

SEM_INT8 = {"int8": False, "gemma_int8": False, "gguf": "LTX\2.5\ltx-2.5-22b-distilled-Q4_K_M.gguf",
            "gemma_bf16": "Gemma\gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"}


def test_troca_para_gguf_quando_so_ele_existe():
    g = {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "LTX\2.5\\" + v.LTX25_INT8, "weight_dtype": "default"}},
         "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Gemma\\" + v.LTX25_GEMMA_INT8, "type": "ltxv", "device": "default"}},
         "outro": {"class_type": "UNETLoader", "inputs": {"unet_name": "zimage.safetensors", "weight_dtype": "default"}}}
    assert v.aplicar_ltx25_gguf(g, SEM_INT8)
    assert g["unet"] == {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": SEM_INT8["gguf"]}}
    assert g["clip"]["inputs"]["clip_name"] == SEM_INT8["gemma_bf16"] and g["clip"]["inputs"]["type"] == "ltxv"
    assert g["outro"]["class_type"] == "UNETLoader"  # so o LTX 2.5 e trocado


def test_com_int8_instalado_nada_muda():
    g = {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": v.LTX25_INT8, "weight_dtype": "default"}}}
    com = dict(SEM_INT8, int8=True, gemma_int8=True)
    assert not v.aplicar_ltx25_gguf(g, com)
    assert g["unet"]["class_type"] == "UNETLoader"


def test_lora_do_usuario_entra_depois_do_gguf():
    g = {"unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "x.gguf"}},
         "amostra": {"class_type": "KSampler", "inputs": {"model": ["unet", 0]}}}
    assert w.aplicar_lora_usuario(g, "minha.safetensors", 0.8)
    assert g["amostra"]["inputs"]["model"][0].startswith("lora_usuario")
