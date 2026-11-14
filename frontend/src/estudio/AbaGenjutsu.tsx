import { useContext, useEffect, useRef, useState } from 'react'
import { LinhaOnde, MotorCtx, useEscolha, useInstalado } from './motor'
import { api, referenciaDaGaleria, urlEntrada, urlImagem, type Referencia } from '../api'
import { ThenNow, abrirVisualizador } from './Visualizador'
import { Contador, limitePrompt, BotaoGerar, CartaoTarefa, Chips, SlotImagem, arquivos, mensagem, useVideoRecebido, useCusto, useTarefas, type Estimativa, Galeria, parteDoHash, useLembrado, textoDoDetalhe, TituloPagina } from './comum'

// Genjutsu: recast a video with a new cast, place or style while its motion,
// camera and timing stay. Models (backend genjutsu.py):
// - Recast (open, default): Qwen Image Edit redraws the first frame with the
//   references, then LTX Union Control carries the whole video to that look.
//   This tab chains the two jobs: when the frame is done, the video job starts.
// - Wan Animate 2 (open): the character photo performs the video's motion.
// - Wan 2.2 Animate Replace (open): the official template, SAM 3 mask; the character goes INTO the video.
// - MiniMax H3 Character Swap (open, Comfy Cloud): MDMZ's workflow; SAM 3 mask + H3 Ref2VA.
// - Higgsfield Genjutsu, Kling Omni, Runway Aleph2: Comfy partner nodes.

type Modelo = { id: string; rotulo: string; aberto: boolean; refs: string[]; dica: string }

const MODELOS: Modelo[] = [
  { id: 'recast', rotulo: 'Recast', aberto: true, refs: ['Character', 'Location (optional)'],
    dica: 'Open weights. Redraws the first frame with your references, then carries the whole video to that look. Up to 14 s.' },
  { id: 'wan_animate2', rotulo: 'Wan Animate 2', aberto: true, refs: ['Character'],
    dica: 'Open weights. The person in your photo performs the exact motion of the video (face, body, hands), in the photo’s own setting. About 5 s.' },
  { id: 'wan22_replace', rotulo: 'Wan 2.2 Animate · Replace', aberto: true, refs: ['Character'],
    dica: 'Open weights. Replaces the person inside the video with your character, keeping the place; the light is matched to the scene. About 5 s. Comfy Cloud, or your GPU with its package from Config Models.' },
  { id: 'h3_swap', rotulo: 'MiniMax H3 Character Swap', aberto: true, refs: ['Character'],
    dica: 'Open weights. Comfy Cloud, or your GPU with its package from Config Models (24-32 GB card). SAM 3 finds who to replace; MiniMax H3 puts your character in, with the video’s motion, camera, light and sound. Up to 8 s. Workflow by MDMZ.' },
  { id: 'higgsfield', rotulo: 'Higgsfield Genjutsu', aberto: false, refs: ['Reference 1', 'Reference 2 (optional)', 'Reference 3 (optional)'],
    dica: 'The original Genjutsu. New cast, place and style from up to 8 references. 720p, up to 30 s.' },
  { id: 'kling_omni', rotulo: 'Kling 3.0 Omni', aberto: false, refs: ['Reference 1 (optional)', 'Reference 2 (optional)'],
    dica: 'Video to video guided by text and reference images. 720p, 3 to 10 s.' },
  { id: 'aleph2', rotulo: 'Runway Aleph2', aberto: false, refs: [],
    dica: 'Restyle, relight, add or remove things, described in text. Up to 30 s.' },
  { id: 'beeble_edit', rotulo: 'Beeble SwitchX', aberto: false, refs: ['Look reference (optional)'],
    dica: 'Switch the background, light or costume while the subject’s own pixels and motion stay. Text and/or a reference image. 720p or 1080p. Comfy Cloud, credits.' },
  { id: 'kling4_edit', rotulo: 'Kling 4.0 Edit', aberto: false, refs: [],
    dica: 'Edit a video with text, keeping its own sound. 720p or 1080p. Comfy Cloud, credits.' },
  { id: 'wan27_edit', rotulo: 'Wan 2.7 Edit', aberto: false, refs: [],
    dica: 'Edit a video with text, keeping its own sound. Up to 10 s. Comfy Cloud, credits.' },
  { id: 'grok_edit', rotulo: 'Grok Imagine Edit', aberto: false, refs: [],
    dica: 'Quick edits of a video described in text. Comfy Cloud, credits.' },
  { id: 'luma_edit', rotulo: 'Luma Ray 3.2 Edit', aberto: false, refs: [],
    dica: 'Edit a video with text: change the look, the light or what is in it. Up to 10 s. Comfy Cloud, credits: the priciest editor here, about US$ 1 to 2 per second of video.' },
]

// Etiquetas dos cartoes: o essencial de cada modelo num relance.
// Foto de cada cartao de modelo (geradas para o app, em public/studios/cartoes).
// Resolucoes oferecidas por modelo (as mesmas de genjutsu.RESOLUCOES no servidor).
const RESOLUCOES: Record<string, string[]> = {
  wan_animate2: ['480p', '720p'], wan22_replace: ['480p', '720p'], h3_swap: ['480p', '720p'],
  higgsfield: ['480p', '720p', '1080p'], kling_omni: ['720p', '1080p'],
  luma_edit: ['360p', '540p', '720p', '1080p'], kling4_edit: ['720p', '1080p'], wan27_edit: ['720p', '1080p'], beeble_edit: ['720p', '1080p'],
}
const FOTOS: Record<string, string> = { recast: 'gj_recast', wan_animate2: 'gj_wan_animate', wan22_replace: 'gj_wan_replace',
  h3_swap: 'gj_h3_swap', higgsfield: 'gj_higgsfield', kling_omni: 'gj_kling', aleph2: 'gj_runway', luma_edit: 'gj_luma_edit', kling4_edit: 'gj_kling4_edit', beeble_edit: 'gj_beeble', wan27_edit: 'gj_wan27_edit', grok_edit: 'gj_grok_edit' }

// Etiquetas dos cartoes, sempre na mesma ordem: quanto dura, o que entra, um extra. Mesmas palavras em todos.
const ETIQUETAS: Record<string, string[]> = {
  recast: ['Up to 14 s', 'Photos'],
  wan_animate2: ['About 5 s', 'Photo'],
  wan22_replace: ['About 5 s', 'Photo'],
  h3_swap: ['Up to 8 s', 'Photo', 'Keeps sound'],
  higgsfield: ['Up to 30 s', '8 photos'],
  kling_omni: ['3 to 10 s', '2 photos'],
  aleph2: ['Up to 30 s', 'Text only'],
  luma_edit: ['Up to 10 s', 'Text only'],
  kling4_edit: ['Up to 15 s', 'Text only', 'Keeps sound'],
  wan27_edit: ['Up to 10 s', 'Text only', 'Keeps sound'],
  grok_edit: ['Up to 15 s', 'Text only'],
  beeble_edit: ['Up to 10 s', 'Look photo'],
}
// Uma frase por cartao: o que ele faz, em poucas palavras.
const FAZ: Record<string, string> = {
  recast: 'New cast and place, same motion',
  wan_animate2: 'Your photo performs the video',
  wan22_replace: 'Swaps in your character',
  h3_swap: 'Swaps in your character',
  higgsfield: 'New cast, place and style',
  kling_omni: 'Rework a video with text and photos',
  aleph2: 'Restyle, relight, add or remove',
  luma_edit: 'Change the look, light or contents',
  kling4_edit: 'Edit by describing the change',
  wan27_edit: 'Edit by describing the change',
  grok_edit: 'Quick edits by description',
  beeble_edit: 'New background, light or costume',
}
// Os modelos de API, agrupados pelo tipo de trabalho.
const GRUPOS_API = [
  { rotulo: 'Swap the cast or place, with photos', ids: ['higgsfield', 'kling_omni'] },
  { rotulo: 'Edit the video by describing the change', ids: ['aleph2', 'luma_edit', 'kling4_edit', 'wan27_edit', 'grok_edit', 'beeble_edit'] },
]

const ROTULO_CUSTO = (a: Estimativa | null, b: Estimativa | null): Estimativa | null =>
  a && b && a.tipo === b.tipo && a.tipo === 'gpu' ? { tipo: 'gpu', usd: (a.usd ?? 0) + (b.usd ?? 0) }
    : a && b && a.tipo === 'gratis' && b.tipo === 'gratis' ? a : b

export default function AbaGenjutsu({ apiLiberado }: { apiLiberado: boolean }) {
  const tarefas = useTarefas()
  const [modelo, setModelo] = useState(() => MODELOS.some((m) => m.id === parteDoHash(1)) ? parteDoHash(1) : 'recast')
  const escolher = useEscolha(setModelo)
  const { naNuvem } = useContext(MotorCtx)
  const instalado = useInstalado()
  const [video, setVideo] = useState<Referencia | null>(null)
  const [refs, setRefs] = useState<(Referencia | null)[]>([])
  const [texto, setTexto] = useLembrado('genjutsu.texto', '')
  const [controle, setControle] = useState('pose')
  // MiniMax H3 Character Swap
  const [alvo, setAlvo] = useState('person')
  const [gemini, setGemini] = useState(true)
  const [turbo, setTurbo] = useState(false)
  // Resolucao final (so na nuvem ou por API; o mesmo quadro de genjutsu.RESOLUCOES).
  const [resolucao, setResolucao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  // "Send to Genjutsu" num video da galeria: vira o video de entrada.
  useVideoRecebido(setVideo, setErro)
  // Recast in flight: the frame job, and what the video job needs once it is done.
  const pendente = useRef<{ id: string; video: string; texto: string; controle: string } | null>(null)
  const [etapa, setEtapa] = useState('')
  // Recast em duas etapas: o primeiro quadro novo espera a aprovacao antes de animar
  // (um quadro errado vira um video inteiro errado, e o video e a parte demorada).
  const [aprovar, setAprovar] = useState<{ quadro: { nome: string; subpasta: string }; video: string; texto: string; controle: string } | null>(null)
  // Jobs started here (the Recast steps are ordinary image and video jobs).
  const [meus, setMeus] = useState<string[]>([])
  const anotar = (id: string) => setMeus((m) => [id, ...m])

  const cfg = MODELOS.find((m) => m.id === modelo)!
  const opcoesRes = RESOLUCOES[modelo] && (!cfg.aberto || naNuvem) ? RESOLUCOES[modelo] : null
  const resEscolhida = opcoesRes ? (opcoesRes.includes(resolucao) ? resolucao : modelo === 'higgsfield' ? '720p' : opcoesRes[0]) : ''
  // Cartao: modelo aberto no motor atual (Wan Animate 2 so existe na nuvem); de API, pelo id.
  const escolherModelo = (m: Modelo) => {
    if (!m.aberto) { escolher(m.id); return }
    escolher(`${m.id === 'wan_animate2' || naNuvem ? 'nuvem' : 'local'}:${m.id}`)
  }
  // Mosaico: cards de tamanhos diferentes (grandes e pequenos) que fecham cada linha sem buracos (ver o CSS "hf-gj-bloco").
  const cartaoMosaico = (m: Modelo) => (
    <div key={m.id} className="hf-gj-cartao" data-m={m.id} data-ativo={modelo === m.id}>
      {FOTOS[m.id] && <img src={`/studios/cartoes/${FOTOS[m.id]}.webp`} alt="" loading="lazy" />}
      <button type="button" className="hf-gj-escolher" aria-pressed={modelo === m.id} onClick={() => escolherModelo(m)} title={m.dica}>
        <b>{m.rotulo}</b>
        <em className="hf-gj-faz">{FAZ[m.id]}</em>
        <span className="hf-mu-tags">
          <i data-onde={m.aberto ? 'local' : 'falta'}>{m.aberto ? 'Open weights' : 'API'}</i>
          {(ETIQUETAS[m.id] ?? []).map((t) => <i key={t}>{t}</i>)}
        </span>
      </button>
      {m.aberto && (
        <div className="hf-gj-onde-cartao">
          <LinhaOnde escolher={escolher} id={m.id} cartaoAtivo={modelo === m.id} local={m.id !== 'wan_animate2'} nuvem faltaLocal={!instalado(m.id)} />
        </div>
      )}
    </div>
  )
  const doBloco = (ids: string[]) => ids.map((id) => MODELOS.find((m) => m.id === id)).filter((m): m is Modelo => !!m).map(cartaoMosaico)
  const imagens = refs.slice(0, cfg.refs.length).filter(Boolean) as Referencia[]
  const precisaRef = cfg.refs.length > 0 && !cfg.refs[0].includes('optional')
  const pronto = !!video && (!cfg.aberto || naNuvem || instalado(modelo)) && (!precisaRef || imagens.length > 0)
    && (modelo === 'wan_animate2' || modelo === 'wan22_replace' || modelo === 'h3_swap' || !!texto.trim()) && !etapa

  const custoQuadro = useCusto(modelo === 'recast' ? { modelo: 'qwen', prompt: 'x', proporcao: '16:9', lote: 1, referencias: ['a.png'] } : null)
  const custoVideo = useCusto(!video ? null : modelo === 'recast'
    ? { modelo: 'transformar_video', efeito_video: 'trocar', prompt: 'x', proporcao: '1:1', referencias: [`entrada:${video.nome}`] }
    : { modelo: 'genjutsu', modelo_genjutsu: modelo, prompt: 'x', proporcao: '1:1',
        referencias: [`entrada:${video.nome}`, ...imagens.map((r) => r.nome)], resolucao_genjutsu: resEscolhida,
        ...(modelo === 'h3_swap' ? { alvo_genjutsu: alvo, gemini_genjutsu: gemini, turbo_genjutsu: turbo } : modelo === 'wan22_replace' ? { alvo_genjutsu: alvo } : {}) })
  const custo = modelo === 'recast' ? ROTULO_CUSTO(custoQuadro, custoVideo) : custoVideo

  // Step 2 of Recast: when the new first frame is ready, start the video job.
  useEffect(() => {
    const p = pendente.current
    if (!p) return
    const t = tarefas.find((x) => x.id === p.id)
    if (!t || (t.estado !== 'pronto' && t.estado !== 'erro')) return
    pendente.current = null
    if (t.estado === 'erro') { setEtapa(''); setErro(t.erro || 'The first frame failed.'); return }
    setEtapa('')
    setAprovar({ quadro: arquivos(t)[0], video: p.video, texto: p.texto, controle: p.controle })
  }, [tarefas])

  // Etapa 2, so depois de aprovar: o LTX Union Control leva o video inteiro para o quadro aprovado.
  const animar = () => {
    const a = aprovar
    if (!a) return
    setAprovar(null)
    setEtapa('Animating the video…')
    referenciaDaGaleria({ arquivo: a.quadro.nome, subpasta: a.quadro.subpasta })
      .then((r) => api.gerar({
        modelo: 'transformar_video', efeito_video: 'trocar', controle_troca: a.controle, prompt: a.texto,
        proporcao: '1:1', referencias: [`entrada:${a.video}`, r.nome],
      } as Parameters<typeof api.gerar>[0]))
      .then((v) => anotar(v.id))
      .catch((e) => setErro(mensagem(e)))
      .finally(() => setEtapa(''))
  }

  const gerar = async () => {
    if (!video) return
    setErro(null)
    setAprovar(null)
    try {
      if (modelo === 'recast') {
        setEtapa('Redrawing the first frame…')
        const r = await fetch('/api/genjutsu/quadro', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ video: `entrada:${video.nome}` }) })
        if (!r.ok) throw new Error(textoDoDetalhe((await r.json().catch(() => ({}))).detail, 'Could not read the video.'))
        const { nome } = await r.json()
        const quem = imagens.length > 1
          ? 'the main character from image 2, placed in the setting of image 3'
          : 'the main character from image 2'
        const instrucao = `Redraw image 1 keeping its exact composition, camera angle, framing and the pose of every person. Replace the person with ${quem}. ${texto.trim()}`
        const t = await api.gerar({ modelo: 'qwen', prompt: instrucao, proporcao: '16:9', lote: 1,
          resolucao_edicao: 'baixa', referencias: [nome, ...imagens.map((i) => i.nome)] } as Parameters<typeof api.gerar>[0])
        anotar(t.id)
        pendente.current = { id: t.id, video: video.nome, texto: texto.trim(), controle }
      } else {
        // The server refuses an empty prompt; for Wan the text is optional.
        // The server refuses an empty prompt; these models need none, so a neutral line goes.
        const frase = texto.trim() || (modelo === 'h3_swap'
          ? 'Replace the performer in the video with the character in the image, copying the motion, timing and camera movement exactly.'
          : modelo === 'wan22_replace' ? 'The person moves naturally' : 'The person from the photo, moving naturally')
        anotar((await api.gerar({ modelo: 'genjutsu', modelo_genjutsu: modelo, prompt: frase, proporcao: '1:1', resolucao_genjutsu: resEscolhida,
          referencias: [`entrada:${video.nome}`, ...imagens.map((i) => i.nome)],
          ...(modelo === 'h3_swap' ? { alvo_genjutsu: alvo, gemini_genjutsu: gemini, turbo_genjutsu: turbo } : modelo === 'wan22_replace' ? { alvo_genjutsu: alvo } : {}),
        } as unknown as Parameters<typeof api.gerar>[0])).id)
      }
    } catch (e) { setEtapa(''); setErro(mensagem(e)) }
  }

  const minhas = tarefas.filter((t) => t.modelo === 'genjutsu' || meus.includes(t.id))
  // O ultimo video pronto desta sessao vai para o comparador Original | Result.
  const feita = minhas.find((t) => t.estado === 'pronto' && arquivos(t).some((a) => /\.(mp4|webm|mov)$/i.test(a.nome)))
  const resultado = feita ? arquivos(feita).find((a) => /\.(mp4|webm|mov)$/i.test(a.nome)) : undefined

  return (
    <div className="hf-aba hf-img hf-gj">
      <TituloPagina antes="Recast" destaque="any video" sub="Same motion, camera and timing. New cast, place or style." />

      <span className="hf-grupo-rotulo hf-gj-rotulo">Open weights <small>your GPU or Comfy Cloud</small></span>
      <div className="hf-gj-bloco" data-bloco="abertos">{doBloco(['recast', 'wan_animate2', 'wan22_replace', 'h3_swap'])}</div>
      {apiLiberado && GRUPOS_API.map((g, n) => (
        <div key={g.rotulo}>
          <span className="hf-grupo-rotulo hf-gj-rotulo">{g.rotulo} <small>Comfy credits</small></span>
          <div className="hf-gj-bloco" data-bloco={n === 0 ? 'troca' : 'edicao'}>{doBloco(g.ids)}</div>
        </div>
      ))}
      <p className="hf-gj-dica-longa hf-gj-escolhido"><b>{cfg.rotulo}.</b> {cfg.dica}</p>

      <div className="hf-barra-prompt hf-ls hf-gj-passos">
        <div className="hf-ls-passos">
          <section className="hf-ls-cartao" data-pronto={!!video}>
            <header><b>1</b> Video</header>
            <label className="hf-slot hf-gj-video" data-cheio={!!video}>
              {video ? <video src={urlEntrada(video.nome)} muted loop autoPlay playsInline />
                : <span>{enviando ? 'Uploading…' : '+ Your video'}<small>Drop it here or click to choose</small></span>}
              <input type="file" accept="video/*" className="hf-arquivo" onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setEnviando(true); setErro(null)
                try { setVideo(await api.enviarReferencia(f)) } catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
              }} />
            </label>
            {video && <button type="button" className="hf-botao-sec" onClick={() => setVideo(null)}>Remove video</button>}
            <p className="hf-dica">The motion, camera and timing come from this video. {(ETIQUETAS[cfg.id] ?? [])[0] ?? 'Short clips'} with {cfg.rotulo}.</p>
          </section>

          <section className="hf-ls-cartao" data-pronto={!precisaRef || imagens.length > 0}>
            <header><b>2</b> New cast {cfg.refs.length === 0 && <small>not used by this model</small>}</header>
            {cfg.refs.length > 0 ? (
              <div className="hf-gj-refs" data-n={cfg.refs.length}>
                {cfg.refs.map((rotulo, i) => (
                  <SlotImagem key={modelo + i} rotulo={rotulo} valor={refs[i] ?? null}
                    aoMudar={(r) => setRefs((atual) => { const c = atual.slice(); c[i] = r; return c })} />
                ))}
              </div>
            ) : <p className="hf-dica">{cfg.rotulo} works from the text alone.</p>}
            {cfg.refs.length > 0 && <p className="hf-dica">A clear photo of the character, full body if the video shows the body. Drag one from the gallery or press ↑ Use.</p>}
          </section>

          <section className="hf-ls-cartao hf-ls-cena">
            <header><b>3</b> Direction {(modelo === 'wan_animate2' || modelo === 'wan22_replace' || modelo === 'h3_swap') && <small>optional</small>}</header>
            <textarea aria-label="Direction" maxLength={limitePrompt(modelo)} value={texto} onChange={(e) => setTexto(e.target.value)} rows={4}
              placeholder={modelo === 'wan_animate2'
                ? 'Describe the character and the background'
                : modelo === 'h3_swap' ? 'e.g. the performer is singing; keep the original voice'
                : 'What changes, e.g. the dancer becomes a snow queen in an ice palace'} /><Contador texto={texto} limite={limitePrompt(modelo)} />
          </section>
        </div>

        {/* As opcoes ficam numa fileira de caixas iguais sob os tres boxes; o Generate e a ultima caixa. */}
        <div className="hf-gj-opcoes">
          {modelo === 'recast' && (
            <div className="hf-gj-opc">
              <Chips rotulo="The new video follows" opcoes={[{ id: 'pose', rotulo: 'Body pose' }, { id: 'profundidade', rotulo: 'Depth' }]}
                valor={controle} aoMudar={setControle} />
            </div>
          )}
          {(modelo === 'wan22_replace' || modelo === 'h3_swap') && (
            <div className="hf-gj-opc hf-gj-opc-larga" title="Who leaves the video. 'person' for one person; 'woman in red:1' to pick one of several.">
              <div className="hf-campo"><span>Who to replace in the video</span>
                <input className="hf-campo-texto" aria-label="Who to replace in the video" value={alvo} onChange={(e) => setAlvo(e.target.value)} placeholder="person" /></div>
              <small className="hf-dica">"person" for one person. With several, describe one: "man in the green shirt".</small>
            </div>
          )}
          {modelo === 'h3_swap' && <>
            <div className="hf-gj-opc">
              <Chips rotulo="Prompt" opcoes={[{ id: 'g', rotulo: 'Gemini writes it (API)' }, { id: 'p', rotulo: 'Standard' }]}
                valor={gemini ? 'g' : 'p'} aoMudar={(v) => setGemini(v === 'g')} />
            </div>
            <div className="hf-gj-opc">
              <Chips rotulo="Speed" opcoes={[{ id: 'n', rotulo: 'Quality · 20 steps' }, { id: 't', rotulo: 'Turbo · 8 steps' }]}
                valor={turbo ? 't' : 'n'} aoMudar={(v) => setTurbo(v === 't')} />
            </div>
          </>}
          {/* A resolucao fica ao lado do Generate, na ponta direita */}
          <div className="hf-gj-direita">
            {opcoesRes && (
              <div className="hf-gj-opc" title="The final size of the video. Higher costs more credits and takes longer.">
                <Chips rotulo="Resolution" opcoes={opcoesRes.map((r) => ({ id: r, rotulo: r === '480p' ? '480p · faster' : r }))}
                  valor={resEscolhida} aoMudar={setResolucao} />
              </div>
            )}
            <div className="hf-gj-opc hf-gj-opc-gerar">
              <BotaoGerar rotulo="Generate →" est={custo} desligado={!pronto} aoClicar={gerar} />
            </div>
          </div>
        </div>
        {etapa && <p className="hf-dica hf-gj-aviso">{etapa}</p>}
        {cfg.aberto && !naNuvem && !instalado(modelo) && (
          <p className="hf-erro hf-gj-aviso" role="alert">{cfg.rotulo} is not installed on this computer. Install it in Config Models, or choose Cloud on its card.</p>
        )}
        {erro && <p className="hf-erro" role="alert">{erro}</p>}
        {aprovar && (
          <section className="hf-gj-aprovar" aria-label="Approve the new first frame">
            <img src={urlImagem(aprovar.quadro)} alt="New first frame" onClick={() => abrirVisualizador(aprovar.quadro)} />
            <div>
              <b>Step 1 of 2 · check the new first frame</b>
              <p className="hf-dica">The whole video will follow this look: the character, clothes and place. If it is not right,
                redraw it (each try comes out different) or change the photo or the direction, before spending time on the video.</p>
              <div className="hf-gj-aprovar-botoes">
                <button type="button" className="hf-botao" onClick={animar}>Animate with this frame →</button>
                <button type="button" className="hf-botao-sec" onClick={() => void gerar()}>Redraw the frame</button>
                <button type="button" className="hf-botao-sec" onClick={() => setAprovar(null)}>Cancel</button>
              </div>
            </div>
          </section>
        )}
      </div>

      {video && resultado && (
        <section className="hf-gj-comparar" aria-label="Original and result">
          <ThenNow antes={urlEntrada(video.nome)} depois={urlImagem(resultado)} modo="cortina" rotulos={['Original', 'Result']} />
        </section>
      )}

      <section className="hf-img-recentes hf-lsn-recentes" aria-label="Recent recasts">
      <span className="hf-img-titulo">Recent recasts</span>
      <Galeria tipo="video">
        {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
        {minhas.length === 0 && <p className="hf-vazio">Your recast videos will appear here.</p>}
      </Galeria>
      </section>
    </div>
  )
}
