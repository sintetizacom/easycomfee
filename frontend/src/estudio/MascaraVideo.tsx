import { useEffect, useRef, useState } from 'react'
import { api, type Referencia } from '../api'
import { mensagem } from './comum'

// Pintar o que sera apagado de um video: o primeiro quadro aparece com uma tela de pintura por cima.
// O que for pintado vira uma imagem de mascara (branco = apagar, preto = manter), enviada ao motor;
// o servidor repete essa mascara em todos os quadros (serve para objetos que ficam no mesmo lugar).

export default function MascaraVideo({ videoUrl, aoMudar }: { videoUrl: string; aoMudar: (m: Referencia | null) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const tela = useRef<HTMLCanvasElement>(null)
  const mascara = useRef<HTMLCanvasElement | null>(null)
  const [raio, setRaio] = useState(40)
  const [pintou, setPintou] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const pintando = useRef(false)

  // Ao carregar o video: a tela e a mascara tem o tamanho real dele.
  const preparar = () => {
    const v = video.current, t = tela.current
    if (!v || !t || !v.videoWidth) return
    t.width = v.videoWidth; t.height = v.videoHeight
    const m = document.createElement('canvas')
    m.width = v.videoWidth; m.height = v.videoHeight
    const c = m.getContext('2d')!
    c.fillStyle = '#000'; c.fillRect(0, 0, m.width, m.height)
    mascara.current = m
    setPintou(false); aoMudar(null)
  }
  useEffect(() => { setPintou(false); aoMudar(null) }, [videoUrl])  // eslint-disable-line react-hooks/exhaustive-deps

  const ponto = (e: React.PointerEvent) => {
    const t = tela.current!
    const r = t.getBoundingClientRect()
    return { x: ((e.clientX - r.left) / r.width) * t.width, y: ((e.clientY - r.top) / r.height) * t.height }
  }
  const pincel = (de: { x: number; y: number }, ate: { x: number; y: number }) => {
    const t = tela.current!, m = mascara.current!
    // Escala do pincel: o raio vale em pixels do video.
    for (const [alvo, cor] of [[t, 'rgba(255,60,60,0.45)'], [m, '#fff']] as const) {
      const c = alvo.getContext('2d')!
      c.strokeStyle = cor; c.fillStyle = cor; c.lineWidth = raio * 2; c.lineCap = 'round'
      c.beginPath(); c.moveTo(de.x, de.y); c.lineTo(ate.x, ate.y); c.stroke()
      c.beginPath(); c.arc(ate.x, ate.y, raio, 0, Math.PI * 2); c.fill()
    }
  }
  const ultimo = useRef({ x: 0, y: 0 })
  const comecar = (e: React.PointerEvent) => {
    if (!mascara.current) return
    pintando.current = true
    ;(e.target as Element).setPointerCapture(e.pointerId)
    ultimo.current = ponto(e)
    pincel(ultimo.current, ultimo.current)
  }
  const mover = (e: React.PointerEvent) => {
    if (!pintando.current) return
    const p = ponto(e)
    pincel(ultimo.current, p)
    ultimo.current = p
  }
  const terminar = async () => {
    if (!pintando.current) return
    pintando.current = false
    setPintou(true); setEnviando(true); setErro(null)
    try {
      const blob: Blob = await new Promise((ok, falha) => mascara.current!.toBlob((b) => (b ? ok(b) : falha(new Error('mask'))), 'image/png'))
      aoMudar(await api.enviarReferencia(new File([blob], 'mascara.png', { type: 'image/png' })))
    } catch (e) { setErro(mensagem(e)); aoMudar(null) } finally { setEnviando(false) }
  }
  const limpar = () => {
    const t = tela.current, m = mascara.current
    if (!t || !m) return
    t.getContext('2d')!.clearRect(0, 0, t.width, t.height)
    const c = m.getContext('2d')!; c.fillStyle = '#000'; c.fillRect(0, 0, m.width, m.height)
    setPintou(false); aoMudar(null)
  }

  return (
    <div className="hf-mask">
      <div className="hf-mask-palco">
        <video ref={video} src={videoUrl} muted playsInline preload="auto" onLoadedData={preparar} onLoadedMetadata={() => { if (video.current) video.current.currentTime = 0.05 }} />
        <canvas ref={tela} onPointerDown={comecar} onPointerMove={mover} onPointerUp={terminar} onPointerCancel={terminar} aria-label="Paint over the object to erase" />
        <div className="hf-mask-barra">
          <label>Brush <input type="range" min={8} max={160} step={4} value={raio} onChange={(e) => setRaio(Number(e.target.value))} aria-label="Brush size" /></label>
          <button type="button" className="hf-botao-sec" onClick={limpar} disabled={!pintou}>Clear</button>
          <span>{enviando ? 'Saving the mask…' : pintou ? 'Mask ready (covers every frame)' : 'Paint over what should disappear'}</span>
        </div>
      </div>
      {erro && <p className="hf-erro" role="alert">{erro}</p>}
    </div>
  )
}
