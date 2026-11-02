"""Voz local usando os nós já instalados do TTS Audio Suite."""
import re
import httpx
import comfy
from nomes_audio import nome_audio


async def capacidades():
    if comfy.na_nuvem():
        # Na Comfy Cloud a voz e o Qwen3-TTS (aberto, Apache-2.0): o OmniVoice
        # nao esta la. Os tres modos existem; a transcricao automatica nao.
        return {"disponivel": True, "motivo": "", "transcricao": False, "design": True}
    try:
        info = await comfy.info_nos(comfy.BASE_PRINCIPAL)
        necessarios = ["OmniVoiceEngineNode", "UnifiedTTSTextNode", "CharacterVoicesNode", "LoadAudio", "SaveAudio", "PreviewAny"]
        faltam = [n for n in necessarios if n not in info]
        return {"disponivel": not faltam, "motivo": "Missing nodes: " + ", ".join(faltam) if faltam else "",
                "transcricao": all(n in info for n in ("GraniteASREngineNode", "UnifiedASRTranscribeNode", "LoadAudio", "PreviewAny")),
                "design": "UnifiedVoiceDesignerNode" in info}
    except Exception as e:
        return {"disponivel": False, "design": False, "motivo": comfy.motivo_sem_info(e)}


def grafo_transcricao(referencia, idioma="Portuguese"):
    if idioma not in {"Portuguese", "English", "Spanish", "German", "French", "Japanese"}:
        raise ValueError("Idioma não suportado pela transcrição automática. Digite a fala da referência.")
    return {
        "audio_voz": {"class_type": "LoadAudio", "inputs": {"audio": referencia}},
        "motor_asr": {"class_type": "GraniteASREngineNode", "inputs": {
            "model_name": "granite-speech-4.1-2b", "device": "cuda",
            "max_new_tokens": 256, "dtype": "bfloat16",
            "asr_use_forced_aligner": False, "attn_implementation": "eager"}},
        "transcreve": {"class_type": "UnifiedASRTranscribeNode", "inputs": {
            "engine": ["motor_asr", 0], "audio": ["audio_voz", 0],
            "language": idioma, "task": "transcribe", "timestamps": "none",
            "chunk_size": 30, "overlap": 2}},
        "texto_voz": {"class_type": "PreviewAny", "inputs": {"source": ["transcreve", 0]}},
    }


def texto_transcrito(saidas):
    textos = saidas.get("texto_voz", {}).get("text", [])
    texto = "\n".join(textos).strip()
    if not texto:
        raise comfy.ErroComfy("Nenhuma fala foi reconhecida. Confira o áudio de referência.")
    return texto


def grafo(p, seed):
    engine = {"model_variant": "OmniVoice", "device": "cuda", "language": p.idioma_voz,
              "num_step": p.passos_voz, "guidance_scale": 2.0, "t_shift": 0.1,
              "speed": p.velocidade_voz, "duration": 0.0, "dtype": "bfloat16",
              "mode": "Voice Design" if p.modo_voz == "criar" else "Text to Speech"}
    g = {"motor_voz": {"class_type": "OmniVoiceEngineNode", "inputs": engine}}
    if p.modo_voz == "criar":
        g["fala"] = {"class_type": "UnifiedVoiceDesignerNode", "inputs": {
            "TTS_engine": ["motor_voz", 0], "reference_text": p.prompt,
            "voice_instruction": tags_omnivoice(p.instrucao_voz), "seed": seed}}
        audio = ["fala", 1]
    else:
        inputs = {"TTS_engine": ["motor_voz", 0], "text": p.prompt,
                  "narrator_voice": "none", "seed": seed % (2**32), "batch_size": 1}
        if p.modo_voz == "clonar":
            g["ref_voz"] = {"class_type": "LoadAudio", "inputs": {"audio": p.referencia_voz}}
            g["personagem_voz"] = {"class_type": "CharacterVoicesNode", "inputs": {
                "voice_name": "none", "reference_text": p.transcricao_voz,
                "trim_start": 0.0, "trim_end": 0.0, "customized": False,
                "opt_audio_input": ["ref_voz", 0]}}
            inputs["opt_narrator"] = ["personagem_voz", 0]
        g["fala"] = {"class_type": "UnifiedTTSTextNode", "inputs": inputs}
        audio = ["fala", 0]
    g["salva"] = {"class_type": "SaveAudio", "inputs": {
        "audio": audio, "filename_prefix": "editor/" + nome_audio(
            (p.nome_voz, p.titulo_audio_voz), "voz")}}
    # TTS Text captura erros e devolve 1 segundo de silêncio com status de
    # sucesso. Ler o relatório evita registrar esse silêncio como narração.
    g["relatorio_voz"] = {"class_type": "PreviewAny", "inputs": {
        "source": ["fala", 2 if p.modo_voz == "criar" else 1]}}
    return g


def conferir_resultado(saidas):
    if "relatorio_voz" not in saidas and comfy.na_nuvem():
        return  # o Qwen3-TTS falha com erro de verdade; nao ha relatorio
    textos = saidas.get("relatorio_voz", {}).get("text", [])
    if not textos:
        raise comfy.ErroComfy("O motor não devolveu o relatório de geração de voz.")
    for texto in textos:
        if "TTS Text generation failed:" in texto:
            raise comfy.ErroComfy(texto[:1500])


FALANTES_QWEN = ["Ryan", "Aiden", "Dylan", "Eric", "Serena", "Vivian", "Ono_anna", "Sohee", "Uncle_fu"]


def grafo_nuvem(p, seed):
    """Os mesmos tres modos com o Qwen3-TTS 1.7B, para a Comfy Cloud."""
    comum = {"device": "auto", "precision": "bf16", "language": p.idioma_voz, "seed": seed % (2**32)}
    if p.modo_voz == "criar":
        fala = {"class_type": "FB_Qwen3TTSVoiceDesign", "inputs": {
            **comum, "text": p.prompt, "instruct": p.instrucao_voz, "model_choice": "1.7B"}}
    elif p.modo_voz == "clonar":
        fala = {"class_type": "FB_Qwen3TTSVoiceClone", "inputs": {
            **comum, "target_text": p.prompt, "model_choice": "1.7B", "ref_audio": ["ref_voz", 0],
            "ref_text": p.transcricao_voz,
            # Sem a fala da referencia, clona so o timbre.
            "x_vector_only": not p.transcricao_voz.strip()}}
    else:
        fala = {"class_type": "FB_Qwen3TTSCustomVoice", "inputs": {
            **comum, "text": p.prompt, "model_choice": "1.7B", "instruct": p.instrucao_voz,
            "speaker": p.falante_voz if p.falante_voz in FALANTES_QWEN else "Ryan"}}
    g = {"fala": fala, "salva": {"class_type": "SaveAudio", "inputs": {
        "audio": ["fala", 0], "filename_prefix": "editor/" + nome_audio((p.nome_voz, p.titulo_audio_voz), "voz")}}}
    if p.modo_voz == "clonar":
        g["ref_voz"] = {"class_type": "LoadAudio", "inputs": {"audio": p.referencia_voz}}
    return g


# O Voice Design do OmniVoice (local) so aceita itens de uma lista fixa; uma descricao
# livre ("Powerful deep male voice, dramatic...") derrubava a geracao. Aqui a descricao
# vira esses itens: genero, idade, tom, sussurro e sotaque. (A nuvem, Qwen3-TTS, le texto livre.)
_SOTAQUES = ("american", "british", "australian", "canadian", "indian", "chinese", "korean",
             "japanese", "portuguese", "russian")


def tags_omnivoice(texto: str) -> str:
    t = " " + re.sub(r"[^a-z\- ]+", " ", texto.lower()) + " "
    def tem(*palavras):
        return any(re.search(rf"\b{p}\b", t) for p in palavras)
    itens = []
    if tem("female", "woman", "women", "girl", "lady", "grandma", "grandmother", "she", "her", "feminine"):
        itens.append("female")
    elif tem("male", "man", "men", "boy", "guy", "grandpa", "grandfather", "he", "his", "masculine"):
        itens.append("male")
    if tem("child", "kid", "children"):
        itens.append("child")
    elif tem("teen", "teenager", "teenage"):
        itens.append("teenager")
    elif tem("middle-aged", "middle aged"):
        itens.append("middle-aged")
    elif tem("young"):
        itens.append("young adult")
    elif tem("elderly", "old", "grandma", "grandpa", "grandmother", "grandfather", "senior"):
        itens.append("elderly")
    elif tem("mature", "adult"):
        itens.append("middle-aged")
    if tem("very low pitch", "very deep", "very low"):
        itens.append("very low pitch")
    elif tem("very high pitch", "very high"):
        itens.append("very high pitch")
    elif tem("low pitch", "deep", "low", "bass", "baritone"):
        itens.append("low pitch")
    elif tem("high pitch", "high", "bright", "squeaky"):
        itens.append("high pitch")
    elif tem("moderate pitch", "moderate", "medium"):
        itens.append("moderate pitch")
    if tem("whisper", "whispering", "whispered"):
        itens.append("whisper")
    for s in _SOTAQUES:
        if tem(s):
            itens.append(f"{s} accent")
            break
    return ", ".join(itens)
