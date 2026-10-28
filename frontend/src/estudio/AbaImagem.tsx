import { useState } from 'react'
import { useReusarPrompt } from './Visualizador'
import { api, type Elemento, type Modelo, type ModeloNuvem, type Referencia } from '../api'
import LayoutIdeogram from './LayoutIdeogram'
import { GruposAbertos, useEscolha, useValor } from './motor'
import { LOOKS, aplicarLook } from './looks'
import { BotaoGerar, CartaoTarefa, Chips, SlotImagem, mensagem, useCusto, useTarefas, Galeria, parteDoHash } from './comum'

// Image tab: one prompt bar, the model, aspect ratio and how many images.
// Everything else (steps, cfg, styles) keeps its defaults; the full controls
// live in the Advanced tab.

const PROPORCOES = ['1:1', '4:5', '2:3', '9:16', '3:2', '16:9']

// English blurbs for the new studio (the backend presets keep the Portuguese ones).
const DESCRICOES: Record<string, string> = {
  krea: 'Photorealism. Fast. The default for most images.',
  kroma: 'Illustration and anime, a fine-tune of Krea 2.',
  qwen21: 'Text inside the scene, very accurate. The only local model with native 2K.',
  klein: 'Maximum micro-detail and texture. Slower.',
  flux3: 'The new BFL model. Photorealism and well-written text.',
  zimage: 'Fast drafts. Supports ControlNet.',
  mage: 'Lightweight. The base of instruction editing.',
  ideogram: 'Typography and layout controlled with boxes.',
  flux1dev: 'The classic FLUX.1, 20 steps. Non-commercial license.',
  flux1krea: 'FLUX.1 tuned by Krea: natural photos that look less like AI.',
  flux2dev: 'FLUX.2 (32B): very detailed and very heavy. Best on Comfy Cloud.',
  hidream: 'HiDream I1 Fast: follows long prompts closely. 16 steps.',
  chroma: 'Chroma1 HD: open FLUX-based model (Apache 2.0) for any style.',
  sd35l: 'Stable Diffusion 3.5 Large (8B): good with text and composition.',
  kandinsky5i: 'Kandinsky 5 for images (Apache 2.0).',
  // Light models, for smaller graphics cards.
  flux1s: 'Light FLUX: good images in 4 steps. For 8-12 GB cards.',
  sd35m: 'Stable Diffusion 3.5 Medium. Handles text in images. For 8 GB cards.',
  sdxl: 'The classic SDXL (RealVisXL 5), photoreal. For 6-8 GB cards.',
  sd15: 'The lightest: runs on 4 GB cards. 512 px images.',
}

// Reference images per open model. With images attached, the request goes to
// the model's reference/edit mode in the backend (presets.EDICAO), or, for
// Krea and Kroma, to the generator's own character slots. "@image1" in the
// prompt is translated by the server to the label each model expects.
// Tested 23/10/2026: the edit models treat image 1 as the BASE (its size and
// scene). With the person first and the scene second, Qwen 2.1 and Flux 3
// kept the scene's original person; scene first, person second worked.
// "base" marks those models, so slot 1 is labelled "Base image".
const REFERENCIAS: Record<string, { modo: string; max: number; uso: string; base?: boolean }> = {
  krea: { modo: 'krea', max: 3, uso: 'Puts up to 3 people or characters from your images into a new scene.' },
  kroma: { modo: 'kroma', max: 3, uso: 'Puts up to 3 characters from your images into a new illustrated scene.' },
  qwen21: { modo: 'qwen21edit', max: 8, base: true, uso: 'Image 1 is the base you edit; add people or objects as image 2, 3… e.g. "put the woman from @image2 in @image1".' },
  klein: { modo: 'trocar', max: 4, base: true, uso: 'Image 1 is the scene; the others replace who or what is in it.' },
  flux3: { modo: 'flux3ref', max: 10, base: true, uso: 'Image 1 is the base you edit; add people, outfits or places as image 2, 3… (up to 10).' },
  mage: { modo: 'instrucao', max: 3, base: true, uso: 'Quick edit of image 1 from an instruction, keeping the rest intact.' },
}

// On Comfy Cloud the Krea character, Qwen 2.1 edit and Flux 3 reference modes
// are not hosted; images go through Qwen Image Edit 2511 there (open, 3 images).
const NUVEM_SEM_REF = new Set(['krea', 'kroma', 'qwen21', 'flux3'])
const REF_NUVEM = { modo: 'qwen', max: 3, base: true, uso: 'On Comfy Cloud, images go through Qwen Image Edit. Image 1 is the base; add people or objects as image 2, 3.' }

export default function AbaImagem({ modelos, apiModelos, naNuvem }: { modelos: Modelo[]; apiModelos: ModeloNuvem[]; naNuvem: boolean }) {
  const tarefas = useTarefas()
  const [prompt, setPrompt] = useState('')
  const [look, setLook] = useState('')
  // "Reuse prompt" in the viewer fills this tab's text.
  useReusarPrompt(setPrompt)
  const [modelo, setModelo] = useState(() => parteDoHash(1) || 'krea')
  const escolher = useEscolha(setModelo)
  const valorSelect = useValor(modelo, apiModelos.some((m) => m.id === modelo))
  const [proporcao, setProporcao] = useState('1:1')
  const [lote, setLote] = useState(1)
  const [refs, setRefs] = useState<Referencia[]>([])
  // Ideogram 4: optional hand-drawn layout (boxes) sent as its caption.
  const [comLayout, setComLayout] = useState(false)
  const [elementos, setElementos] = useState<Elemento[]>([])
  const [fundoLayout, setFundoLayout] = useState('')
  const [pensando, setPensando] = useState(false)
  const ehIdeogram = modelo === 'ideogram'
  const usarLayout = ehIdeogram && comLayout && elementos.length > 0
  const [erro, setErro] = useState<string | null>(null)
  const atual = modelos.find((m) => m.id === modelo)
  // Modelos de API (Nano Banana, GPT Image): rodam pelos creditos da conta Comfy.
  const apiAtual = apiModelos.find((m) => m.id === modelo)
  const niveis = apiAtual ? (apiAtual.resolucoes ?? apiAtual.niveis ?? ['1K']) : []
  const [nivel, setNivel] = useState('1K')
  const nivelOk = niveis.includes(nivel) ? nivel : niveis[0]
  const preco = (() => {
    if (!apiAtual) return null
    const v = apiAtual.preco_usd[nivelOk ?? '']
    const unit = typeof v === 'number' ? v : (v && typeof v === 'object' ? Object.values(v)[0] : undefined)
    return typeof unit === 'number' ? unit * lote : null
  })()

  const usoRefs = apiAtual
    ? { modo: modelo, max: apiAtual.max_referencias ?? 1, base: true, uso: `Image 1 is the base; edit it or combine up to ${apiAtual.max_referencias ?? 1} images.` }
    : naNuvem && NUVEM_SEM_REF.has(modelo) ? REF_NUVEM : REFERENCIAS[modelo]
  const maxRefs = usoRefs?.max ?? 0
  const refsOk = refs.slice(0, maxRefs)
  // With images, open models run in their reference/edit mode, one image per run.
  const comRefs = refsOk.length > 0
  const pedido = {
    modelo: comRefs && usoRefs ? usoRefs.modo : modelo, prompt: prompt || 'x', proporcao,
    lote: comRefs && !apiAtual ? 1 : lote, referencias: refsOk.map((r) => r.nome),
    ...(apiAtual ? { resolucao_nuvem: nivelOk } : {}),
    ...(usarLayout ? { caption: {
      aspect_ratio: proporcao,
      high_level_description: prompt,
      compositional_deconstruction: {
        background: fundoLayout || 'A clean, uncluttered background.',
        elements: elementos.map((e) => ({ type: e.tipo, bbox: e.bbox.map(Math.round), desc: e.desc,
          ...(e.tipo === 'text' ? { text: e.texto ?? '' } : {}) })),
      },
    } } : {}),
  }
  const custo = useCusto(pedido)

  // The local language model drafts the layout from the prompt; the user then adjusts the boxes.
  const sugerir = async () => {
    setErro(null); setPensando(true)
    try {
      const { caption: c } = await api.caption(prompt, proporcao)
      setFundoLayout(c.compositional_deconstruction.background)
      setElementos((c.compositional_deconstruction.elements as Record<string, unknown>[])
        .filter((e) => Array.isArray(e.bbox))
        .map((e) => ({ tipo: e.type === 'text' ? 'text' : 'obj', bbox: e.bbox as Elemento['bbox'],
          texto: (e.text as string) ?? '', desc: (e.desc as string) ?? '' })))
    } catch (e) { setErro(mensagem(e)) } finally { setPensando(false) }
  }

  const lookAtual = LOOKS.find((l) => l.id === look)
  const gerar = async () => {
    setErro(null)
    try {
      await api.gerar({ ...pedido, prompt: aplicarLook(lookAtual, prompt) } as Parameters<typeof api.gerar>[0])
    } catch (e) { setErro(mensagem(e)) }
  }

  const modosRef = new Set([...Object.values(REFERENCIAS).map((r) => r.modo), REF_NUVEM.modo])
  const minhas = tarefas.filter((t) => modelos.some((m) => m.id === t.modelo) || apiModelos.some((m) => m.id === t.modelo)
    || modosRef.has(t.modelo))

  return (
    <div className="hf-aba">
      <div className="hf-heroi">
        <span className="hf-sobretitulo">IMAGE</span>
        <h1>Turn a sentence into a picture</h1>
      </div>

      <div className="hf-barra-prompt">
        {!comRefs && (
          <div className="hf-looks">
            <span className="hf-grupo-rotulo">One-tap looks</span>
            {/* Cartoes com miniatura: cada uma e uma amostra real do look (Flux 3 Klein). */}
            <div className="hf-looks-grade" role="radiogroup" aria-label="One-tap looks">
              <button type="button" role="radio" aria-checked={look === ''} className="hf-look" data-ativo={look === ''} onClick={() => setLook('')}>
                <span className="hf-look-nada" aria-hidden>⊘</span><span>None</span>
              </button>
              {LOOKS.map((l) => (
                <button key={l.id} type="button" role="radio" aria-checked={look === l.id} className="hf-look" data-ativo={look === l.id}
                  onClick={() => setLook(look === l.id ? '' : l.id)} title={`${l.rotulo}: e.g. ${l.exemplo}`}>
                  <img src={`/looks/${l.id}.webp`} alt="" /><span>{l.rotulo}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {maxRefs > 0 && (
          <div className="hf-slots">
            {refsOk.map((r, i) => (
              <SlotImagem key={r.nome + i} rotulo={i === 0 && usoRefs?.base ? 'Base image' : `Image ${i + 1}`} valor={r}
                aoMudar={(n) => setRefs((a) => n ? a.map((x, j) => (j === i ? n : x)) : a.filter((_, j) => j !== i))} />
            ))}
            {refsOk.length < maxRefs && (
              <SlotImagem key={`novo${refsOk.length}`} rotulo={refsOk.length ? `Image ${refsOk.length + 1}` : usoRefs?.base ? 'Base image' : 'Character'}
                valor={null} aoMudar={(n) => n && setRefs((a) => [...a.slice(0, maxRefs), n])} />
            )}
          </div>
        )}
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2}
          placeholder={comRefs ? 'Describe the result. Refer to the images as @image1, @image2…'
            : lookAtual ? `What should it show? e.g. ${lookAtual.exemplo} (empty = this example)` : 'Describe the image you want…'}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && (prompt.trim() || lookAtual)) gerar() }} />
        <div className="hf-linha-controles">
          <select className="hf-select" value={valorSelect} onChange={(e) => escolher(e.target.value)} aria-label="Model">
            <GruposAbertos itens={modelos.map((m) => ({ id: m.id, rotulo: m.rotulo, nuvem: m.nuvem }))} api={apiModelos} />
          </select>
          <Chips rotulo="Aspect ratio" opcoes={PROPORCOES.map((p) => ({ id: p, rotulo: p }))} valor={proporcao} aoMudar={setProporcao} />
          {!(comRefs && !apiAtual) && <Chips rotulo="Images" opcoes={[1, 2, 4].map((n) => ({ id: n, rotulo: `×${n}` }))} valor={lote} aoMudar={setLote} />}
          {apiAtual && niveis.length > 1 && (
            <Chips rotulo="Resolution" opcoes={niveis.map((n) => ({ id: n, rotulo: n }))} valor={nivelOk} aoMudar={setNivel} />
          )}
          <BotaoGerar est={custo} desligado={!prompt.trim() && !(lookAtual && !comRefs)} aoClicar={gerar} />
        </div>
        {ehIdeogram && (
          <div className="hf-linha-controles">
            <Chips rotulo="Layout" opcoes={[{ id: 'auto', rotulo: 'Automatic' }, { id: 'caixas', rotulo: 'Draw boxes' }]}
              valor={comLayout ? 'caixas' : 'auto'} aoMudar={(v) => setComLayout(v === 'caixas')} />
          </div>
        )}
        {ehIdeogram && comLayout && (
          <LayoutIdeogram proporcao={proporcao} elementos={elementos} aoMudar={setElementos}
            fundo={fundoLayout} aoMudarFundo={setFundoLayout} pensando={pensando}
            aoSugerir={sugerir} podeSugerir={!!prompt.trim()} />
        )}
        {atual && <p className="hf-dica">{DESCRICOES[atual.id] ?? atual.descricao}
          {usoRefs ? ` With images: ${usoRefs.uso}` : ''}</p>}
        {apiAtual && <p className="hf-dica">Paid API model, runs on your Comfy account credits{preco !== null ? ` · about $${preco.toFixed(2)} per run` : ''}.</p>}
        {erro && <p className="hf-erro">{erro}</p>}
      </div>

      <Galeria>
        {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
        {minhas.length === 0 && <p className="hf-vazio">Your images will appear here.</p>}
      </Galeria>
    </div>
  )
}
