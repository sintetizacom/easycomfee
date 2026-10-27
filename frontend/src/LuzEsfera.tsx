import { useEffect, useRef, useState } from 'react'

// A esfera mostrada aqui é a MESMA imagem que vai ao modelo como referência —
// ela vem do backend, não é desenhada aqui. Duas implementações da mesma
// iluminação divergiriam, e o usuário estaria mirando numa coisa e enviando
// outra.

type Props = {
  azimute: number
  elevacao: number
  intensidade: number
  temperatura: string
  aoMover: (azimute: number, elevacao: number) => void
}

export default function LuzEsfera({
  azimute, elevacao, intensidade, temperatura, aoMover,
}: Props) {
  const areaRef = useRef<HTMLDivElement>(null)
  const arrastando = useRef(false)
  const [frase, setFrase] = useState('')

  const parametros = new URLSearchParams({
    azimute: String(azimute), elevacao: String(elevacao),
    intensidade: String(intensidade), temperatura,
  }).toString()

  // A frase é o que mais carrega o resultado, então mostramos exatamente o que
  // será pedido ao modelo em vez de deixar o usuário adivinhar.
  useEffect(() => {
    let cancelado = false
    const t = setTimeout(() => {
      fetch(`/api/luz/frase?${parametros}`)
        .then((r) => r.json())
        .then((d) => { if (!cancelado) setFrase(d.frase) })
        .catch(() => {})
    }, 180)
    return () => { cancelado = true; clearTimeout(t) }
  }, [parametros])

  /** Converte a posição do cursor na esfera em azimute e elevação. */
  const daPosicao = (e: React.MouseEvent) => {
    const r = areaRef.current!.getBoundingClientRect()
    const raio = Math.min(r.width, r.height) / 2
    let x = (e.clientX - r.left - r.width / 2) / raio
    let y = (r.top + r.height / 2 - e.clientY) / raio
    // Fora da esfera, projeta na borda: a luz continua rasante em vez de travar.
    const d = Math.hypot(x, y)
    if (d > 1) { x /= d; y /= d }
    aoMover(
      Math.round(Math.asin(Math.max(-1, Math.min(1, x))) * (180 / Math.PI)),
      Math.round(Math.asin(Math.max(-1, Math.min(1, y))) * (180 / Math.PI)),
    )
  }

  // Posição do puxador, derivada dos ângulos — nunca guardada em separado.
  const px = Math.sin((azimute * Math.PI) / 180)
  const py = Math.sin((elevacao * Math.PI) / 180)

  return (
    <div>
      <div
        ref={areaRef}
        className="esfera-luz"
        onMouseDown={(e) => { arrastando.current = true; daPosicao(e) }}
        onMouseMove={(e) => { if (arrastando.current) daPosicao(e) }}
        onMouseUp={() => { arrastando.current = false }}
        onMouseLeave={() => { arrastando.current = false }}
      >
        <img src={`/api/luz/mapa?${parametros}`} alt="" draggable={false} />
        <span
          className="puxador-luz"
          style={{ left: `${50 + px * 50}%`, top: `${50 - py * 50}%` }}
        />
      </div>

      <div className="numeros-luz">
        <span>azimute {azimute}°</span>
        <span>elevação {elevacao}°</span>
      </div>

      {frase && <p className="frase-luz">{frase}</p>}
    </div>
  )
}
