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
  // Instalacao so nuvem (comfy_dir vazio): nao ha ComfyUI para abrir.
  const [soNuvem, setSoNuvem] = useState(false)
  const [desde, setDesde] = useState<number | null>(null)
  const [agora, setAgora] = useState(() => Date.now())
  useEffect(() => {
    let vivo = true
    const ler = () => {
      setAgora(Date.now())
      if (document.hidden) return
      fetch('/api/andamento', { cache: 'no-store' }).then((r) => r.json())
        .then((d) => { if (vivo) { setFora(d.motor_respondendo === false); setSoNuvem(d.so_nuvem === true) } }).catch(() => {})
    }
    ler()
    const t = setInterval(ler, 4000)
    return () => { vivo = false; clearInterval(t) }
  }, [])
  const ativo = (fora || subindo) && !naNuvem
  // Conta o tempo desde que a faixa apareceu; zera quando o ComfyUI responde.
  useEffect(() => { setDesde((d) => (ativo ? d ?? Date.now() : null)) }, [ativo])
  if (!ativo) return null
  if (soNuvem) {
    return (
      <div className="hf-aviso-comfy" role="status">
        <b>This install has no local ComfyUI.</b> Connect Comfy Cloud in Config Models to generate.
      </div>
    )
  }
  const demorou = desde !== null && agora - desde > DEMORA_MS
  const ajuda = 'Open ComfyUI (ComfyUI Desktop, or run_nvidia_gpu.bat in the portable folder) and keep its window open. No GPU? Use Comfy Cloud in Config Models.'
  return (
    <div className="hf-aviso-comfy" role="status" title={ajuda}>
      {/* Uma frase so, que diz o que fazer: "esta ligando" fazia quem ja tinha ComfyUI esperar
          por nada (02/11/2026: o amigo so conectou quando abriu o ComfyUI dele). */}
      {demorou
        ? <><b>ComfyUI is taking long.</b> Check its window for an error, or close it and open it again. No GPU? Use Comfy Cloud in Config Models.</>
        : <><b>Waiting for ComfyUI.</b> Already had ComfyUI installed? Open it (ComfyUI Desktop, or run_nvidia_gpu.bat in its folder). EasyComfee connects by itself.</>}
    </div>
  )
}
