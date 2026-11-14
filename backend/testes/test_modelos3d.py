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
        self.assertFalse(g["gera"]["inputs"]["generate_type.pbr"])
        com_pbr = modelos3d.grafo("tencent", "a.png", True, 7, ajustes={"pbr": True, "faces": "1000000"})
        self.assertTrue(com_pbr["gera"]["inputs"]["generate_type.pbr"])
        self.assertEqual(com_pbr["gera"]["inputs"]["face_count"], 1000000)
        self.assertEqual(modelos3d.grafo("tencent", "a.png", False)["gera"]["inputs"]["generate_type"], "Geometry")
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

    def test_ajustes_validos_chegam_ao_grafo(self):
        g = modelos3d.grafo("tripo", "a.png", True, 7, ajustes={"versao": "v3.0-20250812", "faces": "50000", "low_poly": True,
                                                              "textura_qualidade": "extreme", "pbr": False})
        i = g["gera"]["inputs"]
        self.assertEqual((i["model_version"], i["face_limit"], i["smart_low_poly"], i["texture_quality"], i["pbr"]),
                         ("v3.0-20250812", 50000, True, "extreme", False))
        m = modelos3d.grafo("meshy", "a.png", True, 7, ajustes={"topologia": "quad", "pose": "T-pose", "textura_resolucao": "8k", "ultra": True})
        j = m["gera"]["inputs"]
        self.assertEqual((j["should_remesh.topology"], j["pose_mode"], j["should_texture.texture_resolution"], j["ultra_mode"]),
                         ("quad", "T-pose", "8k", True))
        self.assertIn("ultra_resolution", j)
        r = modelos3d.grafo("rodin", "a.png", True, 7, ajustes={"modo": "Fast", "nivel": "Medium", "pose_t": True})
        k = r["gera"]["inputs"]
        self.assertEqual((k["mode"], k["mode.tier"], k["mode.mesh_faces"], k["TAPose"]), ("Fast", "Gen-2.5-Medium", 20000, True))
        self.assertNotIn("mode.polygon_count", k)
        e = modelos3d.grafo("rodin", "a.png", True, 7, ajustes={"modo": "Extreme-High"})["gera"]["inputs"]
        self.assertEqual(e["mode.mesh_mode"], "Raw")

    def test_ajustes_invalidos_viram_o_padrao(self):
        aj = modelos3d.limpar_ajustes("tripo", {"versao": "x", "faces": "999", "pbr": "nao", "intruso": 1})
        self.assertEqual(aj["versao"], "v3.1-20260211")
        self.assertEqual(aj["faces"], "-1")
        self.assertTrue(aj["pbr"])
        self.assertNotIn("intruso", aj)

    def test_catalogo_para_a_tela(self):
        cat = {m["id"]: m for m in modelos3d.catalogo()}
        self.assertEqual(set(cat), set(modelos3d.MODELOS))
        self.assertEqual(cat["tripo_texto"]["modos"], ["texto"])
        for m in cat.values():
            for a in m["ajustes"]:
                self.assertIn(a["tipo"], ("select", "toggle"))
                if a["tipo"] == "select":
                    self.assertIn(a["padrao"], [o[0] for o in a["opcoes"]])

    def test_varias_vistas(self):
        v = {"esquerda": "l.png", "costas": "b.png", "direita": "r.png"}
        tr = modelos3d.grafo("tripo", "f.png", True, 7, vistas=v)
        self.assertEqual(tr["gera"]["class_type"], "TripoMultiviewToModelNode")
        self.assertEqual((tr["gera"]["inputs"]["image_left"], tr["gera"]["inputs"]["image_back"], tr["gera"]["inputs"]["image_right"]),
                         (["imagem_esquerda", 0], ["imagem_costas", 0], ["imagem_direita", 0]))
        self.assertEqual(tr["salva"]["inputs"]["mesh"], ["gera", 2])
        ro = modelos3d.grafo("rodin", "f.png", True, 7, vistas={"costas": "b.png"})
        self.assertEqual(ro["gera"]["inputs"]["images.image1"], ["imagem_costas", 0])
        self.assertEqual(ro["salva"]["inputs"]["mesh"], ["gera", 0])
        me = modelos3d.grafo("meshy", "f.png", True, 7, vistas={"esquerda": "l.png"})
        self.assertEqual(me["gera"]["class_type"], "MeshyMultiImageToModelNode")
        self.assertEqual(me["gera"]["inputs"]["images.image1"], ["imagem_esquerda", 0])
        self.assertNotIn("image", me["gera"]["inputs"])
        te = modelos3d.grafo("tencent", "f.png", True, 7, vistas=v)
        self.assertEqual(te["gera"]["inputs"]["image_back"], ["imagem_costas", 0])
        # sem vistas extras: continua o modo de uma imagem
        um = modelos3d.grafo("meshy", "f.png", True, 7, vistas={})
        self.assertEqual(um["gera"]["class_type"], "MeshyImageToModelNode")
        # chaves estranhas sao ignoradas
        self.assertNotIn("imagem_x", modelos3d.grafo("tripo", "f.png", vistas={"x": "z.png"}))

    def test_tripo_encadeia_retopologia_rig_animacao_e_formato(self):
        aj = {"retopologia": "10000", "animacao": "preset:run", "formato_extra": "FBX"}  # esqueleto de pessoa e o padrao
        g = modelos3d.grafo("tripo", "f.png", True, 7, ajustes=aj)
        self.assertEqual(g["retopo"]["inputs"]["model_task_id"], ["gera", 0])
        self.assertEqual(g["retopo"]["inputs"]["face_limit"], 10000)
        self.assertEqual(g["rig"]["inputs"]["original_model_task_id"], ["retopo", 1])
        self.assertEqual(g["animacao"]["inputs"]["original_model_task_id"], ["rig", 1])
        self.assertEqual(g["animacao"]["inputs"]["animation"], "preset:run")
        self.assertEqual(g["converte"]["inputs"]["original_model_task_id"], ["animacao", 1])
        self.assertEqual(g["converte"]["inputs"]["format"], "FBX")
        # O no da nuvem exige todos os campos, mesmo os "opcionais".
        for k in ("quad", "force_symmetry", "face_limit", "flatten_bottom", "flatten_bottom_threshold", "texture_size", "texture_format",
                  "pivot_to_center_bottom", "scale_factor", "with_animation", "pack_uv", "bake", "part_names", "fbx_preset",
                  "export_vertex_colors", "export_orientation", "animate_in_place"):
            self.assertIn(k, g["converte"]["inputs"])
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["animacao", 2])
        self.assertEqual(g["salva_extra"]["inputs"]["mesh"], ["converte", 0])
        self.assertIn("fbx", g["salva_extra"]["inputs"]["filename_prefix"])

    def test_tripo_so_o_esqueleto_e_multivista(self):
        g = modelos3d.grafo("tripo", "f.png", True, 7, ajustes={"animacao": "rig"}, vistas={"costas": "b.png"})
        self.assertNotIn("animacao", g)
        self.assertEqual(g["rig"]["inputs"]["original_model_task_id"], ["gera", 1])  # o no de varias vistas tem a tarefa na saida 1
        self.assertEqual(g["salva"]["inputs"]["mesh"], ["rig", 2])
        simples = modelos3d.grafo("tripo", "f.png", True, 7)
        self.assertNotIn("rig", simples)
        self.assertNotIn("salva_extra", simples)
        self.assertEqual(simples["salva"]["inputs"]["mesh"], ["gera", 1])

    def test_esqueleto_de_criatura_e_de_pessoa(self):
        pessoa = modelos3d.grafo("tripo", "f.png", True, 7, ajustes={"animacao": "preset:run"})["rig"]["inputs"]
        self.assertEqual((pessoa["model_version"], pessoa["rig_type"]), ("v1.0-20240301", "biped"))
        bicho = modelos3d.grafo("tripo", "f.png", True, 7, ajustes={"animacao": "preset:quadruped:walk", "esqueleto": "creature"})
        self.assertEqual((bicho["rig"]["inputs"]["model_version"], bicho["rig"]["inputs"]["rig_type"]), ("v2.5-20260210", "auto"))
        with self.assertRaises(ValueError):  # animacao de pessoa em criatura
            modelos3d.grafo("tripo", "f.png", True, 7, ajustes={"animacao": "preset:biped:dance_01", "esqueleto": "creature"})
        with self.assertRaises(ValueError):  # animacao de bicho em pessoa
            modelos3d.grafo("tripo", "f.png", True, 7, ajustes={"animacao": "preset:quadruped:walk"})

    def test_pos_processamento_so_no_tripo(self):
        for m in ("meshy", "rodin", "tencent"):
            ids = {a["id"] for a in modelos3d.MODELOS[m]["ajustes"]}
            self.assertFalse({"animacao", "retopologia", "formato_extra"} & ids)

    def test_modelo_desconhecido(self):
        with self.assertRaises(ValueError):
            modelos3d.grafo("outro", "a.png")


if __name__ == "__main__":
    unittest.main()
