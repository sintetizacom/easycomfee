import unittest
import modelos3d


class TestModelos3D(unittest.TestCase):
    def test_tripo_leva_a_imagem_e_salva_o_glb(self):
        g = modelos3d.grafo("tripo", "a.png", True, 7)
        self.assertEqual(g["imagem"]["inputs"]["image"], "a.png")
        self.assertEqual(g["gera"]["class_type"], "TripoImageToModelNodeV2")
        self.assertTrue(g["gera"]["inputs"]["texture"])
        self.assertEqual(g["salva"]["class_type"], "SaveGLB")
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["gera", 1])

    def test_meshy_sem_textura(self):
        g = modelos3d.grafo("meshy", "a.png", False, 7)
        self.assertEqual(g["gera"]["inputs"]["should_texture"], "false")
        self.assertNotIn("should_texture.enable_pbr", g["gera"]["inputs"])
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["gera", 2])

    def test_meshy_com_textura(self):
        g = modelos3d.grafo("meshy", "a.png", True, 7)
        self.assertEqual(g["gera"]["inputs"]["should_texture"], "true")
        self.assertEqual(g["gera"]["inputs"]["should_texture.texture_resolution"], "2k")

    def test_tripo_por_texto(self):
        g = modelos3d.grafo("tripo_texto", "", True, 7, prompt="a small wooden chair")
        self.assertEqual(g["gera"]["class_type"], "TripoTextToModelNodeV2")
        self.assertEqual(g["gera"]["inputs"]["prompt"], "a small wooden chair")
        self.assertNotIn("imagem", g)
        with self.assertRaises(ValueError):
            modelos3d.grafo("tripo_texto", "", True, 7, prompt="  ")

    def test_hunyuan_tencent(self):
        g = modelos3d.grafo("tencent", "a.png", True, 7)
        self.assertEqual(g["gera"]["class_type"], "TencentImageToModelNode")
        self.assertEqual(g["gera"]["inputs"]["generate_type"], "Normal")
        self.assertTrue(g["gera"]["inputs"]["generate_type.pbr"])
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["gera", 1])

    def test_rodin(self):
        g = modelos3d.grafo("rodin", "a.png", True, 7)
        self.assertEqual(g["gera"]["class_type"], "Rodin3D_Gen25_Image")
        self.assertEqual(g["gera"]["inputs"]["images.image0"], ["imagem", 0])
        self.assertEqual(g["gera"]["inputs"]["material"], "PBR")
        self.assertEqual(modelos3d.grafo("rodin", "a.png", False)["gera"]["inputs"]["material"], "None")
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["gera", 0])
        for k in ("texture_mode", "TAPose", "hd_texture", "texture_delight", "use_original_alpha",
                  "addon_highpack", "bbox_width", "bbox_height", "bbox_length", "height_cm"):
            self.assertIn(k, g["gera"]["inputs"])

    def test_modelo_desconhecido(self):
        with self.assertRaises(ValueError):
            modelos3d.grafo("outro", "a.png")


if __name__ == "__main__":
    unittest.main()
