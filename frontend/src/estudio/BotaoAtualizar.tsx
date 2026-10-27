// "Update" on the top bar: shows only when the GitHub repository has a newer
// version (backend/atualizacao.py). Pressing it closes the server, a window
// downloads and builds the new version, and this page reloads by itself when
// the studio is back.
import { useEffect, useState } from 'react'

type Estado = { disponivel: boolean; novos: number }

export default function BotaoAtualizar() {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [fase, setFase] = useState<'' | 'atualizando' | 'erro'>('')
  const [erro, setErro] = useState('')

  useEffect(() => {
    fetch('/api/atualizacao').then((r) => r.json()).then(setEstado).catch(() => {})
  }, [])

  if (!estado?.disponivel && !fase) return null

  const atualizar = async () => {
    if (!confirm('Update EasyComfee now?\n\nThe studio closes for a few minutes while a window downloads the new version. '
      + 'Your key, gallery and models stay as they are.')) return
    setFase('atualizando')
    const r = await fetch('/api/atualizacao', { method: 'POST' }).catch(() => null)
    if (!r?.ok) {
      setErro(r ? ((await r.json().catch(() => ({}))).detail ?? 'Could not update.') : 'Could not reach the studio.')
      setFase('erro')
      return
    }
    // Espera o servidor cair e voltar com a versao nova; ai recarrega.
    let caiu = false
    const vigia = setInterval(async () => {
      const ok = await fetch('/api/motor', { cache: 'no-store' }).then((x) => x.ok).catch(() => false)
      if (!ok) caiu = true
      else if (caiu) { clearInterval(vigia); location.reload() }
    }, 3000)
  }

  if (fase === 'atualizando') return <span className="hf-atualizar" data-fase="atualizando">Updating… this page reloads by itself</span>
  return (
    <button type="button" className="hf-atualizar" onClick={atualizar} title={fase === 'erro' ? erro : `${estado?.novos ?? ''} new change(s) on GitHub`}>
      {fase === 'erro' ? 'Update failed' : 'Update available'}
    </button>
  )
}
