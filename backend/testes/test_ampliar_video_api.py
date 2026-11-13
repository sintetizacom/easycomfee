import unittest

import app
import voz
import workflows


class AmpliarVideoApiTests(unittest.TestCase):
    def test_flashvsr_leva_a_resolucao_pedida(self):
        g = workflows.ampliar_video_api("v.mp4", "flashvsr", "4k")
        self.assertEqual(g["gera"]["class_type"], "WavespeedFlashVSRNode")
        self.assertEqual(g["gera"]["inputs"]["target_resolution"], "4K")
        self.assertEqual(g["salva"]["inputs"]["video"], ["gera", 0])

    def test_topaz_usa_o_ramo_starlight_fast(self):
        g = workflows.ampliar_video_api("v.mp4", "topaz", "1080p")
        ent = g["gera"]["inputs"]
        self.assertEqual(ent["upscaler_model"], "Starlight (Astra) Fast")
        self.assertEqual(ent["upscaler_model.upscaler_resolution"], "FullHD (1080p)")

    def test_som_mirelo_mantem_o_video_e_troca_o_audio(self):
        g = workflows.som_video_api("v.mp4", "mirelo", "steps on gravel", 7)
        self.assertEqual(g["gera"]["class_type"], "MireloVideoToSFX")
        self.assertEqual(g["gera"]["inputs"]["model.prompt"], "steps on gravel")
        self.assertEqual(g["junta"]["inputs"]["images"], ["partes", 0])
        self.assertEqual(g["junta"]["inputs"]["audio"], ["gera", 0])
        self.assertEqual(g["salva"]["inputs"]["video"], ["junta", 0])

    def test_som_sonilo_usa_o_video_de_entrada(self):
        g = workflows.som_video_api("v.mp4", "sonilo", "", 7)
        self.assertEqual(g["gera"]["class_type"], "SoniloVideoToMusic")
        self.assertEqual(g["gera"]["inputs"]["video"], ["carga", 0])
        with self.assertRaises(ValueError):
            workflows.som_video_api("v.mp4", "outro")

    def test_elevenlabs_leva_voz_idioma_e_etiqueta_de_emocao(self):
        p = app.PedidoGeracao(modelo="voz", modelo_voz="elevenlabs", prompt="Hello there", falante_voz="Sarah",
                              idioma_voz="Portuguese", instrucao_voz="[whispers]", proporcao="1:1")
        g = voz.grafo_elevenlabs(p, 9)
        self.assertEqual(g["voz"]["inputs"]["voice"], "Sarah (female, american)")
        self.assertEqual(g["fala"]["inputs"]["text"], "[whispers] Hello there")
        self.assertEqual(g["fala"]["inputs"]["language_code"], "pt")
        self.assertEqual(g["salva"]["inputs"]["audio"], ["fala", 0])
        sem = voz.grafo_elevenlabs(app.PedidoGeracao(modelo="voz", modelo_voz="elevenlabs", prompt="x",
                                                       falante_voz="Inexistente", proporcao="1:1"), 1)
        self.assertEqual(sem["voz"]["inputs"]["voice"], "Roger (male, american)")

    def test_metodo_desconhecido_e_recusado(self):
        with self.assertRaises(ValueError):
            workflows.ampliar_video_api("v.mp4", "outro")


if __name__ == "__main__":
    unittest.main()
