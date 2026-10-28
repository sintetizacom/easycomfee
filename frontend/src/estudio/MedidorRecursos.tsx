// Medidor de recursos da barra de cima: RAM e VRAM com barrinhas (CPU e GPU no
// detalhe). Le o retrato que o backend tira a cada 2 s (andamento.py), so com a
// aba visivel. Sem placa NVIDIA, mostra so a RAM.
import { useEffect, useState } from 'react'

type Retrato = {
  ram: { usada_gib: number; total_gib: number } | null
  gpu: { vram_usada_gib: number; vram_total_gib: number; uso_pct: number } | null
  cpu_pct: number | null
}

const nivel = (f: number) => (f >= 0.9 ? 'alto' : f >= 0.7 ? 'medio' : 'ok')
const gb = (v: number) => (v >= 10 ? v.toFixed(0) : v.toFixed(1))

function Barra({ rotulo, usada, total }: { rotulo: string; usada: number; total: number }) {
  const f = total ? Math.min(1, usada / total) : 0
  return (
    <span className="hf-rec-item" data-nivel={nivel(f)}>
      <b>{rotulo}</b>
      <span className="hf-rec-barra"><i style={{ width: `${Math.round(f * 100)}%` }} /></span>
      <span>{gb(usada)}/{Math.round(total)}</span>
    </span>
  )
}

export default function MedidorRecursos() {
  const [r, setR] = useState<Retrato | null>(null)
  useEffect(() => {
    let vivo = true
    const ler = () => {
      if (document.hidden) return
      fetch('/api/andamento', { cache: 'no-store' }).then((x) => x.json()).then((d) => { if (vivo) setR(d) }).catch(() => {})
    }
    ler()
    const t = setInterval(ler, 2000)
    return () => { vivo = false; clearInterval(t) }
  }, [])
  if (!r?.ram) return null
  const dica = [
    `RAM ${r.ram.usada_gib.toFixed(1)} of ${r.ram.total_gib.toFixed(1)} GB`,
    r.gpu && `VRAM ${r.gpu.vram_usada_gib.toFixed(1)} of ${r.gpu.vram_total_gib.toFixed(1)} GB · GPU ${Math.round(r.gpu.uso_pct)}%`,
    r.cpu_pct !== null && `CPU ${Math.round(r.cpu_pct)}%`,
  ].filter(Boolean).join('\n')
  return (
    <div className="hf-recursos" title={dica} aria-label="Computer resources">
      <Barra rotulo="RAM" usada={r.ram.usada_gib} total={r.ram.total_gib} />
      {r.gpu && <Barra rotulo="VRAM" usada={r.gpu.vram_usada_gib} total={r.gpu.vram_total_gib} />}
    </div>
  )
}
