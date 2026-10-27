import { useRef, useState, type ReactNode } from 'react'

// Bolinha com "?" que revela o texto de ajuda ao passar o mouse.
//
// POR QUE existe: a lateral tem 370 px, e as explicacoes ocupavam mais espaco
// que os proprios controles — a tela ficava esmagada. O texto continua ali,
// so deixa de competir com o que se usa o tempo todo.
//
// O popup e `position: fixed`, e nao absoluto. A lateral tem rolagem propria
// (`overflow-y: auto`), e qualquer coisa posicionada dentro dela seria CORTADA
// na borda. Fixo, ele flutua acima de tudo; a posicao e calculada na hora de
// abrir, a partir de onde a bolinha esta na tela.
//
// Abre no foco tambem, nao so no mouse: quem navega por teclado precisa
// alcancar a mesma informacao.

// Precisa casar com o max-width de .ajuda-popup no estilo.css.
const LARGURA = 290
const MARGEM = 8

type Props = {
  children: ReactNode
  /** Rotulo para leitor de tela; o padrao serve para a maioria dos casos. */
  titulo?: string
}

export default function Ajuda({ children, titulo = 'Ajuda' }: Props) {
  const [aberto, setAberto] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0, acima: false })
  const botao = useRef<HTMLButtonElement>(null)

  const abrir = () => {
    const b = botao.current?.getBoundingClientRect()
    if (!b) return
    // Abre para baixo por padrao; para cima quando nao ha espaco embaixo,
    // senao o texto sairia da janela na parte de baixo do painel.
    const acima = b.bottom + 180 > window.innerHeight

    // MEDIDO: centralizar no botao jogava o popup para fora pela ESQUERDA
    // (left: -6) quando a bolinha ficava perto da borda da lateral, que tem
    // so 370 px. O centro e limitado para que a caixa inteira caiba na janela.
    const meia = LARGURA / 2
    const centro = b.left + b.width / 2
    const x = Math.min(Math.max(centro, meia + MARGEM), window.innerWidth - meia - MARGEM)

    setPos({ x, y: acima ? b.top - 8 : b.bottom + 8, acima })
    setAberto(true)
  }

  return (
    <>
      <button
        ref={botao}
        type="button"
        className="ajuda-bolinha"
        aria-label={titulo}
        onMouseEnter={abrir}
        onMouseLeave={() => setAberto(false)}
        onFocus={abrir}
        onBlur={() => setAberto(false)}
        // Em toque nao ha "passar o mouse": o clique alterna.
        onClick={(e) => {
          e.preventDefault()
          aberto ? setAberto(false) : abrir()
        }}
      >
        ?
      </button>
      {aberto && (
        <span
          className="ajuda-popup"
          role="tooltip"
          style={{
            left: pos.x,
            top: pos.y,
            transform: `translate(-50%, ${pos.acima ? '-100%' : '0'})`,
          }}
        >
          {children}
        </span>
      )}
    </>
  )
}
