import { useEffect, useState } from 'react'
import AbaNodes from './AbaNodes'
import PainelAndamento from '../PainelAndamento'
import { useSoltarNaCaixa, useTarefas } from './comum'
import { api, type GeradorVideo, type Modelo, type ModeloNuvem } from '../api'
import TelaModelos from '../TelaModelos'
import AbaApps from './AbaApps'
import AbaAssets from './AbaAssets'
import BotaoAtualizar from './BotaoAtualizar'
import MedidorRecursos from './MedidorRecursos'
import MenuEstudios, { ESTUDIOS } from './MenuEstudios'
import AbaCinema from './AbaCinema'
import AbaGenjutsu from './AbaGenjutsu'
import AbaImagem from './AbaImagem'
import AbaLipSync, { type ModeloLipSync } from './AbaLipSync'
import AbaLTX from './AbaLTX'
import { AbaFlux3, AbaH3, AbaWan } from './EstudiosModelo'
import AbaMusica from './AbaMusica'
import AbaVideo from './AbaVideo'
import AbaVoz from './AbaVoz'
import { CHAVE_OCULTAR, MotorCtx } from './motor'
import ContaApi from './ContaApi'
import PainelConta from './PainelConta'
import Visualizador from './Visualizador'
import './estudio.css'

// The new front door, Higgsfield-style: a top bar of modes, the Comfy Cloud
// balance and Models. Where each generation runs is picked in the model menus. "Advanced" is ComfyUI itself,
// with its node editor.

type Aba = 'image' | 'video' | 'ltx' | 'h3' | 'wan' | 'flux3' | 'lipsync' | 'music' | 'voice' | 'cinema' | 'genjutsu' | 'apps' | 'assets' | 'advanced'

const ABAS: { id: Aba; rotulo: string; breve?: boolean }[] = [
  { id: 'image', rotulo: 'Image' },
  { id: 'video', rotulo: 'Video' },
  { id: 'ltx', rotulo: 'LTX Studio' },
  { id: 'h3', rotulo: 'MiniMax H3 Studio' },
  { id: 'wan', rotulo: 'Wan Studio' },
  { id: 'flux3', rotulo: 'FLUX 3 Studio' },
  { id: 'apps', rotulo: 'VFX Studio' },
  { id: 'lipsync', rotulo: 'Lip Sync' },
  { id: 'music', rotulo: 'Music' },
  { id: 'voice', rotulo: 'Voice' },
  { id: 'cinema', rotulo: 'Cinema Studio' },
  { id: 'genjutsu', rotulo: 'Genjutsu' },
  { id: 'assets', rotulo: 'Assets' },
  { id: 'advanced', rotulo: 'Advanced' },
]

function lerAba(): Aba {
  const h = location.hash.replace('#', '').split('/')[0] as Aba
  return ABAS.some((a) => a.id === h) ? h : 'image'
}

export default function Estudio() {
  const [aba, setAba] = useState<Aba>(lerAba)
  const [modelos, setModelos] = useState<Modelo[]>([])
  const [apiImagem, setApiImagem] = useState<ModeloNuvem[]>([])
  const [geradores, setGeradores] = useState<GeradorVideo[]>([])
  const [lipsyncApi, setLipsyncApi] = useState<ModeloLipSync[]>([])
  const [soAbertos, setSoAbertos] = useState(true)
  const [naNuvem, setNaNuvem] = useState(false)
  const [verModelos, setVerModelos] = useState<false | 'api' | 'locais'>(false)
  const [versao, setVersao] = useState(0)
  // Reloads the catalog WITHOUT remounting the tabs (switching engine keeps the prompt).
  const [recarga, setRecarga] = useState(0)
  const [temChave, setTemChave] = useState(false)
  // Installed packages: the "Local" group of each model menu lists only these.
  const [instalados, setInstalados] = useState<Set<string> | undefined>()
  const [ocultar, setOcultar] = useState(() => { try { return localStorage.getItem(CHAVE_OCULTAR) === '1' } catch { return false } })
  const mudarOcultar = (v: boolean) => { setOcultar(v); try { localStorage.setItem(CHAVE_OCULTAR, v ? '1' : '0') } catch { /* private window */ } }
  const [linkRecarga, setLinkRecarga] = useState<string | undefined>()

  useEffect(() => {
    const ao = () => setAba(lerAba())
    window.addEventListener('hashchange', ao)
    return () => window.removeEventListener('hashchange', ao)
  }, [])

  useEffect(() => {
    const ao = (e: Event) => { setNaNuvem((e as CustomEvent).detail === 'nuvem'); setRecarga((r) => r + 1) }
    window.addEventListener('motor-trocado', ao)
    return () => window.removeEventListener('motor-trocado', ao)
  }, [])

  useEffect(() => {
    api.modelos().then((d) => {
      setModelos(d.modelos); setApiImagem(d.nuvem ?? [])
      // Os de API da interface antiga (MiniMax API, Wan 3.0) + os da lista nova (Kling, Veo, Seedance, Runway, Luma).
      const extras = ((d as unknown as { video_api?: GeradorVideo[] }).video_api ?? [])
      setGeradores([...(d.video?.geradores ?? []), ...extras])
      setLipsyncApi((d as unknown as { lipsync_api?: ModeloLipSync[] }).lipsync_api ?? [])
    }).catch(() => {})
    fetch('/api/motor').then((r) => r.json()).then((m) => {
      setNaNuvem(m.modo === 'nuvem'); setSoAbertos(m.so_abertos !== false)
      setTemChave(!!m.chave_nuvem); setLinkRecarga(m.link_recarga)
    }).catch(() => {})
    fetch('/api/pacotes').then((r) => r.json()).then((d) => {
      const lista: { id: string; pronto: boolean | null }[] = d.pacotes ?? d
      setInstalados(new Set(lista.filter((p) => p.pronto).map((p) => p.id)))
    }).catch(() => {})
  }, [versao, recarga])

  // A geracao em curso (local ou na nuvem) aparece no topo, com etapa e passos.
  const tarefas = useTarefas(true)
  // Arrastar da galeria (ou do computador) para qualquer caixa de prompt.
  useSoltarNaCaixa()
  const ATIVOS = ['preparando', 'submetendo', 'executando']
  const ativa = tarefas.find((t) => ATIVOS.includes(t.estado)) ?? tarefas.find((t) => t.estado === 'na_fila')
  const ir = (a: Aba) => { location.hash = a; setAba(a) }

  return (
    <MotorCtx.Provider value={{ naNuvem, temChave, instalados, ocultarNaoInstalados: ocultar }}>
    <div className="hf">
      <header className="hf-topo">
        {/* Assinatura horizontal aprovada (nome em curvas dentro do SVG). Em tela estreita fica so o simbolo. */}
        {/* Esquerda: a marca e, ao lado, o medidor de RAM/VRAM (a direita fica so com conta e config). */}
        <div className="hf-esquerda">
          <a className="hf-marca" href="#image" onClick={() => ir('image')} aria-label="EasyComfee home">
            <img className="hf-marca-completa" src="/brand/easycomfee-logo-horizontal.svg?v=5" alt="" />
            <img className="hf-marca-simbolo" src="/brand/easycomfee-symbol.svg" alt="" />
          </a>
          <MedidorRecursos />
        </div>
        <nav className="hf-nav">
          {/* Os estudios ficam no botao Studios (MenuEstudios), logo depois de Video. */}
          {ABAS.filter((a) => !ESTUDIOS.some((e) => e.id === a.id)).map((a) => (
            <span key={a.id} style={{ display: 'contents' }}>
              <button data-ativo={aba === a.id} onClick={() => ir(a.id)}>
                {a.rotulo}{a.breve && <sup>soon</sup>}
              </button>
              {a.id === 'video' && <MenuEstudios aba={aba} ir={(id) => ir(id as Aba)} />}
            </span>
          ))}
        </nav>
        <div className="hf-direita">
          {ativa && <PainelAndamento key={ativa.id} tarefa={ativa}
            naFila={tarefas.filter((t) => t.estado === 'na_fila' && t.id !== ativa.id).length} />}
<BotaoAtualizar />
          <PainelConta temChave={temChave} linkRecarga={linkRecarga} abrirConfig={() => setVerModelos('api')} />
          <button className="hf-botao-modelos" onClick={() => setVerModelos('locais')}>Config Models</button>
        </div>
      </header>

      <main className={aba === 'advanced' ? 'hf-avancado' : 'hf-corpo'}>
        {aba === 'image' && <AbaImagem key={versao} modelos={modelos} apiModelos={soAbertos ? [] : apiImagem} naNuvem={naNuvem} />}
        {aba === 'video' && <AbaVideo key={versao} apiGeradores={soAbertos ? [] : geradores.filter((g) => g.nuvem)} naNuvem={naNuvem} />}
        {aba === 'ltx' && <AbaLTX />}
        {aba === 'h3' && <AbaH3 />}
        {aba === 'wan' && <AbaWan />}
        {aba === 'flux3' && <AbaFlux3 />}
        {aba === 'cinema' && <AbaCinema key={versao} modelos={modelos} apiModelos={soAbertos ? [] : apiImagem}
          apiGeradores={soAbertos ? [] : geradores.filter((g) => g.nuvem)} naNuvem={naNuvem} />}
        {aba === 'genjutsu' && <AbaGenjutsu key={versao} apiLiberado={!soAbertos} />}
        {aba === 'apps' && <AbaApps key={versao} naNuvem={naNuvem} />}
        {aba === 'lipsync' && <AbaLipSync key={versao} apiModelos={soAbertos ? [] : lipsyncApi} />}
        {aba === 'music' && <AbaMusica key={versao} />}
        {aba === 'voice' && <AbaVoz key={versao} naNuvem={naNuvem} />}
        {aba === 'assets' && <AbaAssets />}
        {aba === 'advanced' && <AbaNodes />}
      </main>

      <Visualizador />
      {verModelos && <TelaModelos abaInicial={verModelos}
        topoLocais={<label className="mq-check"><input type="checkbox" checked={ocultar} onChange={(e) => mudarOcultar(e.target.checked)} />
          <span>Hide the models that are not installed from the model menus (otherwise they show greyed out).</span></label>} fechar={() => { setVerModelos(false); setVersao((v) => v + 1) }}
        conta={<ContaApi temChave={temChave} soAbertos={soAbertos} linkRecarga={linkRecarga} aoMudar={() => setRecarga((r) => r + 1)} />} />}
    </div>
    </MotorCtx.Provider>
  )
}
