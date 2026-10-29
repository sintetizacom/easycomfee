// Faixa no topo quando o motor e local e o ComfyUI nao responde: sem ela, quem
// abria o EasyComfee sem o ComfyUI aberto via o app normal e nada gerava. Le o
// retrato do backend (andamento.py, motor_respondendo) e some sozinha quando o
// ComfyUI sobe. No modo Comfy Cloud nao aparece: la nao se usa o ComfyUI local.
import { useContext, useEffect, useState } from 'react'
import { MotorCtx } from './motor'

export default function AvisoComfy() {
  const { naNuvem } = useContext(MotorCtx)
  const [fora, setFora] = useState(false)
  useEffect(() => {
    let vivo = true
    const ler = () => {
      if (document.hidden) return
      fetch('/api/andamento', { cache: 'no-store' }).then((r) => r.json())
        .then((d) => { if (vivo) setFora(d.motor_respondendo === false) }).catch(() => {})
    }
    ler()
    const t = setInterval(ler, 4000)
    return () => { vivo = false; clearInterval(t) }
  }, [])
  if (!fora || naNuvem) return null
  return (
    <div className="hf-aviso-comfy" role="alert">
      <b>ComfyUI isn't running.</b> Open ComfyUI first (ComfyUI Desktop, or <code>run_nvidia_gpu.bat</code> in the
      portable folder); this page connects by itself when it's up. No GPU? Use Comfy Cloud in <b>Config Models</b>.
    </div>
  )
}
