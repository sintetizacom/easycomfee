import { useEffect, useRef, useState } from 'react'

// Caixa de seleção que não joga fora o que ajuda a escolher: fechada mostra o
// item atual e a descrição dele; aberta mostra todos com as suas descrições.
// Um <select> nativo seria mais simples, mas só carrega o rótulo.

export type Opcao = {
  id: string
  rotulo: string
  descricao?: string
  segundos?: number
  /** true quando o tempo veio de medições reais, não da estimativa escrita. */
  medido?: boolean
  /** true quando escolher isto obriga a trocar o modelo carregado na GPU. */
  trocaMotor?: boolean
  /** A que grupo do menu esta opção pertence. Opcional: sem grupos, a lista
      sai plana, como antes. */
  grupo?: string
  /** Palavra curta em itálico logo depois do nome — "local", "nuvem". Vem
      DEPOIS de propósito: o nome é o que se procura na linha fechada, e o
      prefixo do grupo o empurrava para o fim. */
  sufixo?: string
}

export type Grupo = { id: string; rotulo: string }

type Props = {
  opcoes: Opcao[]
  valor: string
  aoEscolher: (id: string) => void
  rotulo: string
  grupos?: Grupo[]
}

export default function Seletor({ opcoes, valor, aoEscolher, rotulo, grupos }: Props) {
  const [aberto, setAberto] = useState(false)
  const caixaRef = useRef<HTMLDivElement>(null)
  const atual = opcoes.find((o) => o.id === valor)

  // Fecha ao clicar fora ou apertar Esc: sem isso a lista fica presa aberta
  // cobrindo o formulário.
  useEffect(() => {
    if (!aberto) return
    const clique = (e: MouseEvent) => {
      if (!caixaRef.current?.contains(e.target as Node)) setAberto(false)
    }
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') setAberto(false) }
    document.addEventListener('mousedown', clique)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('mousedown', clique)
      document.removeEventListener('keydown', tecla)
    }
  }, [aberto])

  const escolher = (id: string) => {
    aoEscolher(id)
    setAberto(false)
  }

  const mover = (delta: number) => {
    const i = opcoes.findIndex((o) => o.id === valor)
    const j = Math.min(opcoes.length - 1, Math.max(0, (i < 0 ? 0 : i) + delta))
    if (opcoes[j]) aoEscolher(opcoes[j].id)
  }

  return (
    <div className="campo">
      <label>{rotulo}</label>
      <div className="seletor" ref={caixaRef}>
        <button
          type="button"
          className="seletor-botao"
          aria-expanded={aberto}
          onClick={() => setAberto((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); aberto ? null : mover(1) }
            if (e.key === 'ArrowUp') { e.preventDefault(); aberto ? null : mover(-1) }
          }}
        >
          <span className="seletor-atual">
            <b>
              {atual?.rotulo ?? '—'}
              {atual?.sufixo && <em className="grupo-atual"> {atual.sufixo}</em>}
              {!atual?.sufixo && atual?.grupo && grupos?.length ? (
                <em className="grupo-atual">
                  {' '}· {grupos.find((g) => g.id === atual.grupo)?.rotulo}
                </em>
              ) : null}
            </b>
            {atual?.segundos !== undefined && (
              <em>~{atual.segundos}s{atual.trocaMotor && ' + carga'}</em>
            )}
          </span>
          <span className="seta-seletor" aria-hidden>{aberto ? '▴' : '▾'}</span>
        </button>

        {aberto && (
          <div className="seletor-lista" role="listbox">
            {/* Sem grupos declarados, a lista sai plana — é o caso do menu
                de geração, que tem cinco itens e não precisa de seções. */}
            {(grupos?.length
              ? grupos
                  .map((g) => [g, opcoes.filter((o) => o.grupo === g.id)] as const)
                  .filter(([, itens]) => itens.length)
              : [[null, opcoes] as const]
            ).map(([g, itens]) => (
              <div key={g?.id ?? 'todos'} className="secao-seletor">
                {g && <h4>{g.rotulo}</h4>}
                {itens.map((o) => (
                  <button
                    type="button"
                    key={o.id}
                    role="option"
                    aria-selected={o.id === valor}
                    data-ativo={o.id === valor}
                    onClick={() => escolher(o.id)}
                  >
                    <b>
                      {o.rotulo}
                      {o.segundos !== undefined && (
                        <em title={o.medido ? 'mediana das execuções reais' : 'estimativa'}>
                          {' '}· ~{o.segundos}s{o.trocaMotor && ' + carga'}
                        </em>
                      )}
                    </b>
                    {o.descricao && <small>{o.descricao}</small>}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {atual?.descricao && <p className="dica seletor-dica">{atual.descricao}</p>}
      {atual?.trocaMotor && (
        <p className="dica aviso-carga">
          Este modo usa outro modelo. Só cabe um na placa por vez, então a
          primeira geração depois de trocar leva <strong>2 a 3 minutos a
          mais</strong> só para carregar. Repetir no mesmo modo já sai rápido.
        </p>
      )}
    </div>
  )
}
