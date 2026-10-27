import { useEffect, useRef, useState } from 'react'

// Janela flutuante (picture-in-picture) para a previa do rosto. Na coluna
// lateral a previa ficava pequena e abaixo dos controles: para ver o olhar
// mudar era preciso rolar e forcar a vista. Aqui ela fica por cima da tela,
// com zoom e comparacao com o original.

type Caixa = { x: number; y: number; w: number; h: number }
const CHAVE = 'pip-rosto'
const PADRAO: Caixa = { x: 0, y: 0, w: 420, h: 340 }

function lerCaixa(): Caixa {
  try {
    const c = JSON.parse(localStorage.getItem(CHAVE) ?? '')
    if (c && typeof c.x === 'number') return c
  } catch { /* sem armazenamento: usa o padrao */ }
  return { ...PADRAO, x: window.innerWidth - PADRAO.w - 24, y: window.innerHeight - PADRAO.h - 24 }
}

export default function JanelaPip({ src, original, calculando, aoFechar }: {
  src: string | null; original: string; calculando: boolean; aoFechar: () => void
}) {
  const [caixa, setCaixa] = useState<Caixa>(lerCaixa)
  const [zoom, setZoom] = useState(1)
  const [desloc, setDesloc] = useState({ x: 0, y: 0 })
  const [vendoOriginal, setVendoOriginal] = useState(false)
  const janela = useRef<HTMLDivElement>(null)

  useEffect(() => {
    try { localStorage.setItem(CHAVE, JSON.stringify(caixa)) } catch { /* ignora */ }
  }, [caixa])

  // O redimensionamento e o do proprio navegador (resize: both); aqui so
  // anotamos o tamanho final para lembrar na proxima vez.
  useEffect(() => {
    const el = janela.current
    if (!el) return
    const obs = new ResizeObserver(() =>
      setCaixa((c) => (c.w === el.offsetWidth && c.h === el.offsetHeight
        ? c : { ...c, w: el.offsetWidth, h: el.offsetHeight })))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const arrastar = (ini: React.PointerEvent, mover: (dx: number, dy: number) => void) => {
    const x0 = ini.clientX, y0 = ini.clientY
    const mov = (e: PointerEvent) => mover(e.clientX - x0, e.clientY - y0)
    const fim = () => { window.removeEventListener('pointermove', mov); window.removeEventListener('pointerup', fim) }
    window.addEventListener('pointermove', mov)
    window.addEventListener('pointerup', fim)
  }

  const moverJanela = (e: React.PointerEvent) => {
    const { x, y } = caixa
    arrastar(e, (dx, dy) => setCaixa((c) => ({
      ...c,
      x: Math.min(Math.max(x + dx, 0), window.innerWidth - 120),
      y: Math.min(Math.max(y + dy, 0), window.innerHeight - 40),
    })))
  }

  const moverImagem = (e: React.PointerEvent) => {
    if (zoom <= 1) return
    const { x, y } = desloc
    arrastar(e, (dx, dy) => setDesloc({ x: x + dx, y: y + dy }))
  }

  const rodar = (e: React.WheelEvent) => {
    const novo = Math.min(6, Math.max(1, zoom * (e.deltaY < 0 ? 1.2 : 1 / 1.2)))
    setZoom(novo)
    if (novo === 1) setDesloc({ x: 0, y: 0 })
  }

  const imagem = vendoOriginal || !src ? original : src

  return (
    <div ref={janela} className="janela-pip" role="dialog" aria-label="Prévia do rosto em janela flutuante"
         style={{ left: caixa.x, top: caixa.y, width: caixa.w, height: caixa.h }}>
      <div className="barra-pip" onPointerDown={moverJanela}>
        <span>Prévia do rosto{calculando ? ' · calculando…' : ''}{vendoOriginal ? ' · ORIGINAL' : ''}</span>
        <div className="botoes-pip" onPointerDown={(e) => e.stopPropagation()}>
          <span className="zoom-pip">{zoom.toFixed(1).replace('.', ',')}×</span>
          <button type="button" title="Voltar ao tamanho inteiro"
                  onClick={() => { setZoom(1); setDesloc({ x: 0, y: 0 }) }}>1:1</button>
          <button type="button" title="Segure para ver a foto original"
                  onPointerDown={() => setVendoOriginal(true)}
                  onPointerUp={() => setVendoOriginal(false)}
                  onPointerLeave={() => setVendoOriginal(false)}>Original</button>
          <button type="button" title="Fechar a janela" aria-label="Fechar" onClick={aoFechar}>✕</button>
        </div>
      </div>
      <div className="area-pip" onWheel={rodar} onPointerDown={moverImagem}
           style={{ cursor: zoom > 1 ? 'grab' : 'default' }}>
        <img src={imagem} alt={vendoOriginal ? 'foto original' : 'prévia do rosto'} draggable={false}
             style={{ transform: `translate(${desloc.x}px, ${desloc.y}px) scale(${zoom})` }} />
        {!src && !vendoOriginal && <p className="aviso-pip">Mexa num controle para ver o ajuste aqui.</p>}
      </div>
      <p className="dica-pip">Roda do mouse: zoom · arraste a imagem para enquadrar os olhos</p>
    </div>
  )
}
