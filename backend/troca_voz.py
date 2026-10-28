"""Trocar a voz de uma musica pelo timbre de um modelo treinado (RVC, via Applio).

Roda fora do ComfyUI, no ambiente proprio do Applio, chamado como processo
(como o separador). Caminho da troca: o separador tira a voz da musica, o
Applio converte a voz mantendo a melodia, e o ffmpeg junta de novo com o
instrumental, com o volume da voz convertida igualado ao da voz original.

Teste de 22/10/2026 (voz sintetica da "Cidade Natal"): treino de 65 s com
20 epocas em 231 s; conversao de 23 s em 11 s; a nota cantada coincide com a
da entrada em 84% dos quadros (controle, a mesma voz deslocada 2 s: 6%). A
voz convertida sai uns 8 dB mais baixa — por isso o ajuste de volume.

Uso combinado com o usuario: so a propria voz, a de quem autorizou, ou uma
voz sintetica original. Nunca a de um cantor real sem consentimento.
"""
import config
import asyncio
import json
import pathlib
import re
import shutil

import separacao

APPLIO = config.APPLIO_DIR
PYTHON = APPLIO / "env" / "Scripts" / "python.exe"
CORE = APPLIO / "core.py"
MODELOS = APPLIO / "logs"
DADOS = APPLIO / "datasets"
TAXA = 40000
TEMPO_CONVERSAO = 1800
TEMPO_TREINO = 6 * 3600
# O modelo final do Applio se chama "<nome>_<epocas>e_<passos>s.pth".
_FINAL = re.compile(r"^(?P<nome>.+)_(?P<epocas>\d+)e_\d+s\.pth$")


def _seguro(texto, padrao="voz"):
    return re.sub(r'[<>:"/\\|?*\s]+', "_", texto).strip("_.") or padrao


def vozes() -> list[dict]:
    """Os modelos treinados: o .pth final mais recente e o indice de cada um."""
    lista = []
    if not MODELOS.is_dir():
        return lista
    for pasta in sorted(MODELOS.iterdir()):
        if not pasta.is_dir() or pasta.name.startswith(("teste_", "mute")):
            continue
        finais = [(int(m["epocas"]), p) for p in pasta.glob("*.pth")
                  if (m := _FINAL.match(p.name)) and m["nome"] == pasta.name]
        indices = sorted(pasta.glob("*.index"))
        if finais and indices:
            epocas, pth = max(finais)
            lista.append({"id": pasta.name, "epocas": epocas,
                          "pth": str(pth), "indice": str(indices[0])})
    return lista


def disponivel() -> dict:
    if not PYTHON.exists():
        return {"disponivel": False, "motivo": "O Applio não está instalado.", "vozes": []}
    if not separacao.PYTHON.exists():
        return {"disponivel": False, "motivo": "O separador de faixas não está instalado.", "vozes": []}
    return {"disponivel": True, "motivo": "",
            "vozes": [{"id": v["id"], "epocas": v["epocas"]} for v in vozes()]}


async def _rodar(args, tempo, ao_linha=None):
    proc = await asyncio.create_subprocess_exec(
        str(PYTHON), str(CORE), *args, cwd=str(APPLIO),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    ultimas = []

    async def ler():
        # O tqdm escreve com \r; quebrar nos dois para ver cada linha.
        resto = b""
        while chunk := await proc.stdout.read(4096):
            partes = re.split(rb"[\r\n]", resto + chunk)
            resto = partes.pop()
            for p in partes:
                linha = p.decode("utf-8", "replace").strip()
                if linha:
                    ultimas[:] = (ultimas + [linha])[-20:]
                    if ao_linha:
                        await ao_linha(linha)
    try:
        await asyncio.wait_for(asyncio.gather(ler(), proc.wait()), tempo)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("O Applio passou do tempo máximo e foi interrompido.")
    if proc.returncode != 0:
        erro = next((l for l in reversed(ultimas) if "Error" in l or "error" in l), ultimas[-1] if ultimas else "sem detalhe")
        raise RuntimeError(f"O Applio falhou: {erro[-300:]}")


async def _ffmpeg(*args):
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, erro = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("O ffmpeg falhou: " + erro.decode("utf-8", "replace").strip()[-200:])


async def _volume_medio(arquivo: pathlib.Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-i", str(arquivo), "-af", "volumedetect", "-f", "null", "-",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, saida = await proc.communicate()
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", saida.decode("utf-8", "replace"))
    return float(m.group(1)) if m else 0.0


async def trocar(entrada: pathlib.Path, voz: str, tom: int, destino: pathlib.Path,
                 base: str, formato: str = "flac", ao_etapa=None):
    """Devolve [(arquivo, versao)]: a musica com a voz trocada e a voz sozinha."""
    modelo = next((v for v in vozes() if v["id"] == voz), None)
    if modelo is None:
        raise RuntimeError("A voz escolhida não está treinada.")
    destino.mkdir(parents=True, exist_ok=True)
    trabalho = destino / "_trabalho_voz"
    if trabalho.exists():
        shutil.rmtree(trabalho)
    trabalho.mkdir()
    try:
        if ao_etapa:
            await ao_etapa("separando a voz da música")
        faixas = await separacao.separar(entrada, "voz", trabalho, "faixa")
        caminho = {faixa: trabalho / nome for nome, faixa in faixas}
        if "Voz" not in caminho or "Instrumental" not in caminho:
            raise RuntimeError("O separador não devolveu voz e instrumental.")

        if ao_etapa:
            await ao_etapa(f"convertendo para a voz “{voz}”")
        convertida = trabalho / "convertida.wav"
        await _rodar(["infer", "--input-path", str(caminho["Voz"]), "--output-path", str(convertida),
                      "--pth-path", modelo["pth"], "--index-path", modelo["indice"],
                      "--pitch", str(tom), "--f0-method", "rmvpe"], TEMPO_CONVERSAO)
        if not convertida.exists():
            raise RuntimeError("O Applio não gravou a voz convertida.")

        if ao_etapa:
            await ao_etapa("juntando a voz nova com o instrumental")
        ganho = await _volume_medio(caminho["Voz"]) - await _volume_medio(convertida)
        codec = ["-c:a", "libmp3lame", "-b:a", "320k"] if formato == "mp3" else ["-c:a", "flac"]
        seguro = re.sub(r'[<>:"/\\|?*]+', "_", base).strip() or "musica"
        nomes = []
        for versao in ("Voz trocada", "Voz convertida"):
            n = 1
            while (destino / f"{seguro} - {versao} ({voz})_{n:03d}.{formato}").exists():
                n += 1
            nomes.append(destino / f"{seguro} - {versao} ({voz})_{n:03d}.{formato}")
        # amix com normalize=0 soma as duas faixas sem baixar cada uma pela metade.
        await _ffmpeg("-i", str(caminho["Instrumental"]), "-i", str(convertida), "-filter_complex",
                      f"[1:a]volume={ganho:.2f}dB,aresample=44100[v];[0:a]aresample=44100[i];"
                      "[i][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.97[s]",
                      "-map", "[s]", *codec, str(nomes[0]))
        await _ffmpeg("-i", str(convertida), "-af", f"volume={ganho:.2f}dB", *codec, str(nomes[1]))
        return [(nomes[0].name, "Voz trocada"), (nomes[1].name, "Voz convertida")]
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)


async def treinar(arquivos: list[pathlib.Path], nome: str, epocas: int, separar_voz: bool,
                  ao_etapa=None, ao_progresso=None) -> dict:
    """Treina um modelo de voz a partir de gravacoes da pessoa (10-30 min)."""
    nome = _seguro(nome)
    if (MODELOS / nome).exists():
        raise RuntimeError(f"Já existe uma voz chamada “{nome}”. Escolha outro nome.")
    pasta = DADOS / nome
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    try:
        for i, a in enumerate(arquivos):
            if separar_voz:
                if ao_etapa:
                    await ao_etapa(f"tirando o instrumental da gravação {i + 1} de {len(arquivos)}")
                faixas = await separacao.separar(a, "voz", pasta / "_sep", f"g{i}")
                voz = next(pasta / "_sep" / n for n, f in faixas if f == "Voz")
                await _ffmpeg("-i", str(voz), "-ac", "1", str(pasta / f"gravacao_{i:02d}.wav"))
                shutil.rmtree(pasta / "_sep", ignore_errors=True)
            else:
                await _ffmpeg("-i", str(a), "-ac", "1", str(pasta / f"gravacao_{i:02d}.wav"))

        if ao_etapa:
            await ao_etapa("preparando as gravações")
        await _rodar(["preprocess", "--model-name", nome, "--dataset-path", str(pasta),
                      "--sample-rate", str(TAXA)], TEMPO_TREINO)
        if ao_etapa:
            await ao_etapa("extraindo afinação e timbre")
        await _rodar(["extract", "--model-name", nome, "--sample-rate", str(TAXA)], TEMPO_TREINO)
        if ao_etapa:
            await ao_etapa(f"treinando (0 de {epocas} épocas)")

        async def linha(texto):
            m = re.search(r"\| epoch=(\d+) \|", texto)
            if m:
                feitas = int(m.group(1))
                if ao_etapa:
                    await ao_etapa(f"treinando ({feitas} de {epocas} épocas)")
                if ao_progresso:
                    await ao_progresso(min(feitas / epocas, 0.99))
        # Guarda a cada 50 epocas so o ultimo ponto (save-only-latest), para
        # uma queda no meio nao perder o treino inteiro sem encher o disco.
        await _rodar(["train", "--model-name", nome, "--sample-rate", str(TAXA),
                      "--total-epoch", str(epocas), "--batch-size", "8",
                      "--save-every-epoch", str(min(50, epocas)), "--save-only-latest"],
                     TEMPO_TREINO, linha)
    except BaseException:
        # Uma voz pela metade nao pode aparecer na lista como pronta.
        shutil.rmtree(MODELOS / nome, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    pronta = next((v for v in vozes() if v["id"] == nome), None)
    if pronta is None:
        raise RuntimeError("O treino terminou, mas o modelo final não apareceu.")
    return {"id": nome, "epocas": pronta["epocas"]}


def apagar(nome: str) -> pathlib.Path:
    """Tira a voz da lista movendo a pasta para a quarentena (nao apaga)."""
    # So uma voz que esta na lista: com nome "..", MODELOS / ".." e uma pasta e o
    # .parent dele parecia ser MODELOS, e a pasta de modelos inteira ia junto.
    if nome not in {v["id"] for v in vozes()}:
        raise RuntimeError("Voice not found.")
    pasta = MODELOS / nome
    if not pasta.is_dir() or pasta.resolve().parent != MODELOS.resolve():
        raise RuntimeError("Voice not found.")
    quarentena = APPLIO / "_removidas"
    quarentena.mkdir(exist_ok=True)
    alvo = quarentena / nome
    n = 1
    while alvo.exists():
        n += 1
        alvo = quarentena / f"{nome}_{n}"
    pasta.rename(alvo)
    return alvo
