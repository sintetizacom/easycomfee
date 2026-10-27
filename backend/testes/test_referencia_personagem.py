"""Contratos do caminho de identidade e recusas antes da fila. Sem GPU."""
import asyncio
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app as A
import workflows as W
from fastapi import HTTPException


class ReferenciaPersonagem(unittest.TestCase):
    def test_identidade_entra_no_encoder_e_no_modelo(self):
        for modelo in ('krea', 'kroma', 'kroma_foto'):
            with self.subTest(modelo=modelo):
                g = W.gerar_simples(modelo, 'walking in a forest', '', 42, 896, 1152,
                                    referencias=['personagem.png'], forca_referencia=2)
                self.assertEqual(g['amostra']['inputs']['model'], ['ref_modelo', 0])
                self.assertEqual(g['pos']['inputs']['image'], ['ref_escala', 0])
                self.assertEqual(g['ref_modelo']['inputs']['source_latent'], ['ref_latente', 0])
                self.assertEqual(g['ref_modelo']['inputs']['ref_boost'], 2)
                self.assertEqual(g['latente']['inputs']['width'], 896)
                self.assertEqual(g['latente']['inputs']['height'], 1152)
                self.assertIn('walking in a forest', g['pos']['inputs']['prompt'])
                self.assertEqual(g['unet']['inputs']['unet_name'], A.presets.win(A.presets.SIMPLE[modelo]['unet']))

    def test_texto_sem_referencia_mantem_caminho_original(self):
        g = W.gerar_simples('krea', 'forest', '', 42, 1024, 1024)
        self.assertEqual(g['pos']['class_type'], 'CLIPTextEncode')
        self.assertEqual(g['amostra']['inputs']['model'], ['unet', 0])
        self.assertNotIn('ref_lora', g)

    def test_despachante_encaminha_referencia(self):
        p = A.PedidoGeracao(modelo='kroma', prompt='cafe', referencias=['p.png'], forca_referencia=3)
        g = asyncio.run(A.montar(A.Tarefa(p)))
        self.assertEqual(g['referencia']['inputs']['image'], 'p.png')
        self.assertEqual(g['ref_modelo']['inputs']['ref_boost'], 3)

    def test_varios_personagens_encadeiam_passadas(self):
        g = W.gerar_simples('kroma', 'bookshop', '', 7, 1344, 768,
                            referencias=['a.png', 'b.png', 'c.png'],
                            posicoes=['esquerda', '', 'direita'])
        # Cada passada parte da imagem da anterior e soma uma pessoa (*_b).
        self.assertEqual(g['ref_modelo_2']['inputs']['source_image'], ['decodifica', 0])
        self.assertEqual(g['ref_modelo_3']['inputs']['source_latent_b'], ['ref_latente_3', 0])
        self.assertEqual(g['pos_3']['inputs']['image'], ['decodifica_2', 0])
        self.assertEqual(g['salva']['inputs']['images'], ['decodifica_3', 0])
        self.assertIn('on the left side', g['pos']['inputs']['prompt'])
        self.assertIn('no other people', g['pos']['inputs']['prompt'])
        self.assertIn('on the right side', g['pos_3']['inputs']['prompt'])
        self.assertEqual({g['amostra' + k]['inputs']['seed'] for k in ('', '_2', '_3')}, {7, 8, 9})
        # Uma referencia so: grafo de sempre, sem passadas extras.
        um = W.gerar_simples('kroma', 'bookshop', '', 7, 1024, 1024, referencias=['a.png'])
        self.assertNotIn('ref_modelo_2', um)
        self.assertNotIn('no other people', um['pos']['inputs']['prompt'])

    def test_pedidos_invalidos_nao_entram_na_fila(self):
        casos = [dict(modelo='klein', referencias=['p.png']),
                 dict(modelo='krea', referencias=['p.png', 'q.png', 'r.png', 's.png']),
                 dict(modelo='kroma', referencias=['p.png', 'q.png'], posicoes_referencia=['acima', '']),
                 dict(modelo='krea', referencias=['inexistente.png']),
                 dict(modelo='krea', referencias=['p.png'], lote=2),
                 dict(modelo='kroma', referencias=['p.png'], escala=2)]
        for campos in casos:
            with self.subTest(campos=campos), patch.object(A, '_caminho_de_entrada',
                    side_effect=lambda r: '' if r == 'inexistente.png' else '/input/' + r):
                with self.assertRaises(HTTPException) as erro:
                    asyncio.run(A.gerar(A.PedidoGeracao(prompt='forest', **campos)))
                self.assertEqual(erro.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
