import { useRef, useState } from 'react'
import type { Elemento, Zonas } from './api'

// O Ideogram 4 usa bbox [y1, x1, y2, x2] normalizada de 0 a 1000 nos dois
// eixos, com origem no canto superior esquerdo. Como a normalizacao e
// independente por eixo, desenhar sobre uma tela na proporcao alvo ja produz
// as coordenadas certas: basta dividir pelo tamanho da tela.

type Props = {
  proporcao: string
  elementos: Elemento[]
  aoMudar: (e: Elemento[]) => void
  // Foto de fundo, quando houver. Sem ela o usuario posiciona as caixas as
  // cegas — foi assim que o texto foi parar em cima do letreiro da mercearia
  // e dos olhos do retrato.
  fundo?: string
  // Alturas da foto ja ocupadas por rosto ou letreiro. Marcadas na tela para
  // o usuario ver onde nao pousar texto ANTES de gerar.
  zonas?: Zonas | null
}

function proporcaoParaFracao(p: string) {
  const [l, a] = p.split(':').map(Number)
  return l && a ? l / a : 1
}

export default function EditorCaixas({ proporcao, elementos, aoMudar,
                                      fundo, zonas }: Props) {
  const telaRef = useRef<HTMLDivElement>(null)
  const [ativo, setAtivo] = useState<number | null>(null)
  const [desenhando, setDesenhando] = useState<Elemento['bbox'] | null>(null)
  const arraste = useRef<{ i: number; y: number; x: number } | null>(null)

  const fracao = proporcaoParaFracao(proporcao)

  /** Converte um evento do mouse em coordenadas 0-1000 (y, x). */
  const paraNormal = (e: React.MouseEvent) => {
    const r = telaRef.current!.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * 1000
    const y = ((e.clientY - r.top) / r.height) * 1000
    return { y: Math.max(0, Math.min(1000, y)), x: Math.max(0, Math.min(1000, x)) }
  }

  const aoPressionar = (e: React.MouseEvent) => {
    if (e.target !== telaRef.current) return
    const { y, x } = paraNormal(e)
    setDesenhando([y, x, y, x])
    setAtivo(null)
  }

  const aoMover = (e: React.MouseEvent) => {
    if (desenhando) {
      const { y, x } = paraNormal(e)
      setDesenhando([desenhando[0], desenhando[1], y, x])
      return
    }
    if (arraste.current) {
      const { y, x } = paraNormal(e)
      const { i, y: y0, x: x0 } = arraste.current
      const dy = y - y0
      const dx = x - x0
      const b = elementos[i].bbox
      const prender = (v: number) => Math.max(0, Math.min(1000, v))
      const novo = [...elementos]
      novo[i] = {
        ...novo[i],
        bbox: [prender(b[0] + dy), prender(b[1] + dx),
               prender(b[2] + dy), prender(b[3] + dx)],
      }
      arraste.current = { i, y, x }
      aoMudar(novo)
    }
  }

  const aoSoltar = () => {
    arraste.current = null
    if (!desenhando) return
    const [ya, xa, yb, xb] = desenhando
    setDesenhando(null)
    // Ignora cliques sem arrasto, que criariam caixas de area zero.
    if (Math.abs(yb - ya) < 15 || Math.abs(xb - xa) < 15) return
    const bbox: Elemento['bbox'] = [
      Math.round(Math.min(ya, yb)), Math.round(Math.min(xa, xb)),
      Math.round(Math.max(ya, yb)), Math.round(Math.max(xa, xb)),
    ]
    aoMudar([...elementos, { tipo: 'text', bbox, texto: '', desc: '' }])
    setAtivo(elementos.length)
  }

  const atualizar = (i: number, campos: Partial<Elemento>) => {
    const novo = [...elementos]
    novo[i] = { ...novo[i], ...campos }
    aoMudar(novo)
  }

  const remover = (i: number) => {
    aoMudar(elementos.filter((_, j) => j !== i))
    setAtivo(null)
  }

  const estilo = (b: Elemento['bbox']) => ({
    top: `${b[0] / 10}%`,
    left: `${b[1] / 10}%`,
    height: `${(b[2] - b[0]) / 10}%`,
    width: `${(b[3] - b[1]) / 10}%`,
  })

  return (
    <div>
      <div
        ref={telaRef}
        className="tela-caixas"
        style={{ aspectRatio: String(fracao) }}
        onMouseDown={aoPressionar}
        onMouseMove={aoMover}
        onMouseUp={aoSoltar}
        onMouseLeave={aoSoltar}
      >
        {/* A foto fica ATRAS e nao recebe evento: clicar nela tem de comecar
            uma caixa nova, como acontece na tela vazia. Atenuada, porque o
            que se le aqui sao as caixas, nao a imagem. */}
        {fundo && <img className="fundo-da-tela" src={fundo} alt="" />}
        {(zonas?.rostos ?? []).map(([a, b], i) => (
          <div key={`r${i}`} className="zona" data-tipo="rosto"
               style={{ top: `${a / 10}%`, height: `${(b - a) / 10}%` }}>
            rosto
          </div>
        ))}
        {(zonas?.letreiros ?? []).map(([a, b], i) => (
          <div key={`l${i}`} className="zona" data-tipo="letreiro"
               style={{ top: `${a / 10}%`, height: `${(b - a) / 10}%` }}>
            letreiro na foto
          </div>
        ))}
        {elementos.map((el, i) => (
          <div
            key={i}
            className="caixa"
            data-ativo={ativo === i}
            data-tipo={el.tipo}
            style={estilo(el.bbox)}
            onMouseDown={(e) => {
              e.stopPropagation()
              setAtivo(i)
              const { y, x } = paraNormal(e)
              arraste.current = { i, y, x }
            }}
          >
            {el.tipo === 'text' ? el.texto || 'texto' : el.desc || 'objeto'}
          </div>
        ))}
        {desenhando && (
          <div
            className="caixa"
            style={estilo([
              Math.min(desenhando[0], desenhando[2]),
              Math.min(desenhando[1], desenhando[3]),
              Math.max(desenhando[0], desenhando[2]),
              Math.max(desenhando[1], desenhando[3]),
            ])}
          />
        )}
      </div>

      <p className="dica">
        Arraste na tela para criar um elemento. Clique numa caixa para editar ou
        mover. As coordenadas acompanham a proporção escolhida.
      </p>

      <div className="lista-elementos">
        {elementos.map((el, i) => (
          <div key={i} className="item-elemento" data-ativo={ativo === i}
               onClick={() => setAtivo(i)}>
            <header>
              <button
                className="mini"
                onClick={() => atualizar(i, { tipo: el.tipo === 'text' ? 'obj' : 'text' })}
              >
                {el.tipo === 'text' ? 'texto' : 'objeto'}
              </button>
              <span className="espaco">
                y {Math.round(el.bbox[0])}–{Math.round(el.bbox[2])} · x{' '}
                {Math.round(el.bbox[1])}–{Math.round(el.bbox[3])}
              </span>
              <button className="mini" onClick={() => remover(i)}>remover</button>
            </header>
            {el.tipo === 'text' && (
              <input
                placeholder="Texto exato que deve aparecer"
                value={el.texto ?? ''}
                onChange={(e) => atualizar(i, { texto: e.target.value })}
                style={{ marginBottom: 6 }}
              />
            )}
            <textarea
              placeholder={
                el.tipo === 'text'
                  ? 'Como esse texto deve parecer: tipografia, cor, peso'
                  : 'O que é esse objeto e como ele aparece'
              }
              value={el.desc}
              onChange={(e) => atualizar(i, { desc: e.target.value })}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
