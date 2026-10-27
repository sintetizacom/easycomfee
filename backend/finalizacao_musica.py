"""Finalização conservadora em CPU. Não confunde batidas com compassos certos."""
import io
import numpy as np
import soundfile as sf


def analisar(audio, sr, alvo, margem):
    # Energia por canal, evitando cancelamento de fase entre canais estéreo.
    hop = max(1, round(sr * .02))
    n = len(audio) // hop
    if n < 100 or not np.isfinite(audio).all():
        raise ValueError("Áudio inválido ou muito curto para analisar")
    blocos = audio[:n*hop].reshape(n, hop, -1)
    energia = np.sqrt(np.mean(blocos.astype(np.float64)**2, axis=(1,2)))
    referencia = float(np.quantile(energia, .8))
    if referencia < 1e-5:
        return None, {"motivo": "Áudio sem sinal suficiente para analisar."}
    dt = hop / sr
    onset = np.maximum(np.diff(energia, prepend=energia[0]), 0)
    # Evidência de periodicidade do áudio; BPM pedido não define os cortes.
    central = onset - onset.mean()
    ac = np.correlate(central[-3000:], central[-3000:], mode='full')[min(3000,len(central))-1:]
    lags = np.arange(max(1, round(.333/dt)), min(len(ac), round(1.0/dt))+1)
    bpm = None; ritmo_confiavel = False
    if len(lags) and ac[0] > 1e-10:
        lag = int(lags[np.argmax(ac[lags])]); confianca = float(ac[lag]/ac[0])
        ritmo_confiavel = confianca >= .35
        if ritmo_confiavel: bpm = round(60/(lag*dt),1)
    # Exigir silêncio real sustentado: uma batida estimada sozinha não autoriza corte.
    quieto = energia < min(referencia * .04, .002)
    pad = np.r_[False, quieto, False].astype(int)
    starts = np.where(np.diff(pad)==1)[0]; ends=np.where(np.diff(pad)==-1)[0]
    candidatos=[]
    limite_min=max(5,alvo-margem); limite_max=min(len(audio)/sr,alvo+margem)
    for start,end in zip(starts,ends):
        if (end-start)*dt < .6: continue
        # Mantém 250 ms da pausa após a cauda, e deixa margem antes de nova entrada.
        corte=(start*dt)+.25
        if not limite_min <= corte <= limite_max or start*dt < 1: continue
        anteriores=energia[max(0,start-round(1/dt)):start]
        if len(anteriores)==0 or anteriores.max() < referencia*.15: continue
        # Uma pausa intermediária não é um encerramento. Se a música volta
        # depois, preservamos o arquivo: não inferimos compassos pelo BPM.
        if end < n and energia[end:].max() > referencia*.1: continue
        # Pausas rítmicas dentro de uma sequência de batidas regulares são inseguras.
        proximos=onset[end:min(n,end+round(2/dt))]
        penalidade = .5 if ritmo_confiavel and len(proximos) and proximos.max() > referencia*.15 else 0
        candidatos.append((abs(corte-alvo)+penalidade,corte))
    report={"bpm_estimado":bpm,"ritmo_confiavel":ritmo_confiavel}
    if not candidatos:
        return None, report | {"motivo":"Nenhuma pausa sustentada confiável perto da duração solicitada. Original preservado."}
    return min(candidatos)[1],report | {"motivo":"Pausa sustentada após a cauda dos instrumentos. Não há garantia de fechamento harmônico."}


def finalizar(dados, alvo, margem=10, modo='natural', vocal=False):
    audio,sr=sf.read(io.BytesIO(dados),dtype='float32',always_2d=True)
    if not np.isfinite(audio).all() or len(audio)==0:raise ValueError('Áudio inválido')
    dur=len(audio)/sr
    rel={"duracao_original":round(dur,3),"duracao_final":round(dur,3),"modo":modo,"alterado":False}
    if modo=='original':return None,rel | {"motivo":"Original preservado por escolha."}
    if vocal and modo=='natural':
        return None,rel | {"motivo":"Com letra: corte automático desativado para proteger frases cantadas."}
    if modo=='fade':
        # Escolha explícita. Não promete fechar compasso, melodia ou palavra.
        corte=min(dur,alvo)
        fim=round(corte*sr);resultado=audio[:fim].copy()
        fade=min(fim,round(2*sr));resultado[-fade:] *= np.linspace(1,0,fade,dtype=np.float32)[:,None]
        motivo={"motivo":"Fade-out de até 2 segundos aplicado por escolha. Pode interromper uma frase musical."}
    else:
        corte,motivo=analisar(audio,sr,alvo,margem)
        if corte is None or corte >= dur-.03:return None,rel | motivo
        resultado=audio[:round(corte*sr)].copy()
        # Só suaviza o silêncio na extremidade: não esconde um corte em música ativa.
        fade=min(len(resultado),round(.02*sr));resultado[-fade:] *= np.linspace(1,0,fade,dtype=np.float32)[:,None]
    output=io.BytesIO();sf.write(output,resultado,sr,format='FLAC',subtype='PCM_16')
    return output.getvalue(),rel | motivo | {"duracao_final":round(len(resultado)/sr,3),"alterado":True}
