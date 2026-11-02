// Faixa no topo quando o motor e local e o ComfyUI nao responde: sem ela, quem
// abria o EasyComfee sem o ComfyUI aberto via o app normal e nada gerava. Le o
// retrato do backend (andamento.py, motor_respondendo) e some sozinha quando o
// ComfyUI sobe. No modo Comfy Cloud nao aparece: la nao se usa o ComfyUI local.
import { useContext, useEffect, useState } from 'react'
import { MotorCtx } from './motor'

// Depois disto sem resposta, a faixa deixa de dizer "esta subindo" e diz o que conferir.
const DEMORA_MS = 3 * 60 * 1000

// Uma faixa so: "subindo" (o app acabou de abrir) e "fora" viravam duas mensagens.
// Quem ja tinha ComfyUI (o instalador gravou comfy_iniciar: false): o atalho acha a porta
// dele ou abre o dele (portatil, Desktop); numa instalacao manual a pessoa abre.
export default function AvisoComfy({ subindo = false }: { subindo?: boolean }) {
  const { naNuvem } = useContext(MotorCtx)
  const [fora, setFora] = useState(false)
  const [daPessoa, setDaPessoa] = useState(false)
  const [desde, setDesde] = useState<number | null>(null)
  const [agora, setAgora] = useState(() => Date.now())
  useEffect(() => {
    fetch('/api/motor').then((r) => r.json()).then((m) => setDaPessoa(!!m?.comfy_da_pessoa)).catch(() => {})
    let vivo = true
    const ler = () => {
      setAgora(Date.now())
      if (document.hidden) return
      fetch('/api/andamento', { cache: 'no-store' }).then((r) => r.json())
        .then((d) => { if (vivo) setFora(d.motor_respondendo === false) }).catch(() => {})
    }
    ler()
    const t = setInterval(ler, 4000)
    return () => { vivo = false; clearInterval(t) }
  }, [])
  const ativo = (fora || subindo) && !naNuvem
  // Conta o tempo desde que a faixa apareceu; zera quando o ComfyUI responde.
  useEffect(() => { setDesde((d) => (ativo ? d ?? Date.now() : null)) }, [ativo])
  if (!ativo) return null
  const demorou = desde !== null && agora - desde > DEMORA_MS
  const ajuda = 'Open ComfyUI (ComfyUI Desktop, or run_nvidia_gpu.bat in the portable folder) and keep its window open. No GPU? Use Comfy Cloud in Config Models.'
  return (
    <div className="hf-aviso-comfy" role="status" title={ajuda}>
      {daPessoa
        ? <><b>Waiting for your ComfyUI…</b> The shortcut opens it when it can; if no ComfyUI window appears, open it yourself. This page connects by itself.</>
        : demorou
          ? <><b>ComfyUI is taking long to start.</b> Check its window for an error, or close it and open it again. No GPU? Use Comfy Cloud in Config Models.</>
          : <><b>ComfyUI is starting…</b> about a minute or two after the PC starts. Not coming up? Open ComfyUI, or use Comfy Cloud in Config Models.</>}
    </div>
  )
}
