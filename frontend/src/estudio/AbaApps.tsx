import { useContext, useRef, useState } from 'react'
import { MotorCtx } from './motor'
import { api, urlEntrada, type Referencia } from '../api'
import { BotaoGerar, CartaoTarefa, Chips, SlotImagem, mensagem, useCusto, useTarefas, Galeria, MAX_PROMPT } from './comum'

// VFX Apps: one card per effect, all open-weight LTX IC-LoRAs. Pick a card,
// drop a video, press Apply. Each card id is an effect of VIDEO_TRANSFORMAR
// in the backend (presets.py); "slowmo" is the LTX slow-motion LoRA instead.

export type App = {
  id: string; nome: string; frase: string; texto?: string
  imagem?: string; imagemOpcional?: boolean; formatos?: boolean; video?: boolean; chaves?: boolean
}

type Chave = { id: number; img: Referencia | null; quadro: number }

export const APPS: App[] = [
  { id: 'noite', nome: 'Day → Night', frase: 'The same shot at night: dark sky, streetlights and windows on.' },
  { id: 'limpar', nome: 'Remove people', frase: 'Erases people and cars that move and rebuilds the background.' },
  { id: 'agua', nome: 'Add water', frase: 'Flood, rain, waves and splashes. Describe the water you want.', texto: 'The ground is flooded with shallow rushing water' },
  { id: 'trocar', nome: 'Swap character', frase: 'Keeps the motion of the video, takes the look from a new first frame.', imagem: 'New first frame' },
  { id: 'expandir', nome: 'Expand frame', frase: 'Turns vertical into widescreen (or back) by inventing the edges.', formatos: true },
  { id: 'cor', nome: 'Colorize', frase: 'Brings black-and-white footage to color. Name the colors you want: it needs them.', texto: 'A full color video with natural vivid colors: ' },
  { id: 'nitidez', nome: 'Unblur', frase: 'Recovers sharpness from blurry footage.' },
  { id: 'compressao', nome: 'Remove compression', frase: 'Clears blocky compression artifacts from footage.' },
  { id: 'detalhe', nome: 'Refine details', frase: 'Rebuilds texture in soft or upscaled footage.' },
  { id: 'restaurar', nome: 'Restore', frase: 'For very damaged footage. Creative: it may invent details.' },
  { id: 'profundidade', nome: 'Follow depth', frase: 'Keeps the video’s forms and camera motion while changing its appearance.', imagem: 'First frame (optional)', imagemOpcional: true },
  { id: 'maquete', nome: '3D render → Video', frase: 'A blockout from Blender or Unreal becomes the finished shot: camera and motion from the render, look from your image.', imagem: 'Look (frame 1)', chaves: true },
  { id: 'mapa_profundidade', nome: 'Video → Depth map', frase: 'Turns a video into a stable depth map: near is bright, far is dark. Optional EXR frames for Blender or After Effects.' },
  { id: 'slowmo', nome: 'Slow motion', frase: 'Animates a still in true slow motion (high-speed camera look).', imagem: 'Start image', video: false },
]

// Comfy Cloud has the LTX 2.3 version of most of these LoRAs (nuvem.SUBSTITUTOS);
// these two exist only in the 2.5 Creative Lab, so they need your own GPU.
// The layout-to-render LoRA (3D render → Video) is a 2.5 one too.
const SO_LOCAL = new Set(['restaurar', 'slowmo', 'maquete', 'mapa_profundidade'])

export default function AbaApps({ naNuvem }: { naNuvem: boolean }) {
  const tarefas = useTarefas()
  const [app, setApp] = useState<App | null>(() => APPS.find((a) => location.hash === `#apps/${a.id}`) ?? null)
  const [video, setVideo] = useState<Referencia | null>(null)
  const [imagem, setImagem] = useState<Referencia | null>(null)
  const [texto, setTexto] = useState('')
  const [formato, setFormato] = useState('16:9')
  // Video -> Depth map: cinza ou colorido, e quadros EXR opcionais.
  const [corMapa, setCorMapa] = useState<'gray' | 'inferno'>('gray')
  const [exr, setExr] = useState(false)
  const ehMapa = app?.id === 'mapa_profundidade'
  // Pacote "profundidade" do Config Models (modelo + extensao no motor de video).
  const { instalados } = useContext(MotorCtx)
  const semPacote = ehMapa && !!instalados && !instalados.has('profundidade')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  // 3D render → Video: keyframes, each at a frame number (from 1, 24 fps, as in Blender).
  const [chaves, setChaves] = useState<Chave[]>([])
  const proximo = useRef(1)
  const player = useRef<HTMLVideoElement>(null)
  const [duracao, setDuracao] = useState(0)
  const quadroAtual = () => Math.round((player.current?.currentTime ?? 0) * 24) + 1
  const addChave = () => {
    const n = quadroAtual()
    setChaves((a) => a.some((c) => c.quadro === n) ? a
      : [...a, { id: proximo.current++, img: null, quadro: n }].sort((x, y) => x.quadro - y.quadro))
  }
  const mudarChave = (id: number, c: Partial<Chave>) => setChaves((a) => a.map((x) => (x.id === id ? { ...x, ...c } : x)))
  // Saves the gray frame to Assets, in the size the model uses, to restyle in the Image tab.
  const capturar = async (n: number) => {
    setErro(null)
    try {
      await api.gerar({ modelo: 'quadros_maquete', prompt: '', proporcao: '1:1', quadros_extrair: [n],
        referencias: [`entrada:${video!.nome}`] })
    } catch (e) { setErro(mensagem(e)) }
  }

  const abrir = (a: App) => { setApp(a); setTexto(a.texto ?? ''); setErro(null) }
  const precisaVideo = app?.video !== false
  const bloqueado = naNuvem && !!app && SO_LOCAL.has(app.id)
  const pronto = app && !bloqueado && !semPacote && (!precisaVideo || video) && (!app.imagem || app.imagemOpcional || imagem)

  const custo = useCusto(!app || bloqueado ? null : ehMapa
    ? { modelo: 'profundidade_video', prompt: '', proporcao: '1:1', referencias: video ? [`entrada:${video.nome}`] : [] }
    : app.id === 'slowmo'
    ? { modelo: 'video', modelo_video: 'ltx', modo_video: 'imagem', prompt: 'x', proporcao: '1:1',
        proporcao_video: '16:9', resolucao_video: '720p', duracao_video: 5, com_audio: false, referencias: ['a.png'] }
    : { modelo: 'transformar_video', efeito_video: app.id, prompt: 'x', proporcao: '1:1',
        referencias: video ? [`entrada:${video.nome}`] : [] })

  const aplicar = async () => {
    if (!app) return
    setErro(null)
    try {
      if (ehMapa) {
        await api.gerar({ modelo: 'profundidade_video', prompt: '', proporcao: '1:1', mapa_cor: corMapa, exr,
          referencias: [`entrada:${video!.nome}`] } as Parameters<typeof api.gerar>[0])
      } else if (app.id === 'slowmo') {
        await api.gerar({
          modelo: 'video', modelo_video: 'ltx', modo_video: 'imagem', proporcao: '1:1',
          prompt: texto.trim() || 'Slow motion shot, high-speed camera, every movement stretched and graceful',
          proporcao_video: '16:9', resolucao_video: '720p', duracao_video: 5, com_audio: false,
          velocidade_video: 0.2, referencias: [imagem!.nome],
        })
      } else {
        await api.gerar({
          modelo: 'transformar_video', efeito_video: app.id, prompt: texto.trim(), proporcao: '1:1',
          formato_saida: formato, referencias: [`entrada:${video!.nome}`, ...(imagem ? [imagem.nome] : [])],
          ...(app.chaves ? { chaves_video: chaves.filter((c) => c.img).map((c) => ({ imagem: c.img!.nome, quadro: c.quadro })) } : {}),
        })
      }
    } catch (e) { setErro(mensagem(e)) }
  }

  const minhas = tarefas.filter((t) => t.modelo === 'transformar_video' || t.modelo === 'quadros_maquete' || t.modelo === 'profundidade_video' || (t.modelo === 'video' && t.prompt.includes('Slow motion')))

  return (
    <div className="hf-aba">
      <div className="hf-heroi">
        <span className="hf-sobretitulo">VFX APPS · LTX OPEN WEIGHTS</span>
        <h1>One click visual effects</h1>
        <p className="hf-dica">Each app is an open LTX IC-LoRA, on your own GPU or on Comfy Cloud. Pick one and drop a video.</p>
      </div>

      <div className="hf-apps">
        {APPS.map((a) => (
          <button key={a.id} className="hf-app" data-ativo={app?.id === a.id} aria-pressed={app?.id === a.id} onClick={() => abrir(a)}>
            <video src={`/exemplos/${a.id}.mp4?v=5`} muted loop autoPlay playsInline
              onError={(e) => { (e.currentTarget as HTMLVideoElement).style.visibility = 'hidden' }} />
            {a.id === 'maquete' && <small className="hf-selo-neon">Experimental</small>}
            <b>{a.nome}{naNuvem && SO_LOCAL.has(a.id) && <small> · local GPU only</small>}</b>
            <span>{a.frase}</span>
          </button>
        ))}
      </div>

      {app && (
        <div className="hf-barra-prompt" style={{ marginTop: 20 }}>
          <span className="hf-passo">{app.nome}</span>
          {app.id === 'maquete' && (
            <div className="hf-experimental">
              <b>Experimental</b>: results vary from shot to shot. For fewer errors:
              <ul>
                <li><b>Make the Look from frame 1 of your render</b>: capture it, restyle it in the Image tab with the gray frame as the base, and drop it here. Same framing, same aspect ratio.</li>
                <li><b>Keep the render simple</b>: clear blocks, a visible ground, smooth camera moves, 5 to 10 s at 24 fps.</li>
                <li><b>Add a keyframe whenever a new side of the object shows</b> (it turns, the camera goes around it): the model only invents what it never saw.</li>
                <li><b>Describe the scene in the prompt</b> (“a green sports car on a desert road at sunset”), not the camera.</li>
                <li>Try 2 or 3 seeds before changing the setup.</li>
              </ul>
            </div>
          )}
          <div className="hf-slots">
            {precisaVideo && (
              <label className="hf-slot" data-cheio={!!video}>
                {video ? <video src={urlEntrada(video.nome)} muted /> : <span>{enviando ? 'Uploading…' : '+ Video'}</span>}
                <input type="file" accept="video/*" className="hf-arquivo" onChange={async (e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  setEnviando(true); setErro(null)
                  try { setVideo(await api.enviarReferencia(f)) } catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
                }} />
              </label>
            )}
            {app.imagem && <SlotImagem rotulo={app.imagem} valor={imagem} aoMudar={setImagem} />}
          </div>
          {app.chaves && video && (
            <div className="hf-chaves">
              <video ref={player} src={urlEntrada(video.nome)} controls muted
                onLoadedMetadata={(e) => setDuracao(e.currentTarget.duration)} />
              {duracao > 0 && (
                <div className="hf-linha-tempo" title="Keyframes on the timeline">
                  {chaves.map((c) => (
                    <i key={c.id} data-cheio={!!c.img} style={{ left: `${Math.min(100, ((c.quadro - 1) / 24 / duracao) * 100)}%` }}
                      onClick={() => { if (player.current) player.current.currentTime = (c.quadro - 1) / 24 }} />
                  ))}
                </div>
              )}
              <div className="hf-linha-controles">
                <button type="button" className="hf-botao-sec" onClick={addChave}>+ Keyframe at this frame</button>
                <button type="button" className="hf-botao-sec" onClick={() => capturar(quadroAtual())}>Capture this frame to Assets</button>
              </div>
              {chaves.map((c) => {
                const q = Math.round((c.quadro - 1) / 8) * 8 + 1
                return (
                  <div key={c.id} className="hf-chave">
                    <SlotImagem rotulo={`Frame ${c.quadro}`} valor={c.img} aoMudar={(img) => mudarChave(c.id, { img })} />
                    <label className="hf-equip">
                      <span className="hf-grupo-rotulo">Frame nº</span>
                      <input className="hf-campo" type="number" min={1} value={c.quadro}
                        onChange={(e) => mudarChave(c.id, { quadro: Math.max(1, Math.round(Number(e.target.value))) })} />
                      {q !== c.quadro && <small className="hf-dica">enters at frame {q} (multiples of 8)</small>}
                    </label>
                    <button type="button" className="hf-botao-sec" onClick={() => capturar(c.quadro)}>Capture</button>
                    <button type="button" className="hf-botao-sec" onClick={() => setChaves((a) => a.filter((x) => x.id !== c.id))}>Remove</button>
                  </div>
                )
              })}
              <p className="hf-dica">Frame 1 comes from the Look image. For later moments, add a keyframe, capture the gray frame,
                restyle it in the Image tab (Flux 3 with the captured frame as the base) and drop it here. 24 frames = 1 s, counted from 1 as in Blender.</p>
            </div>
          )}
          {!ehMapa && <textarea aria-label="Prompt" maxLength={MAX_PROMPT} value={texto} onChange={(e) => setTexto(e.target.value)} rows={1}
            placeholder="Optional: describe what you want to see…" />}
          {ehMapa && <p className="hf-dica">Up to the first 20 seconds of the video. EXR keeps the real depth values (32-bit, Z channel), one file per frame.</p>}
          <div className="hf-linha-controles">
            {ehMapa && <Chips rotulo="Look" opcoes={[{ id: 'gray', rotulo: 'Gray' }, { id: 'inferno', rotulo: 'Color' }]} valor={corMapa} aoMudar={setCorMapa} />}
            {ehMapa && <label className="hf-toggle"><input type="checkbox" checked={exr} onChange={(e) => setExr(e.target.checked)} /> EXR too</label>}
            {app.formatos && <Chips rotulo="Output format" opcoes={['16:9', '9:16', '1:1'].map((f) => ({ id: f, rotulo: f }))} valor={formato} aoMudar={setFormato} />}
            {semPacote && <span className="hf-dica">Install “Video depth map” in Config Models to use this app.</span>}
            {bloqueado && <span className="hf-dica">This effect is not on Comfy Cloud yet. Switch to Local to use it.</span>}
            <BotaoGerar rotulo="Apply ✦" est={custo} desligado={!pronto} aoClicar={aplicar} />
          </div>
          {erro && <p className="hf-erro">{erro}</p>}
        </div>
      )}

      <Galeria tipo="video">
        {minhas.map((t) => t.exr && t.estado === 'pronto' ? (
          <div key={t.id} className="hf-com-exr">
            <CartaoTarefa t={t} />
            <a className="hf-botao-sec" href={`/api/profundidade/exr/${t.id}`} download>Download EXR frames (.zip)</a>
          </div>
        ) : <CartaoTarefa key={t.id} t={t} />)}
      </Galeria>
    </div>
  )
}
