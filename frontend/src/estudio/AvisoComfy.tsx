// Faixa no topo quando o motor e local e o ComfyUI nao responde: sem ela, quem
// abria o EasyComfee sem o ComfyUI aberto via o app normal e nada gerava. Le o
// retrato do backend (andamento.py, motor_respondendo) e some sozinha quando o
// ComfyUI sobe. No modo Comfy Cloud nao aparece: la nao se usa o ComfyUI local.
import { useContext, useEffect, useState } from 'react'
import { MotorCtx } from './motor'

// Uma faixa so: "subindo" (o app acabou de abrir) e "fora" viravam duas mensagens.
export default function AvisoComfy({ subindo = false }: { subindo?: boolean }) {
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
  if (!(fora || subindo) || naNuvem) return null
  return (
    <div className="hf-aviso-comfy" role="status"
      title="If it doesn't come up, open ComfyUI (ComfyUI Desktop, or run_nvidia_gpu.bat in the portable folder). No GPU? Use Comfy Cloud in Config Models.">
      <b>ComfyUI is starting…</b> about a minute or two after the PC starts. Not coming up? Open ComfyUI, or use Comfy Cloud in Config Models.
    </div>
  )
}
