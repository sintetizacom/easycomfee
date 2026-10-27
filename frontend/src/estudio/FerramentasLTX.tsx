import { useRef, useState } from 'react'
import { api, urlImagem, type Referencia } from '../api'
import { BotaoGerar, CartaoTarefa, Chips, SlotImagem, TIPO_GALERIA, arquivos, mensagem, referenciaDe, useCusto, useTarefas, Galeria } from './comum'

// Telas proprias do LTX Studio (#ltx/<ferramenta>): Keyframes com linha do
// tempo, Ingredients e Latent upscale. Antes as duas ultimas so existiam no
// editor antigo (aba Advanced).

export const FERRAMENTAS = ['chaves', 'ingredientes', 'ampliar'] as const
export type Ferramenta = typeof FERRAMENTAS[number]

function Voltar() {
  return <a className="hf-ltx-voltar" href="#ltx">← LTX Studio</a>
}

// ---------- Keyframes ----------

type Chave = { id: number; img: Referencia; seg: number }
// O modelo encaixa cada imagem em passos de 1/3 s (8 quadros a 24 fps).
const passo = (s: number) => Math.round(s * 3) / 3
const rotuloSeg = (s: number) => `${s.toFixed(s % 1 ? 1 : 0)}s`

function Keyframes() {
  const tarefas = useTarefas()
  const [duracao, setDuracao] = useState(8)
  const [chaves, setChaves] = useState<Chave[]>([])
  const [prompt, setPrompt] = useState('')
  const [proporcao, setProporcao] = useState('16:9')
  const [audio, setAudio] = useState(true)
  const [forca, setForca] = useState(0.7)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const trilha = useRef<HTMLDivElement>(null)
  const seletor = useRef<HTMLInputElement>(null)
  const segNovo = useRef(0)
  const proximo = useRef(1)

  const segDoPonto = (x: number) => {
    const r = trilha.current!.getBoundingClientRect()
    return passo(Math.max(0, Math.min(1, (x - r.left) / r.width)) * duracao)
  }
  // Arquivos do computador ou uma imagem arrastada da galeria.
  const adicionar = async (arqs: (File | { nome: string; subpasta: string })[], seg: number) => {
    const fotos = arqs.filter((f) => !(f instanceof File) || f.type.startsWith('image/')).slice(0, 8 - chaves.length)
    if (!fotos.length) return
    setEnviando(true); setErro(null)
    try {
      const novas = await Promise.all(fotos.map((f) => referenciaDe(f)))
      setChaves((a) => [...a, ...novas.map((img, i) => ({ id: proximo.current++, img, seg: Math.min(duracao, passo(seg + i)) }))])
    } catch (e) { setErro(mensagem(e)) } finally { setEnviando(false) }
  }
  // Clicar num ponto vazio da trilha abre o seletor de imagem para aquele segundo.
  const clicarTrilha = (e: React.MouseEvent) => {
    if (e.target !== trilha.current || chaves.length >= 8) return
    segNovo.current = segDoPonto(e.clientX)
    seletor.current?.click()
  }
  const arrastar = (id: number) => (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('button')) return
    e.preventDefault()
    const mover = (ev: PointerEvent) => setChaves((a) => a.map((c) => (c.id === id ? { ...c, seg: segDoPonto(ev.clientX) } : c)))
    const soltar = () => { window.removeEventListener('pointermove', mover); window.removeEventListener('pointerup', soltar) }
    window.addEventListener('pointermove', mover)
    window.addEventListener('pointerup', soltar)
  }

  const ordem = chaves.map((c) => ({ ...c, seg: Math.min(c.seg, duracao) })).sort((x, y) => x.seg - y.seg)
  // Duas imagens no mesmo instante: o backend fica com uma so; avisa antes.
  const repetidas = ordem.some((c, i) => i > 0 && Math.round(c.seg * 24) === Math.round(ordem[i - 1].seg * 24))
  const pedido = {
    modelo: 'video', modelo_video: 'ltx', modo_video: 'chaves', prompt: prompt || 'x', proporcao: '1:1',
    proporcao_video: proporcao, resolucao_video: '720p', duracao_video: duracao, com_audio: audio,
    referencias: ordem.length >= 2 ? ordem.map((c) => c.img.nome) : ['a.png', 'b.png'],
  }
  const custo = useCusto(pedido)
  const gerar = async () => {
    setErro(null)
    try {
      await api.gerar({ ...pedido, prompt,
        quadros_referencias: ordem.map((c) => Math.round(c.seg * 24) + 1), forca_chaves: forca,
      } as Parameters<typeof api.gerar>[0])
    } catch (e) { setErro(mensagem(e)) }
  }

  const marcas = Array.from({ length: duracao + 1 }, (_, i) => i)
  const minhas = tarefas.filter((t) => t.modelo === 'video' && t.modelo_video === 'ltx')

  return (
    <div className="hf-aba hf-ltx">
      <Voltar />
      <div className="hf-heroi">
        <span className="hf-sobretitulo">LTX 2.5 · KEYFRAMES</span>
        <h1>Pin images to the timeline</h1>
        <p className="hf-dica">Drop 2 to 8 images on the timeline, each at the second it should appear. Drag them to move. LTX animates the way between them.</p>
      </div>

      <div className="hf-barra-prompt">
        <div className="hf-kf">
          <div className="hf-kf-regua">
            {marcas.map((s) => <span key={s} style={{ left: `${(s / duracao) * 100}%` }}>{s}s</span>)}
          </div>
          <div ref={trilha} className="hf-kf-trilha" data-vazia={chaves.length === 0}
            onClick={clicarTrilha}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              const daGaleria = e.dataTransfer.getData(TIPO_GALERIA)
              adicionar(daGaleria ? [JSON.parse(daGaleria)] : Array.from(e.dataTransfer.files), segDoPonto(e.clientX))
            }}>
            {chaves.length === 0 && <span className="hf-kf-vazio">{enviando ? 'Uploading…' : 'Click the timeline or drop images here (from your computer or the gallery)'}</span>}
            {ordem.map((c, i) => (
              <div key={c.id} className="hf-kf-chave" style={{ left: `${(c.seg / duracao) * 100}%` }} onPointerDown={arrastar(c.id)}>
                <img src={c.img.url} alt="" draggable={false} />
                <small>{i + 1} · {rotuloSeg(c.seg)}</small>
                <button type="button" className="hf-slot-x" onClick={() => setChaves((a) => a.filter((x) => x.id !== c.id))}>×</button>
              </div>
            ))}
          </div>
          <input ref={seletor} type="file" accept="image/*" multiple hidden
            onChange={(e) => { adicionar(Array.from(e.target.files ?? []), segNovo.current); e.target.value = '' }} />
          <div className="hf-linha-controles">
            {chaves.length < 8 && (
              <button type="button" className="hf-botao-sec" onClick={() => {
                segNovo.current = chaves.length ? Math.min(duracao, passo(Math.max(...chaves.map((c) => c.seg)) + 2)) : 0
                seletor.current?.click()
              }}>+ Add image</button>
            )}
            <label className="hf-duracao">Length {duracao}s
              <input type="range" min={2} max={15} value={duracao} onChange={(e) => setDuracao(Number(e.target.value))} />
            </label>
            <label className="hf-ctrl hf-ctrl-largo" title="How strictly the video matches each image. Lower lets the motion flow more freely between them.">
              <small>Keyframe strength · {Math.round(forca * 100)}%</small>
              <input type="range" min={0.3} max={1} step={0.05} value={forca} onChange={(e) => setForca(Number(e.target.value))} />
            </label>
          </div>
          {repetidas && <p className="hf-erro">Two images are at the same moment: move one of them.</p>}
          <p className="hf-dica">Neighbouring images should share a similar point of view; very different ones blend into each other.</p>
        </div>

        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2}
          placeholder="What happens between the images: motion, camera, sound…" />
        <div className="hf-linha-controles">
          <Chips rotulo="Aspect ratio" opcoes={['16:9', '9:16', '1:1'].map((p) => ({ id: p, rotulo: p }))} valor={proporcao} aoMudar={setProporcao} />
          <label className="hf-toggle"><input type="checkbox" checked={audio} onChange={(e) => setAudio(e.target.checked)} /> Audio</label>
          <BotaoGerar est={custo} desligado={!prompt.trim() || ordem.length < 2 || repetidas} aoClicar={gerar} />
        </div>
        {erro && <p className="hf-erro">{erro}</p>}
      </div>

      <Galeria tipo="video">
        {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
      </Galeria>
    </div>
  )
}

// ---------- Ingredients ----------

const POSICOES: Record<string, string[]> = {
  '16:9': ['left', 'center-left', 'center-right', 'right'],
  '9:16': ['top', 'upper middle', 'lower middle', 'bottom'],
}

function Ingredientes() {
  const tarefas = useTarefas()
  const [imgs, setImgs] = useState<Referencia[]>([])
  const [prompt, setPrompt] = useState('')
  const [proporcao, setProporcao] = useState('16:9')
  const [duracao, setDuracao] = useState(5)
  const [erro, setErro] = useState<string | null>(null)

  // Na folha, 2 imagens ficam em "left/right"; 3 ou 4 usam as posicoes do meio.
  const posicoes = (POSICOES[proporcao] ?? POSICOES['16:9'])
  const ondeFica = (i: number) => imgs.length <= 2 ? [posicoes[0], posicoes[3]][i] ?? posicoes[0] : imgs.length === 3 ? [posicoes[0], 'center', posicoes[3]][i] : posicoes[i]

  const pedido = {
    modelo: 'video', modelo_video: 'ltx', modo_video: 'ingredientes', prompt: prompt || 'x', proporcao: '1:1',
    proporcao_video: proporcao, resolucao_video: '720p', duracao_video: duracao, com_audio: false,
    referencias: imgs.length ? imgs.map((r) => r.nome) : ['a.png'],
  }
  const custo = useCusto(pedido)
  const gerar = async () => {
    setErro(null)
    try { await api.gerar({ ...pedido, prompt } as Parameters<typeof api.gerar>[0]) } catch (e) { setErro(mensagem(e)) }
  }
  const minhas = tarefas.filter((t) => t.modelo === 'video' && t.modelo_video === 'ltx')

  return (
    <div className="hf-aba hf-ltx">
      <Voltar />
      <div className="hf-heroi">
        <span className="hf-sobretitulo">LTX 2.5 · INGREDIENTS · LOCAL GPU</span>
        <h1>One shot from several ingredients</h1>
        <p className="hf-dica">1 to 4 images (a person, an object, a place…) become a reference sheet, and LTX builds one shot that combines them.</p>
      </div>

      <div className="hf-barra-prompt">
        <div className="hf-slots">
          {imgs.map((r, i) => (
            <div key={r.nome + i} className="hf-ingrediente">
              <SlotImagem rotulo={`Ingredient ${i + 1}`} valor={r}
                aoMudar={(n) => setImgs((a) => n ? a.map((x, j) => (j === i ? n : x)) : a.filter((_, j) => j !== i))} />
              {imgs.length > 1 && <small>{ondeFica(i)} of the sheet</small>}
            </div>
          ))}
          {imgs.length < 4 && (
            <SlotImagem key={`novo${imgs.length}`} rotulo={imgs.length ? 'Ingredient' : 'Person, object or place'}
              valor={null} aoMudar={(n) => n && setImgs((a) => [...a, n])} />
          )}
        </div>
        <p className="hf-dica">Name each image by its place on the sheet, in English — e.g. “the woman from the left of the reference sheet walks along the street shown on the right of the sheet”. Writing “image 1” makes the model animate the sheet itself.</p>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2}
          placeholder="the man from the left of the reference sheet rides the red bike from the right of the sheet…" />
        <div className="hf-linha-controles">
          <Chips rotulo="Aspect ratio" opcoes={['16:9', '9:16'].map((p) => ({ id: p, rotulo: p }))} valor={proporcao} aoMudar={setProporcao} />
          <label className="hf-duracao">{duracao}s
            <input type="range" min={2} max={8} value={duracao} onChange={(e) => setDuracao(Number(e.target.value))} />
          </label>
          <BotaoGerar est={custo} desligado={!prompt.trim() || !imgs.length} aoClicar={gerar} />
        </div>
        {erro && <p className="hf-erro">{erro}</p>}
      </div>

      <Galeria tipo="video">
        {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
      </Galeria>
    </div>
  )
}

// ---------- Latent upscale ----------

type Escolhido = { ref: string; url: string; rotulo: string }

function Ampliar() {
  const tarefas = useTarefas()
  const [video, setVideo] = useState<Escolhido | null>(null)
  const [metodo, setMetodo] = useState('ltx')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  // Videos prontos da galeria, os mais novos primeiro.
  const recentes = tarefas.filter((t) => t.estado === 'pronto' && t.modelo !== 'limpar_video')
    .flatMap((t) => arquivos(t).filter((a) => /\.(mp4|webm|mov)$/i.test(a.nome)).map((a) => ({ ...a, t })))
    .slice(0, 12)

  const pedido = video ? { modelo: 'limpar_video', prompt: '', proporcao: '1:1', metodo_video: metodo,
    resolucao_limpeza: 1440, referencias: [video.ref] } : null
  const custo = useCusto(pedido)
  const ampliar = async () => {
    if (!pedido) return
    setErro(null)
    try { await api.gerar(pedido as Parameters<typeof api.gerar>[0]) } catch (e) { setErro(mensagem(e)) }
  }
  const minhas = tarefas.filter((t) => t.modelo === 'limpar_video')

  return (
    <div className="hf-aba hf-ltx">
      <Voltar />
      <div className="hf-heroi">
        <span className="hf-sobretitulo">LTX 2.5 · UPSCALE · LOCAL GPU</span>
        <h1>Make any video sharper and bigger</h1>
        <p className="hf-dica">Pick a video you made or upload one. Its sound is kept.</p>
      </div>

      <div className="hf-barra-prompt">
        <div className="hf-slots">
          <label className="hf-slot" data-cheio={!!video}>
            {video ? <video src={video.url} muted loop autoPlay playsInline /> : <span>{enviando ? 'Uploading…' : '+ Upload video'}</span>}
            {video && <button type="button" className="hf-slot-x" onClick={(e) => { e.preventDefault(); setVideo(null) }}>×</button>}
            <input type="file" accept="video/*" hidden onChange={async (e) => {
              const f = e.target.files?.[0]
              if (!f) return
              setEnviando(true); setErro(null)
              try { const r = await api.enviarReferencia(f); setVideo({ ref: `entrada:${r.nome}`, url: r.url, rotulo: f.name }) }
              catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
            }} />
          </label>
        </div>
        {recentes.length > 0 && (
          <>
            <span className="hf-grupo-rotulo">Or pick one of your videos</span>
            <div className="hf-ampliar-lista">
              {recentes.map((a) => {
                const ref = `${a.subpasta}/${a.nome}`
                return (
                  <button key={ref} type="button" data-ativo={video?.ref === ref}
                    onClick={() => setVideo({ ref, url: urlImagem(a), rotulo: a.t.prompt })}>
                    <video src={urlImagem(a)} muted preload="metadata" />
                  </button>
                )
              })}
            </div>
          </>
        )}
        <div className="hf-linha-controles">
          <Chips rotulo="Method" opcoes={[
            { id: 'ltx', rotulo: 'Latent · LTX', dica: 'Understands motion and can reinterpret the scene. May soften faces.' },
            { id: 'seedvr', rotulo: 'Pixels · SeedVR2', dica: 'Faithful to the original. Best for faces.' },
          ]} valor={metodo} aoMudar={setMetodo} />
          <BotaoGerar rotulo="Upscale ✦" est={custo} desligado={!video} aoClicar={ampliar} />
        </div>
        <p className="hf-dica">{metodo === 'ltx' ? 'Latent: LTX re-renders the clip at twice the size, keeping the motion. Faces may change a little.' : 'Pixels: sharpens and enlarges without changing what is in the shot.'}</p>
        {erro && <p className="hf-erro">{erro}</p>}
      </div>

      <Galeria tipo="video">
        {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
      </Galeria>
    </div>
  )
}

export default function FerramentaLTX({ id }: { id: Ferramenta }) {
  return id === 'chaves' ? <Keyframes /> : id === 'ingredientes' ? <Ingredientes /> : <Ampliar />
}
