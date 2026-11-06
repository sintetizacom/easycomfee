import { useEffect, useState } from 'react'

type Estado = { vivo: boolean; pode_ligar: boolean }

/** Aparece so com o ComfyUI local fora e quando o app sabe liga-lo. A subida leva cerca de 40 s. */
export default function BotaoLigarMotor() {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [ligando, setLigando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let vivo = true
    const ler = () => {
      if (document.hidden) return
      fetch('/api/comfy/estado', { cache: 'no-store' }).then((r) => r.json())
        .then((e: Estado) => {
          if (!vivo) return
          setEstado(e)
          if (e.vivo) setLigando(false)
        })
        .catch(() => {})
    }
    ler()
    const t = setInterval(ler, 5000)
    return () => { vivo = false; clearInterval(t) }
  }, [])

  if (!estado || estado.vivo || !estado.pode_ligar) return null

  const ligar = async () => {
    setLigando(true)
    setErro('')
    try {
      const r = await fetch('/api/comfy/ligar', { method: 'POST' })
      const corpo = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(corpo.detail ?? 'Could not start ComfyUI.')
      // Se o motor nao responder, o botao volta para tentar de novo.
      setTimeout(() => setLigando(false), 90000)
    } catch (e) {
      setLigando(false)
      setErro(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <button type="button" className="hf-botao-modelos" onClick={ligar}
            disabled={ligando} title={erro || 'Start ComfyUI'}>
      {ligando ? 'Starting ComfyUI…' : erro ? 'Try again' : 'Start ComfyUI'}
    </button>
  )
}
