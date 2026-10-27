import { useEffect, useState } from 'react'
import { urlImagem, type ItemGaleria } from '../api'
import { eAudio, eVideo } from './comum'

// Full-size viewer for every generated file of the new studio, local or cloud.
// Any <Midia> opens it; the arrows walk through the files on the page, in the
// order they appear. On the side: what the file is, how it was made, and
// actions to download it or reuse its prompt.

type Arquivo = { nome: string; subpasta: string }

/** Opens the viewer on this file, with every file on the page as its neighbours. */
export function abrirVisualizador(atual: Arquivo) {
  const lista: Arquivo[] = [...document.querySelectorAll<HTMLElement>('[data-midia]')]
    .map((e) => ({ nome: e.dataset.nome!, subpasta: e.dataset.subpasta! }))
    .filter((a, i, todos) => todos.findIndex((b) => b.nome === a.nome && b.subpasta === a.subpasta) === i)
  const indice = Math.max(0, lista.findIndex((a) => a.nome === atual.nome && a.subpasta === atual.subpasta))
  window.dispatchEvent(new CustomEvent('abrir-visualizador', { detail: { lista: lista.length ? lista : [atual], indice } }))
}

/** Sends a prompt back to the tab that is open (each tab listens with useReusarPrompt). */
export function reusarPrompt(prompt: string) {
  window.dispatchEvent(new CustomEvent('reusar-prompt', { detail: prompt }))
}

export function useReusarPrompt(aoReusar: (prompt: string) => void) {
  useEffect(() => {
    const ao = (e: Event) => aoReusar((e as CustomEvent<string>).detail)
    window.addEventListener('reusar-prompt', ao)
    return () => window.removeEventListener('reusar-prompt', ao)
  }, [aoReusar])
}

const tamanho = (b?: number) => !b ? '—' : b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1)} MB`
const tempo = (s?: number) => !s ? '—' : s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`
const quando = (t?: number) => !t ? '—' : new Date(t * 1000).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

// Readable names for the ids saved with each file. Unknown ids show as saved.
const NOMES: Record<string, string> = {
  ltx: 'LTX 2.5', ltx23: 'LTX 2.3', minimax: 'MiniMax H3', krea: 'Krea 2 Turbo', kroma: 'Kroma', qwen21: 'Qwen Image 2.1',
  klein: 'Flux 2 Klein 9B', flux3: 'Flux 3 Klein', zimage: 'Z-Image Turbo', mage: 'Mage Flow', ideogram: 'Ideogram 4',
  transformar_video: 'LTX VFX app', video: 'Video', musica: 'Music', voz: 'Voice', avatar: 'Lip sync', genjutsu: 'Genjutsu',
  trocar: 'Flux 2 Klein · swap', flux3ref: 'Flux 3 · references', qwen21edit: 'Qwen 2.1 · edit', instrucao: 'Mage · edit', qwen: 'Qwen Image Edit',
}
const EFEITOS: Record<string, string> = { noite: 'Day → Night', limpar: 'Remove people', agua: 'Add water', trocar: 'Swap character',
  expandir: 'Expand frame', cor: 'Colorize', nitidez: 'Unblur', restaurar: 'Restore', maquete: '3D render → Video' }
const nome = (id?: unknown) => (id ? NOMES[String(id)] ?? String(id) : '')

const MODOS: Record<string, string> = { texto: 'Text to video', imagem: 'Image to video', primeiro_ultimo: 'First & last frame', referencia: 'References to video' }

function Linha({ rotulo, valor }: { rotulo: string; valor?: string | number | null }) {
  if (valor === undefined || valor === null || valor === '') return null
  return <div className="hf-vis-linha"><span>{rotulo}</span><b>{valor}</b></div>
}

export default function Visualizador() {
  const [lista, setLista] = useState<Arquivo[]>([])
  const [i, setI] = useState(0)
  const [info, setInfo] = useState<ItemGaleria | null>(null)
  const [copiado, setCopiado] = useState('')
  const atual = lista[i]

  useEffect(() => {
    const ao = (e: Event) => { const d = (e as CustomEvent).detail; setLista(d.lista); setI(d.indice) }
    window.addEventListener('abrir-visualizador', ao)
    return () => window.removeEventListener('abrir-visualizador', ao)
  }, [])

  useEffect(() => {
    if (!atual) return
    setInfo(null); setCopiado('')
    fetch(`/api/galeria/arquivo?subpasta=${encodeURIComponent(atual.subpasta)}&nome=${encodeURIComponent(atual.nome)}`)
      .then((r) => (r.ok ? r.json() : null)).then(setInfo).catch(() => setInfo(null))
  }, [atual?.nome, atual?.subpasta])

  useEffect(() => {
    if (!atual) return
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLista([])
      if (e.key === 'ArrowRight') setI((x) => Math.min(lista.length - 1, x + 1))
      if (e.key === 'ArrowLeft') setI((x) => Math.max(0, x - 1))
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [atual, lista.length])

  if (!atual) return null
  const url = urlImagem({ nome: atual.nome, subpasta: atual.subpasta })
  const p = (info?.parametros ?? {}) as Record<string, unknown>
  const prompt = info?.prompt || info?.prompt_final || ''
  const copiar = async (texto: string, qual: string) => {
    try { await navigator.clipboard.writeText(texto); setCopiado(qual) } catch { setCopiado('') }
  }
  const resumo = [
    `File: ${atual.subpasta}/${atual.nome}`,
    info && `Model: ${info.rotulo || info.modelo}${p.modelo_video ? ` (${p.modelo_video})` : ''}`,
    info?.largura ? `Size: ${info.largura} × ${info.altura}` : '',
    p.seed !== undefined ? `Seed: ${p.seed}` : '',
    prompt && `Prompt: ${prompt}`,
  ].filter(Boolean).join('\n')

  return (
    <div className="hf-vis-fundo" onClick={() => setLista([])}>
      <div className="hf-vis" role="dialog" aria-label="Viewer" onClick={(e) => e.stopPropagation()}>
        <div className="hf-vis-palco">
          {i > 0 && <button className="hf-vis-seta" data-lado="esq" onClick={() => setI(i - 1)} aria-label="Previous">‹</button>}
          {eVideo(atual.nome) ? <video key={url} src={url} controls autoPlay loop playsInline />
            : eAudio(atual.nome) ? <audio key={url} src={url} controls autoPlay />
              : <img src={url} alt="" />}
          {i < lista.length - 1 && <button className="hf-vis-seta" data-lado="dir" onClick={() => setI(i + 1)} aria-label="Next">›</button>}
          {lista.length > 1 && <span className="hf-vis-conta">{i + 1} / {lista.length}</span>}
        </div>
        <aside className="hf-vis-lado">
          <button className="hf-vis-fechar" onClick={() => setLista([])} aria-label="Close">×</button>
          <span className="hf-vis-titulo">Details</span>
          {info ? <>
            <Linha rotulo="Resolution" valor={info.largura ? `${info.largura} × ${info.altura} · ${((info.largura * info.altura) / 1e6).toFixed(1)} MP` : null} />
            <Linha rotulo="Length" valor={info.duracao_video ? `${info.duracao_video.toFixed(2)} s${info.fps ? ` · ${info.fps} fps` : ''}` : null} />
            <Linha rotulo="Generation time" valor={tempo(info.duracao)} />
            <Linha rotulo="File" valor={tamanho(info.bytes)} />
            <Linha rotulo="Created" valor={quando(info.criada_em)} />
            <Linha rotulo="Cost" valor={info.custo_usd ? `$${info.custo_usd.toFixed(3)}` : atual.nome.startsWith('nuvem_') ? 'Comfy credits' : 'Free (your GPU)'} />
            <hr />
            <Linha rotulo="Model" valor={info.modelo === 'video' ? nome(p.modelo_video) : (!info.teste && info.rotulo) || nome(info.modelo)} />
            <Linha rotulo="Effect" valor={info.modelo === 'transformar_video' && p.efeito_video ? EFEITOS[String(p.efeito_video)] ?? String(p.efeito_video) : null} />
            <Linha rotulo="Mode" valor={info.modelo === 'video' && p.modo_video ? MODOS[String(p.modo_video)] ?? String(p.modo_video) : null} />
            <Linha rotulo="Seed" valor={p.seed !== undefined ? String(p.seed) : null} />
            <Linha rotulo="Aspect" valor={(p.proporcao_video ?? p.proporcao) as string} />
            <Linha rotulo="Sound" valor={p.com_audio === undefined || !eVideo(atual.nome) ? null : p.com_audio ? 'yes' : 'no'} />
            {prompt && <>
              <hr />
              <span className="hf-vis-titulo">Prompt</span>
              <p className="hf-vis-prompt">{prompt}</p>
            </>}
          </> : <p className="hf-dica">No details saved for this file.</p>}
          <div className="hf-vis-acoes">
            <a className="hf-vis-botao" href={url} download={atual.nome}>⬇ Download</a>
            {prompt && <button className="hf-vis-botao" onClick={() => { reusarPrompt(prompt); setLista([]) }}>↺ Reuse prompt</button>}
            {prompt && <button className="hf-vis-botao" onClick={() => copiar(prompt, 'prompt')}>{copiado === 'prompt' ? '✓ Copied' : '⧉ Copy prompt'}</button>}
            <button className="hf-vis-botao" onClick={() => copiar(resumo, 'resumo')}>{copiado === 'resumo' ? '✓ Copied' : '⧉ Copy summary'}</button>
            <a className="hf-vis-botao" href={url} target="_blank" rel="noreferrer">↗ Open in a new tab</a>
          </div>
          <small className="hf-vis-arquivo">{atual.subpasta}/{atual.nome}</small>
        </aside>
      </div>
    </div>
  )
}
