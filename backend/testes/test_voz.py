"""Contratos de voz: referências com transcrição e saída de áudio na galeria."""
import asyncio
import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app
import comfy
import voz


class VozTests(unittest.TestCase):
    # Os grafos e conferencias aqui sao os do motor local (OmniVoice), seja
    # qual for o modo que o app deixou gravado nas preferencias.
    def setUp(self):
        self._motor = comfy.MODO["motor"]
        comfy.MODO["motor"] = "local"

    def tearDown(self):
        comfy.MODO["motor"] = self._motor

    def test_identificacao_no_arquivo_em_todos_os_modos(self):
        for modo in ("narrar", "criar", "clonar"):
            p = app.PedidoGeracao(modelo="voz", prompt="Olá", modo_voz=modo,
                                  nome_voz="Ana / Estúdio", titulo_audio_voz="Abertura: verão?",
                                  instrucao_voz="female", referencia_voz="ref.wav",
                                  transcricao_voz="fala")
            nome = voz.grafo(p, 42)["salva"]["inputs"]["filename_prefix"]
            self.assertEqual(nome, "editor/Ana Estudio - Abertura verao")
            self.assertNotIn("\\", nome)
        p.nome_voz = ""
        p.titulo_audio_voz = ""
        self.assertEqual(voz.grafo(p, 42)["salva"]["inputs"]["filename_prefix"], "editor/voz")

    def test_idioma_da_narracao_e_independente_da_referencia(self):
        for idioma in ("English", "Spanish", "German", "Italian", "French", "Japanese", "Chinese", "Korean"):
            p = app.PedidoGeracao(modelo="voz", prompt="Texto", idioma_voz=idioma)
            self.assertEqual(voz.grafo(p, 42)["motor_voz"]["inputs"]["language"], idioma)
        self.assertEqual(voz.grafo_transcricao("voz.wav", "German")["transcreve"]["inputs"]["language"], "German")
        with self.assertRaises(ValueError):
            voz.grafo_transcricao("voz.wav", "Italian")
        with self.assertRaises(ValueError):
            app.PedidoTranscricao(referencia="voz.wav", idioma="Italian")

    def test_upload_audio_nome_com_pontos(self):
        from io import BytesIO
        arquivo = app.UploadFile(filename="[Voz 2.0] Olha ......uêii_.mp3", file=BytesIO(b"audio"))
        with patch.object(comfy, "enviar_imagem", new_callable=AsyncMock) as enviar:
            enviar.return_value = "refaudio_seguro.mp3"
            resultado = asyncio.run(app.referencia_audio(arquivo))
        nome, dados = enviar.call_args.args
        self.assertNotIn("..", nome)
        self.assertTrue(nome.endswith(".mp3"))
        self.assertEqual(dados, b"audio")
        self.assertEqual(resultado["nome"], "refaudio_seguro.mp3")
        self.assertEqual(app._tipo_mime("voz.m4a"), "audio/mp4")

    def test_clonagem_preserva_transcricao(self):
        p = app.PedidoGeracao(modelo="voz", prompt="Nova fala", modo_voz="clonar",
                              referencia_voz="voz.wav", transcricao_voz="Fala original")
        g = voz.grafo(p, 42)
        self.assertEqual(g["personagem_voz"]["inputs"]["reference_text"], "Fala original")
        self.assertEqual(g["fala"]["inputs"]["opt_narrator"], ["personagem_voz", 0])
        self.assertEqual(g["salva"]["inputs"]["audio"], ["fala", 0])

    def test_design_salva_preview_correto(self):
        p = app.PedidoGeracao(modelo="voz", prompt="Olá", modo_voz="criar", instrucao_voz="female")
        g = voz.grafo(p, 42)
        self.assertEqual(g["salva"]["inputs"]["audio"], ["fala", 1])
        self.assertEqual(g["motor_voz"]["inputs"]["mode"], "Voice Design")

    def test_audio_final_ignora_previas(self):
        saidas = {"salva": {"audio": [{"filename": "voz.flac", "subfolder": "editor"}]},
                  "outro": {"audio": [{"filename": "preview.wav"}]}}
        self.assertEqual(comfy.imagens_salvas(saidas), [{"nome": "voz.flac", "subpasta": "editor", "tipo": "output"}])
        self.assertEqual(app._tipo_mime("voz.flac"), "audio/flac")

    def test_clonagem_incompleta_nao_entra_na_fila(self):
        with self.assertRaises(app.HTTPException) as e:
            asyncio.run(app.gerar(app.PedidoGeracao(modelo="voz", prompt="Olá", modo_voz="clonar")))
        self.assertEqual(e.exception.status_code, 400)

    def test_montagem_nao_expande_texto_falado(self):
        t = app.Tarefa(app.PedidoGeracao(modelo="voz", prompt="Fale exatamente isto"))
        g = asyncio.run(app.montar(t))
        self.assertEqual(g["fala"]["inputs"]["text"], t.pedido.prompt)
        self.assertEqual((t.largura, t.altura), (0, 0))

    def test_silencio_de_erro_nao_e_sucesso(self):
        with self.assertRaises(comfy.ErroComfy):
            voz.conferir_resultado({"relatorio_voz": {"text": ["❌ TTS Text generation failed: download error"]}})
        with self.assertRaises(comfy.ErroComfy):
            voz.conferir_resultado({})
        voz.conferir_resultado({"relatorio_voz": {"text": ["Generated successfully"]}})

    def test_transcricao_vazia_e_erro(self):
        with self.assertRaises(comfy.ErroComfy):
            voz.texto_transcrito({"texto_voz": {"text": [" "]}})
        self.assertEqual(voz.texto_transcrito({"texto_voz": {"text": ["Olá, mundo."]}}), "Olá, mundo.")

    def test_transcricao_persistida_e_recuperada(self):
        t = app.Tarefa(app.PedidoGeracao(modelo="transcricao_voz", prompt="Transcrição", referencia_voz="voz.wav"))
        t.resultado_texto = "Texto reconhecido"
        recuperada = app.Tarefa.de_registro(t.registro())
        self.assertEqual(recuperada.como_dict()["resultado_texto"], "Texto reconhecido")

    def test_transcricao_nao_grava_imagem_na_galeria(self):
        async def executar():
            t = app.Tarefa(app.PedidoGeracao(modelo="transcricao_voz", prompt="Transcrição", referencia_voz="voz.wav"))
            t.prompt_id = "teste-asr"
            h = {"status": {"status_str": "success"}, "outputs": {"texto_voz": {"text": ["Texto reconhecido"]}}}
            with patch.object(comfy, "historico", AsyncMock(return_value=h)), patch.object(app, "anunciar", AsyncMock()), patch.object(app.biblioteca, "registrar") as registrar:
                await app.esperar_fim(t)
                self.assertEqual(t.estado, "pronto")
                self.assertEqual(t.resultado_texto, "Texto reconhecido")
                self.assertEqual(t.imagens, [])
                registrar.assert_not_called()
        asyncio.run(executar())

    def test_transcricao_recusa_caminho_externo(self):
        for ref in ("../voz.wav", "C:\\voz.wav", "imagem.png", ""):
            with self.assertRaises(app.HTTPException) as e:
                asyncio.run(app.transcrever_voz(app.PedidoTranscricao(referencia=ref)))
            self.assertEqual(e.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
