import { useEffect, useState } from 'react'

// Escolhe onde as gerações rodam: no ComfyUI desta máquina ou na Comfy Cloud.
// A troca vale para as próximas gerações; o backend recusa trocar no meio de
// uma. Na nuvem, o que não existe lá aparece como "só local" nos seletores.

type Estado = { modo: 'local' | 'nuvem'; chave_nuvem: boolean; link_recarga?: string }

export default function SeletorMotor({ aoTrocar }: { aoTrocar: (modo: string) => void }) {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/motor').then((r) => r.json()).then(setEstado).catch(() => {})
  }, [])

  const trocar = async (modo: 'local' | 'nuvem') => {
    setErro(null)
    const r = await fetch('/api/motor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modo }),
    })
    const corpo = await r.json().catch(() => ({}))
    if (!r.ok) { setErro(corpo.detail ?? 'Could not switch.'); return }
    setEstado(corpo)
    aoTrocar(corpo.modo)
  }

  if (!estado) return null
  return (
    <div className="seletor-motor" role="group" aria-label="Where to run">
      <button type="button" data-ativo={estado.modo === 'local'} aria-pressed={estado.modo === 'local'}
        onClick={() => trocar('local')} title="Run on the ComfyUI of this machine, with your GPU.">
        Local
      </button>
      <button type="button" data-ativo={estado.modo === 'nuvem'} aria-pressed={estado.modo === 'nuvem'}
        onClick={() => trocar('nuvem')}
        title={estado.chave_nuvem ? 'Run on Comfy Cloud, with your account credits.' : 'Add your Comfy Cloud API key first.'}>
        Comfy Cloud
      </button>
      {estado.modo === 'nuvem' && estado.link_recarga && (
        <a className="seletor-recarga" href={estado.link_recarga} target="_blank" rel="noreferrer"
          title="Add Comfy Cloud credits">Top up</a>
      )}
      {erro && <span className="selo erro" role="alert">{erro}</span>}
    </div>
  )
}
