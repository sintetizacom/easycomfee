import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

// Top-right: the Comfy Cloud balance. The key itself lives in Config Models,
// out of sight; this only shows the money and the top-up link.

type Saldo = Awaited<ReturnType<typeof api.saldoNuvem>>

export default function PainelConta({ temChave, linkRecarga, abrirConfig }: {
  temChave: boolean; linkRecarga?: string; abrirConfig: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [saldo, setSaldo] = useState<Saldo | null>(null)
  const caixa = useRef<HTMLDivElement>(null)

  const ler = (forcar = false) => { if (temChave) api.saldoNuvem(forcar).then(setSaldo).catch(() => setSaldo(null)) }
  useEffect(() => {
    ler()
    // The balance changes after each paid generation; a minute is enough.
    const t = setInterval(() => ler(), 60_000)
    return () => clearInterval(t)
  }, [temChave])

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => { if (!caixa.current?.contains(e.target as Node)) setAberto(false) }
    document.addEventListener('mousedown', fora)
    return () => document.removeEventListener('mousedown', fora)
  }, [aberto])

  if (!temChave) {
    return <button type="button" className="hf-saldo" data-sem-chave onClick={abrirConfig}><span aria-hidden>☁</span> Connect Comfy Cloud</button>
  }
  const usd = saldo?.ok && saldo.usd != null ? `$${saldo.usd.toFixed(2)}` : null
  return (
    <div className="hf-conta" ref={caixa}>
      <button type="button" className="hf-saldo" onClick={() => { setAberto((a) => !a); ler(true) }} title="Comfy Cloud credits">
        <span aria-hidden>☁</span> {usd ?? 'Comfy Cloud'}
      </button>
      {aberto && (
        <div className="hf-conta-painel">
          <b>Comfy Cloud credits</b>
          <p className="hf-conta-saldo">{usd ? <><strong>{usd}</strong> available</> : saldo ? `Balance unavailable: ${saldo.motivo ?? ''}` : 'Reading…'}</p>
          {saldo?.gasto && saldo.gasto.usd > 0 && <p className="hf-dica">Spent in this app so far: ${saldo.gasto.usd.toFixed(2)}</p>}
          {linkRecarga && <a className="hf-botao-sec" href={linkRecarga} target="_blank" rel="noreferrer">Top up credits ↗</a>}
        </div>
      )}
    </div>
  )
}
