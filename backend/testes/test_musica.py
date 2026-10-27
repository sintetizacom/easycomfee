import sys,pathlib,unittest,asyncio
from unittest.mock import patch,AsyncMock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app,musica
class MusicaTests(unittest.TestCase):
    def test_ace_recebe_tonalidade_e_genero_vocal(self):
        pesos={'unet':'u','clip1':'c1','clip2':'c2','vae':'v'}
        p=app.PedidoGeracao(modelo='musica',modelo_musica='ace-step15',prompt='Jazz suave',
                            vocal_musica=True,letra_musica='Olá',
                            tonalidade_musica='F# minor',genero_vocal_musica='feminino')
        g=musica.grafo(p,42,pesos)
        self.assertEqual(g['cond_musica']['inputs']['keyscale'],'F# minor')
        self.assertIn('Female lead vocal.',g['cond_musica']['inputs']['tags'])
        self.assertEqual(g['cond_musica']['inputs']['lyrics'],'Olá')
        self.assertEqual(musica.configuracao_geracao(p)[0],g['cond_musica']['inputs']['tags'])
        p.vocal_musica=False
        self.assertNotIn('Female lead vocal.',musica.grafo(p,42,pesos)['cond_musica']['inputs']['tags'])
        self.assertNotIn('female',p.prompt.lower())
        self.assertEqual(app.PedidoGeracao(modelo='musica',prompt='Jazz').tonalidade_musica,'C major')
    def test_nome_musica_normaliza_sem_criar_subpastas(self):
        p=app.PedidoGeracao(modelo='musica',prompt='Jazz',projeto_musica='../João: Trio',titulo_musica='Chuva / verão\\mix?')
        nome=musica.nome_musica(p)
        self.assertEqual(nome,'Joao Trio - Chuva veraomix')
        self.assertNotIn('/',nome);self.assertNotIn('\\',nome)
        g=musica.grafo(p,42,{'unet':'u','clip':'c','vae':'v'})
        self.assertEqual(g['salva']['inputs']['filename_prefix'],'editor/'+nome)
        p.projeto_musica='';p.titulo_musica=''
        self.assertEqual(musica.nome_musica(p),'musica_minimax-music3')
    def test_cover_usa_guia_e_desativa_composicao_lm(self):
        p=app.PedidoGeracao(modelo='musica',modelo_musica='ace-step15',prompt='Jazz',referencia_musica='refaudio_teste.flac',transformacao_musica=.75)
        g=musica.grafo(p,42,{'unet':'u','clip1':'c1','clip2':'c2','vae':'v'})
        self.assertFalse(g['cond_musica']['inputs']['generate_audio_codes'])
        self.assertEqual(g['cond_guia']['inputs']['latent'],['guia_latente',0])
        self.assertEqual(g['amostra_musica']['inputs']['latent_image'],['guia_latente',0])
        self.assertEqual(g['amostra_musica']['inputs']['denoise'],.75)
        self.assertEqual(g['guia']['inputs']['audio'],'refaudio_teste.flac')
    def test_grafos_preservam_prompt_letra_duracao(self):
        pesos={'unet':'u','clip':'c','clip1':'c1','clip2':'c2','vae':'v','checkpoint':'cp'}
        for ident in [i for i in musica.MODELOS if not musica.MODELOS[i].get('plenio')]:  # YuE2 vai pelo Plenio, sem este grafo
            p=app.PedidoGeracao(modelo='musica',modelo_musica=ident,prompt='Estilo exato',letra_musica='Letra exata',vocal_musica=True,duracao_musica=30)
            g=musica.grafo(p,42,pesos)
            self.assertEqual(g['latente']['inputs']['seconds'],['cond_musica',1] if ident == 'minimax-music3' else 30)
            if ident == 'minimax-music3':self.assertEqual(g['cond_musica']['inputs']['max_duration'],30)
            self.assertEqual(g['salva']['inputs']['audio'],['audio_musica',0])
            if ident != 'stable-audio3':self.assertEqual(g['cond_musica']['inputs']['lyrics'],'Letra exata')
            else:self.assertEqual(g['pos']['inputs']['text'],'Estilo exato')
    def test_instrumental_nao_envia_letra_antiga(self):
        p=app.PedidoGeracao(modelo='musica',prompt='Instrumental',letra_musica='Texto antigo',vocal_musica=False)
        g=musica.grafo(p,42,{'unet':'u','clip':'c','vae':'v'})
        estrutura=g['cond_musica']['inputs']['lyrics']
        self.assertIn('[Instrumental]',estrutura)
        self.assertIn('[Outro]',estrutura)
        self.assertNotIn('Texto antigo',estrutura)
    def test_ausencia_de_pesos_impede_disponibilidade(self):
        for ident in musica.MODELOS:self.assertFalse(musica.resolver({},ident)['disponivel'])
    def test_stable_recusa_vocal_antes_da_fila(self):
        cfg={'id':'stable-audio3','disponivel':True,'maximo':380,'letra':False}
        with patch.object(musica,'catalogo',new=AsyncMock(return_value=[cfg])):
            with self.assertRaises(app.HTTPException) as e:asyncio.run(app.gerar(app.PedidoGeracao(modelo='musica',modelo_musica='stable-audio3',prompt='Rock',vocal_musica=True,letra_musica='Letra')))
        self.assertEqual(e.exception.status_code,400)
    def test_limite_duracao_modelo(self):
        cfg={'id':'stable-audio3','disponivel':True,'maximo':380,'letra':False}
        with patch.object(musica,'catalogo',new=AsyncMock(return_value=[cfg])):
            with self.assertRaises(app.HTTPException):asyncio.run(app.gerar(app.PedidoGeracao(modelo='musica',modelo_musica='stable-audio3',prompt='Rock',duracao_musica=381)))
if __name__=='__main__':unittest.main()
