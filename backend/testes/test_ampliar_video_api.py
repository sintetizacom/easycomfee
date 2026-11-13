import unittest

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

    def test_metodo_desconhecido_e_recusado(self):
        with self.assertRaises(ValueError):
            workflows.ampliar_video_api("v.mp4", "outro")


if __name__ == "__main__":
    unittest.main()
