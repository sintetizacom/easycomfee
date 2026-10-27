import { useRef, useState } from 'react'
import type { Elemento } from '../api'
import { Chips } from './comum'

// Ideogram 4 layout: draw text and object boxes on a canvas in the target
// aspect ratio, before generating. Ideogram reads each bbox as [y1, x1, y2, x2]
// normalized 0-1000 on both axes from the top-left corner; since each axis is
// normalized on its own, drawing on a canvas of the right ratio already gives
// the right numbers. Same contract as the Advanced editor (EditorCaixas).

type Props = {
  proporcao: string
  elementos: Elemento[]
  aoMudar: (e: Elemento[]) => void
  fundo: string
  aoMudarFundo: (f: string) => void
  pensando: boolean
  aoSugerir: () => void
  podeSugerir: boolean
}

type Gesto = { i: number; y: number; x: number; canto: boolean }

const prender = (v: number) => Math.max(0, Math.min(1000, v))

export default function LayoutIdeogram({ proporcao, elementos, aoMudar, fundo, aoMudarFundo,
                                         pensando, aoSugerir, podeSugerir }: Props) {
  const telaRef = useRef<HTMLDivElement>(null)
  const [tipo, setTipo] = useState<Elemento['tipo']>('text')
  const [ativo, setAtivo] = useState<number | null>(null)
  const [desenhando, setDesenhando] = useState<Elemento['bbox'] | null>(null)
  const gesto = useRef<Gesto | null>(null)
  const [l, a] = proporcao.split(':').map(Number)

  const ponto = (e: React.PointerEvent) => {
    const r = telaRef.current!.getBoundingClientRect()
    return { y: prender(((e.clientY - r.top) / r.height) * 1000), x: prender(((e.clientX - r.left) / r.width) * 1000) }
  }

  const pressionar = (e: React.PointerEvent) => {
    if (e.target !== telaRef.current) return
    telaRef.current!.setPointerCapture(e.pointerId)
    const { y, x } = ponto(e)
    setDesenhando([y, x, y, x]); setAtivo(null)
  }

  const mover = (e: React.PointerEvent) => {
    const { y, x } = ponto(e)
    if (desenhando) { setDesenhando([desenhando[0], desenhando[1], y, x]); return }
    const g = gesto.current
    if (!g) return
    const b = elementos[g.i].bbox
    const dy = y - g.y, dx = x - g.x
    // Corner handle resizes; anywhere else on the box moves it.
    const nova: Elemento['bbox'] = g.canto
      ? [b[0], b[1], prender(Math.max(b[0] + 20, b[2] + dy)), prender(Math.max(b[1] + 20, b[3] + dx))]
      : (() => {
          const ddy = Math.max(-b[0], Math.min(1000 - b[2], dy)), ddx = Math.max(-b[1], Math.min(1000 - b[3], dx))
          return [b[0] + ddy, b[1] + ddx, b[2] + ddy, b[3] + ddx]
        })()
    gesto.current = { ...g, y, x }
    aoMudar(elementos.map((el, j) => (j === g.i ? { ...el, bbox: nova } : el)))
  }

  const soltar = () => {
    gesto.current = null
    if (!desenhando) return
    const [ya, xa, yb, xb] = desenhando
    setDesenhando(null)
    // A click without a drag would make a zero-size box.
    if (Math.abs(yb - ya) < 15 || Math.abs(xb - xa) < 15) return
    const bbox: Elemento['bbox'] = [Math.round(Math.min(ya, yb)), Math.round(Math.min(xa, xb)),
                                    Math.round(Math.max(ya, yb)), Math.round(Math.max(xa, xb))]
    aoMudar([...elementos, { tipo, bbox, texto: '', desc: '' }])
    setAtivo(elementos.length)
  }

  const pegar = (i: number, canto: boolean) => (e: React.PointerEvent) => {
    e.stopPropagation()
    telaRef.current!.setPointerCapture(e.pointerId)
    setAtivo(i)
    gesto.current = { i, ...ponto(e), canto }
  }

  const atualizar = (i: number, campos: Partial<Elemento>) =>
    aoMudar(elementos.map((el, j) => (j === i ? { ...el, ...campos } : el)))

  const posicao = (b: Elemento['bbox']) => ({
    top: `${b[0] / 10}%`, left: `${b[1] / 10}%`, height: `${(b[2] - b[0]) / 10}%`, width: `${(b[3] - b[1]) / 10}%`,
  })

  return (
    <div className="hf-layout">
      <div className="hf-layout-palco">
        <div className="hf-linha-controles">
          <Chips rotulo="New box" opcoes={[{ id: 'text', rotulo: 'T  Text' }, { id: 'obj', rotulo: '▢  Object' }]}
            valor={tipo} aoMudar={setTipo} />
          <button type="button" className="hf-botao-sec" disabled={!podeSugerir || pensando} onClick={aoSugerir}>
            {pensando ? 'Writing the layout…' : '✦ Suggest from my prompt'}
          </button>
          {elementos.length > 0 && <button type="button" className="hf-botao-sec" onClick={() => { aoMudar([]); setAtivo(null) }}>Clear</button>}
        </div>
        <div ref={telaRef} className="hf-tela-layout" style={{ aspectRatio: `${l || 1} / ${a || 1}` }}
          onPointerDown={pressionar} onPointerMove={mover} onPointerUp={soltar}>
          {elementos.length === 0 && !desenhando && (
            <span className="hf-tela-vazia">Drag to draw a {tipo === 'text' ? 'text' : 'object'} box</span>
          )}
          {elementos.map((el, i) => (
            <div key={i} className="hf-caixa" data-tipo={el.tipo} data-ativo={ativo === i}
              style={posicao(el.bbox)} onPointerDown={pegar(i, false)}>
              <span>{el.tipo === 'text' ? (el.texto || 'Text') : (el.desc || 'Object')}</span>
              <i className="hf-caixa-canto" onPointerDown={pegar(i, true)} />
            </div>
          ))}
          {desenhando && (
            <div className="hf-caixa" data-tipo={tipo} style={posicao([
              Math.min(desenhando[0], desenhando[2]), Math.min(desenhando[1], desenhando[3]),
              Math.max(desenhando[0], desenhando[2]), Math.max(desenhando[1], desenhando[3])])} />
          )}
        </div>
      </div>

      <div className="hf-layout-lista">
        <label className="hf-equip">
          <span className="hf-grupo-rotulo">Background</span>
          <textarea value={fundo} onChange={(e) => aoMudarFundo(e.target.value)} rows={2}
            placeholder="e.g. a soft cream paper texture with warm light" />
        </label>
        {elementos.map((el, i) => (
          <div key={i} className="hf-equip hf-elemento" data-ativo={ativo === i} onClick={() => setAtivo(i)}>
            <div className="hf-elemento-topo">
              <button type="button" className="hf-botao-sec"
                onClick={() => atualizar(i, { tipo: el.tipo === 'text' ? 'obj' : 'text' })}>
                {el.tipo === 'text' ? 'T  Text' : '▢  Object'}
              </button>
              <button type="button" className="hf-botao-sec" onClick={() => { aoMudar(elementos.filter((_, j) => j !== i)); setAtivo(null) }}>Remove</button>
            </div>
            {el.tipo === 'text' && (
              <input className="hf-campo" value={el.texto ?? ''} placeholder="The exact words to print"
                onChange={(e) => atualizar(i, { texto: e.target.value })} />
            )}
            <input className="hf-campo" value={el.desc}
              placeholder={el.tipo === 'text' ? 'Style: font, color, weight' : 'What it is and how it looks'}
              onChange={(e) => atualizar(i, { desc: e.target.value })} />
          </div>
        ))}
        {elementos.length === 0 && (
          <p className="hf-dica">Text boxes print exactly the words you type. Object boxes place a thing or a person.
            Or let the model suggest a layout from your prompt, then adjust it.</p>
        )}
      </div>
    </div>
  )
}
