import { useCallback, useEffect, useRef, useState } from 'react'

// A escala 1 significa "cabe na tela". O botao de pixels reais calcula quanto
// isso representa em relacao ao tamanho natural do arquivo, que varia com a
// proporcao e com o tamanho da janela.

const MIN = 0.2
const MAX = 12

type Props = { src: string | null; vazio: React.ReactNode }

export default function Palco({ src, vazio }: Props) {
  const areaRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  // O palco serve imagem e video. A url sempre passa por /api/imagem, e a
  // extensao esta no PARAMETRO `nome`, no meio da query — nao no fim da url.
  // A primeira versao testava fim-de-string e por isso nunca reconhecia um
  // video: depois de ".mp4" vem "&subpasta=...".
  const ehVideo = (() => {
    if (!src) return false
    const nome = new URLSearchParams(src.split('?')[1] ?? '').get('nome') ?? src
    return /\.(mp4|webm|mkv|mov)$/i.test(nome)
  })()
  const ehAudio = !!src && /\.(flac|wav|mp3|ogg)$/i.test(new URLSearchParams(src.split('?')[1] ?? '').get('nome') ?? src)
  const [escala, setEscala] = useState(1)
  const [deslocamento, setDeslocamento] = useState({ x: 0, y: 0 })
  const arrastando = useRef<{ x: number; y: number } | null>(null)
  // O percentual depende do tamanho medido da imagem. Ele só existe depois que
  // ela carrega, e muda quando a janela é redimensionada — este contador força
  // o recálculo nos dois casos.
  const [medida, remedir] = useState(0)

  useEffect(() => {
    const aoRedimensionar = () => remedir((n) => n + 1)
    window.addEventListener('resize', aoRedimensionar)
    return () => window.removeEventListener('resize', aoRedimensionar)
  }, [])

  const ajustar = useCallback(() => {
    setEscala(1)
    setDeslocamento({ x: 0, y: 0 })
  }, [])

  // Trocar de imagem sempre volta para "cabe na tela".
  useEffect(() => { ajustar() }, [src, ajustar])

  /** Escala em que um pixel do arquivo ocupa um pixel da tela. */
  const escalaReal = () => {
    const img = imgRef.current
    if (!img || !img.clientWidth) return 1
    return img.naturalWidth / img.clientWidth
  }

  const aplicarZoom = (fator: number, ancora?: { x: number; y: number }) => {
    setEscala((z) => {
      const nova = Math.min(MAX, Math.max(MIN, z * fator))
      if (ancora && areaRef.current) {
        // Mantem sob o cursor o mesmo ponto da imagem durante o zoom.
        const r = areaRef.current.getBoundingClientRect()
        const cx = ancora.x - r.left - r.width / 2
        const cy = ancora.y - r.top - r.height / 2
        const k = nova / z
        setDeslocamento((d) => ({
          x: cx - (cx - d.x) * k,
          y: cy - (cy - d.y) * k,
        }))
      }
      return nova
    })
  }

  const aoRolar = (e: React.WheelEvent) => {
    e.preventDefault()
    aplicarZoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, { x: e.clientX, y: e.clientY })
  }

  const aoPressionar = (e: React.MouseEvent) => {
    if (escala <= 1) return
    arrastando.current = { x: e.clientX - deslocamento.x, y: e.clientY - deslocamento.y }
  }

  const aoMover = (e: React.MouseEvent) => {
    if (!arrastando.current) return
    setDeslocamento({
      x: e.clientX - arrastando.current.x,
      y: e.clientY - arrastando.current.y,
    })
  }

  const soltar = () => { arrastando.current = null }

  // `medida` entra na conta só para amarrar o recálculo ao ciclo de render.
  void medida
  const percentual = Math.round((escala / (escalaReal() || 1)) * 100)

  return (
    <div className="palco-envolucro">
      <div
        ref={areaRef}
        className="palco"
        data-arrastavel={escala > 1}
        onWheel={src ? aoRolar : undefined}
        onMouseDown={aoPressionar}
        onMouseMove={aoMover}
        onMouseUp={soltar}
        onMouseLeave={soltar}
        onDoubleClick={() => (escala > 1 ? ajustar() : setEscala(escalaReal()))}
      >
        {src && ehAudio ? <audio src={src} controls preload="metadata" /> : src && ehVideo ? (
          /* Video tem controles proprios do navegador e nao entra no zoom por
             arrasto: arrastar dentro de um player e para procurar na linha do
             tempo, nao para mover a imagem. Roubar esse gesto quebraria o
             player sem dar nada em troca. */
          <video
            key={src}
            src={src}
            controls
            loop
            autoPlay
            // MUDO ao abrir, de proposito. Antes era `muted={false}`: bastava
            // clicar numa miniatura para o audio comecar a tocar sozinho e
            // repetir em laco — o usuario ouviu uma respiracao gerada saindo
            // do fone sem saber de onde vinha. Som so quando ele pedir, pelo
            // controle do proprio player.
            muted
            playsInline
            className="video-palco"
          />
        ) : src ? (
          <img
            ref={imgRef}
            src={src}
            alt=""
            draggable={false}
            onLoad={() => remedir((n) => n + 1)}
            style={{
              transform: `translate(${deslocamento.x}px, ${deslocamento.y}px) scale(${escala})`,
              // Acima de 1:1 o navegador deve mostrar o pixel, nao borrar.
              imageRendering: escala > escalaReal() ? 'pixelated' : 'auto',
            }}
          />
        ) : (
          <div className="vazio">
            <div className="vazio-simbolo" aria-hidden="true">✦</div>
            <strong>Área de criação</strong>
            <p>{vazio}</p>
          </div>
        )}
      </div>

      {/* Sem zoom no video: os botoes nao teriam efeito, e um controle que
          nao faz nada e pior que controle nenhum. */}
      {src && !ehVideo && !ehAudio && (
        <div className="controles-zoom">
          <button className="mini" onClick={() => aplicarZoom(1 / 1.25)} title="Reduzir">−</button>
          <span className="valor-zoom">{percentual}%</span>
          <button className="mini" onClick={() => aplicarZoom(1.25)} title="Ampliar">+</button>
          <button className="mini" onClick={ajustar}>Ajustar</button>
          <button className="mini" onClick={() => { setEscala(escalaReal()); setDeslocamento({ x: 0, y: 0 }) }}>
            Pixels reais
          </button>
        </div>
      )}
    </div>
  )
}
