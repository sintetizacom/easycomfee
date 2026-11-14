import unittest
import app
import voz


def pedido(**kw):
    base = dict(modelo="voz", prompt="Hello there, this is a test.", idioma_voz="English")
    base.update(kw)
    return app.PedidoGeracao(**base)


class TestVozesExtras(unittest.TestCase):
    def test_breeze_design(self):
        g = voz.grafo_breeze(pedido(modelo_voz="breeze", modo_voz="criar", instrucao_voz="warm old man"), 5)
        self.assertEqual(g["voz"]["class_type"], "BreezeVoiceDesign")
        self.assertEqual(g["voz"]["inputs"]["description"], "warm old man")
        self.assertEqual(g["voz"]["inputs"]["language.model"], "Breeze TTS 2")
        self.assertEqual(g["fala"]["inputs"]["voice"], ["voz", 0])
        self.assertEqual(g["salva"]["class_type"], "SaveAudio")

    def test_breeze_clone_e_idioma_sem_modelo(self):
        g = voz.grafo_breeze(pedido(modelo_voz="breeze", modo_voz="clonar", referencia_voz="a.wav", idioma_voz="Portuguese"), 5)
        self.assertEqual(g["voz"]["class_type"], "BreezeVoiceClone")
        self.assertEqual(g["amostra"]["inputs"]["audio"], "a.wav")
        self.assertNotIn("language.model", g["fala"]["inputs"])

    def test_fish_clone_e_voz_aleatoria(self):
        g = voz.grafo_fish(pedido(modelo_voz="fish", modo_voz="clonar", referencia_voz="a.wav"), 5)
        self.assertEqual(g["fala"]["inputs"]["model.voices.voice0"], ["voz", 0])
        self.assertEqual(g["voz"]["inputs"]["files.audio0"], ["amostra", 0])
        sem = voz.grafo_fish(pedido(modelo_voz="fish", modo_voz="narrar"), 5)
        self.assertNotIn("model.voices.voice0", sem["fala"]["inputs"])
        self.assertNotIn("voz", sem)

    def test_isolar_voz(self):
        g = voz.grafo_isolar(pedido(modo_voz="limpar", referencia_voz="gravacao.wav"))
        self.assertEqual(g["limpa"]["class_type"], "ElevenLabsAudioIsolation")
        self.assertEqual(g["limpa"]["inputs"]["audio"], ["amostra", 0])
        self.assertEqual(g["salva"]["inputs"]["audio"], ["limpa", 0])


if __name__ == "__main__":
    unittest.main()
