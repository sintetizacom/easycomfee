import { useState } from 'react'
import { api, urlImagem } from '../api'
import { TIPO_GALERIA, eAudio, mensagem, textoDoDetalhe } from './comum'

// Separar uma musica em faixas (voz, bateria, baixo, outros) pelo Plenio, no
// segundo motor. As faixas voltam como cartoes de audio em Recent songs.
export default function BlocoSeparar({ naNuvem }: { naNuvem: boolean }) {
  const [origem, setOrigem] = useState<{ nome: string; url: string; rotulo: string } | null>(null)
  const [formato, setFormato] = useState<'flac' | 'mp3'>('flac')
  const [subindo, setSubindo] = useState(false)
  const [arrastando, setArrastando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const enviarOrigem = async (f: File) => {
    setSubindo(true); setErro(null)
    try { setOrigem({ nome: (await api.enviarAudio(f)).nome, url: URL.createObjectURL(f), rotulo: f.name }) }
    catch (x) { setErro(mensagem(x)) } finally { setSubindo(false) }
  }

  const separar = async () => {
    if (!origem) return
    setErro(null); setEnviando(true)
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelo: 'separar', prompt: origem.rotulo, proporcao: '1:1', modo_separar: 'plenio',
          referencia_separar: origem.nome, formato_separar: formato }) })
      if (!r.ok) throw new Error(textoDoDetalhe((await r.json().catch(() => ({}))).detail, 'Could not split the song.'))
    } catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
  }

  const escolherArquivo = (
    <input type="file" accept="audio/*" className="hf-arquivo" onChange={async (e) => {
      const f = e.target.files?.[0]; if (f) await enviarOrigem(f)
    }} />
  )

  return (
    <section className="hf-separar">
      <div className="hf-separar-linha">
        <div className="hf-origem" data-cheio={!!origem} data-sobre={arrastando || undefined}
          title="WAV, MP3, FLAC or OGG, up to 40 MB. Drop a file or a song from Recent songs here."
          onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
          onDragLeave={() => setArrastando(false)}
          onDrop={async (e) => {
            e.preventDefault(); setArrastando(false)
            // Da galeria do app ou um arquivo do computador.
            const bruto = e.dataTransfer.getData(TIPO_GALERIA)
            if (bruto) {
              try {
                const { nome, subpasta } = JSON.parse(bruto) as { nome: string; subpasta: string }
                if (!eAudio(nome)) { setErro('Drop an audio file here.'); return }
                const blob = await (await fetch(urlImagem({ nome, subpasta }))).blob()
                await enviarOrigem(new File([blob], nome, { type: blob.type || 'audio/flac' }))
              } catch (x) { setErro(mensagem(x)) }
              return
            }
            const f = Array.from(e.dataTransfer.files).find((x) => x.type.startsWith('audio/') || eAudio(x.name))
            if (f) await enviarOrigem(f); else setErro('Drop an audio file here.')
          }}>
          {origem ? (<>
            <span className="hf-origem-nome" title={origem.rotulo}>♪ {origem.rotulo}</span>
            <audio src={origem.url} controls />
            <label className="hf-botao-sec hf-origem-trocar">Replace{escolherArquivo}</label>
            <button type="button" className="hf-origem-tirar" onClick={() => setOrigem(null)}
              title="Remove the song" aria-label="Remove the song">×</button>
          </>) : (
            <label className="hf-origem-vazia">
              <span>{subindo ? 'Uploading…' : '+ Song to split · click or drop a song'}</span>
              {escolherArquivo}
            </label>
          )}
        </div>
      </div>
      <div className="hf-separar-acao">
        <p className="hf-dica">{naNuvem ? 'Runs on your GPU only: switch the engine to Local to use it.'
          : 'Runs on your GPU through Plenio, about 30 s for a 3 min song. The stems appear in Recent songs.'}</p>
        <label className="hf-separar-formato"><small>Format</small>
          <select value={formato} onChange={(e) => setFormato(e.target.value as 'flac' | 'mp3')}>
            <option value="flac">FLAC (lossless)</option><option value="mp3">MP3 320k</option>
          </select></label>
        <button type="button" className="hf-botao" disabled={!origem || enviando || naNuvem} onClick={separar}
          title={naNuvem ? 'Split into stems runs on your GPU: switch to Local.' : undefined}>Split ✦</button>
      </div>
      {erro && <p className="hf-erro" role="alert">{erro}</p>}
    </section>
  )
}
