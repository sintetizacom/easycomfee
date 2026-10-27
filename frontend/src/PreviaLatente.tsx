import { useState } from 'react'
import { api } from './api'

/* Prévia do que o espaço latente do LTX perde.
 *
 * Não é estimativa: o backend roda o `encode -> decode` de verdade, que é a
 * etapa exata onde o método de ampliar no latente destrói o que for pequeno no
 * quadro. Sai em poucos segundos porque usa só uma janela do vídeo.
 *
 * A LUPA é o componente, não um enfeite. A primeira versão mostrava os dois
 * quadros lado a lado, no tamanho da tela, e eles pareciam IGUAIS — o rosto
 * derretido ocupava 60 px. O dano só aparece a 1:1.
 *
 * E quem aponta onde olhar é o usuário, de propósito. Tentei escolher a região
 * por métrica: ela apontou o brilho da jaqueta, que muda muito em número e nada
 * aos olhos, enquanto o rosto derretido passou batido. Ver o NOTAS-MOTOR.
 */

const LADO_LUPA = 190 // lado da janela ampliada, em pixels de tela
// 3x deixava o bloco de pixels grande demais para julgar: via-se o mosaico, nao
// o rosto. 2,5x ainda mostra o pixel real, sem que ele domine.
const AUMENTO = 2.5

type Par = { antes: string; depois: string; tamanho: { largura: number; altura: number } }

export default function PreviaLatente({ referencia, aoFechar }: {
  referencia: string
  aoFechar: () => void
}) {
  const [par, setPar] = useState<Par | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  // Posição relativa (0..1) do ponto sob o cursor; null esconde a lupa.
  const [ponto, setPonto] = useState<{ x: number; y: number } | null>(null)

  const rodar = async () => {
    setCarregando(true)
    setErro('')
    try {
      setPar(await api.previaLatente(referencia))
    } catch (e) {
      setErro(String(e))
    } finally {
      setCarregando(false)
    }
  }

  /* A posicao e medida dentro da IMAGEM sob o cursor, nao do contêiner: o
     contêiner tem os dois painéis lado a lado, e medir nele faria a lupa
     apontar para metade do lugar certo. */
  const mover = (e: React.MouseEvent<HTMLImageElement>) => {
    const alvo = e.currentTarget.getBoundingClientRect()
    setPonto({
      x: Math.min(1, Math.max(0, (e.clientX - alvo.left) / alvo.width)),
      y: Math.min(1, Math.max(0, (e.clientY - alvo.top) / alvo.height)),
    })
  }

  /* A lupa em CSS: a imagem entra como fundo, ampliada, e a posição do fundo
     acompanha o cursor. Os dois painéis usam o MESMO ponto — comparar regiões
     diferentes não compararia nada. */
  const lupa = (fonte: string) => {
    if (!ponto || !par) return {}
    const l = par.tamanho.largura * AUMENTO
    const a = par.tamanho.altura * AUMENTO
    return {
      backgroundImage: `url(${fonte})`,
      backgroundSize: `${l}px ${a}px`,
      backgroundPosition: `${-(ponto.x * l - LADO_LUPA / 2)}px ${-(ponto.y * a - LADO_LUPA / 2)}px`,
    }
  }

  return (
    <div className="previa-latente">
      <div className="linha-ajuda">
        <strong>O que o latente perde</strong>
        <button className="mini" onClick={aoFechar} title="Fechar">×</button>
      </div>

      {!par && (
        <>
          <p className="dica">
            O método <strong>no latente</strong> passa o vídeo por um espaço
            comprimido, e o que for pequeno no quadro se perde ali. Isto roda
            só essa etapa, no seu vídeo, em alguns segundos — antes de você
            gastar os minutos da ampliação.
          </p>
          <button className="principal" onClick={rodar} disabled={carregando}>
            {carregando ? 'Rodando a prévia…' : 'Ver o que se perde'}
          </button>
        </>
      )}

      {erro && <p className="custo alerta">{erro}</p>}

      {par && (
        <>
          <p className="dica">
            Passe o mouse sobre a imagem: a lupa mostra o mesmo ponto nos dois,
            em {String(AUMENTO).replace('.', ',')}×. Olhe rostos e objetos pequenos.
          </p>
          {/* As lupas ficam ACIMA das imagens: com o mouse sobre a imagem,
              olhar para baixo tira o detalhe do campo de visão. A altura é
              reservada mesmo sem cursor, senão o bloco pula quando aparece. */}
          <div className="previa-lupas" style={{ height: LADO_LUPA + 20 }}>
            {ponto ? (
              <>
                {/* Rotulo na propria lupa: as legendas das imagens ficam
                    abaixo delas, longe daqui, e comparacao mal rotulada e
                    pior que comparacao nenhuma. */}
                <figure className="com-lupa">
                  <div className="lupa" style={{ width: LADO_LUPA, height: LADO_LUPA, ...lupa(par.antes) }} />
                  <figcaption>seu vídeo</figcaption>
                </figure>
                <figure className="com-lupa">
                  <div className="lupa" style={{ width: LADO_LUPA, height: LADO_LUPA, ...lupa(par.depois) }} />
                  <figcaption>depois do latente</figcaption>
                </figure>
              </>
            ) : (
              <p className="dica vazio-lupa">a lupa aparece aqui</p>
            )}
          </div>

          <div className="previa-par" onMouseLeave={() => setPonto(null)}>
            <figure>
              <img src={par.antes} alt="quadro original" onMouseMove={mover} />
              <figcaption>seu vídeo</figcaption>
            </figure>
            <figure>
              <img src={par.depois} alt="quadro depois do latente" onMouseMove={mover} />
              <figcaption>depois do latente</figcaption>
            </figure>
          </div>
        </>
      )}
    </div>
  )
}
