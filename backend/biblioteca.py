"""Galeria persistente: guarda cada imagem gerada com os dados para refazer."""

import json
import pathlib
import sqlite3
import time
from contextlib import contextmanager

BANCO = pathlib.Path(__file__).parent / "galeria.db"

# Colunas acrescentadas depois da primeira versao do banco. Sao aplicadas em
# bancos antigos sem perder nada do que ja estava gravado.
COLUNAS_EXTRAS = {
    "largura": "INTEGER NOT NULL DEFAULT 0",
    "altura": "INTEGER NOT NULL DEFAULT 0",
    "duracao": "REAL NOT NULL DEFAULT 0",
    "bytes": "INTEGER NOT NULL DEFAULT 0",
    # Imagens de teste/diagnostico. Ficam no banco, mas fora da vista por
    # padrao: sao uteis para comparar depois e nao devem competir com o
    # trabalho de verdade na galeria.
    "teste": "INTEGER NOT NULL DEFAULT 0",
    # Rotulo legivel, quando o nome do modo nao basta. A coluna `modelo` guarda
    # o ID do modo e e o que o botao "Reusar parametros" precisa; misturar
    # texto humano ali quebrava o botao.
    "rotulo": "TEXT",
    # Dolares que a imagem custou de verdade, medidos pela diferenca de saldo
    # antes e depois. Zero nos modelos locais, que nao custam nada. Fica em
    # coluna propria, e nao dentro de `parametros`: parametro e o que se pede,
    # custo e o que aconteceu — e so a coluna permite somar por periodo.
    "custo_usd": "REAL NOT NULL DEFAULT 0",
    # Segundos de video. Zero nas imagens — e o que distingue um do outro na
    # galeria sem ter que olhar a extensao do arquivo.
    "duracao_video": "REAL NOT NULL DEFAULT 0",
    "fps": "REAL NOT NULL DEFAULT 0",
}


@contextmanager
def _conectar():
    con = sqlite3.connect(BANCO)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def criar_tabelas():
    with _conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS imagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criada_em REAL NOT NULL,
                modelo TEXT NOT NULL,
                prompt TEXT NOT NULL,
                prompt_final TEXT NOT NULL,
                arquivo TEXT NOT NULL,
                subpasta TEXT NOT NULL DEFAULT '',
                parametros TEXT NOT NULL,
                caption TEXT
            )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data ON imagens(criada_em DESC)")
        con.execute("""CREATE TABLE IF NOT EXISTS tarefas (
            id TEXT PRIMARY KEY, criada_em REAL NOT NULL,
            estado TEXT NOT NULL, registro TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_data ON tarefas(criada_em DESC)")

        existentes = {l["name"] for l in con.execute("PRAGMA table_info(imagens)")}
        for nome, tipo in COLUNAS_EXTRAS.items():
            if nome not in existentes:
                con.execute(f"ALTER TABLE imagens ADD COLUMN {nome} {tipo}")

        # Repetir uma geracao identica (mesmo modelo, prompt, seed e parametros)
        # faz o motor devolver o resultado em cache, com o MESMO nome de
        # arquivo. Sem isto a galeria ganhava duas linhas para a mesma imagem.
        con.execute("""
            DELETE FROM imagens WHERE id NOT IN (
                SELECT MIN(id) FROM imagens GROUP BY arquivo, subpasta
            )""")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_arquivo"
                    " ON imagens(arquivo, subpasta)")


def marcar_testes(prefixos=("Teste", "LoRA v2", "Chave")) -> int:
    """Marca como teste as linhas que vieram das minhas comparacoes.

    E uma correcao de uma vez so: dali em diante quem grava passa `teste=1`.
    """
    with _conectar() as con:
        alvo = " OR ".join("modelo LIKE ?" for _ in prefixos)
        cur = con.execute(f"UPDATE imagens SET teste = 1 WHERE {alvo}",
                          [p + "%" for p in prefixos])
        return cur.rowcount


def nome_dado(dados: dict) -> str:
    """O nome que a pessoa deu ao audio (projeto/voz e titulo), ou "".

    Os campos ja entravam no nome do arquivo, mas o cartao da galeria mostra
    o rotulo — e o rotulo de musica era sempre "Musica · versao".
    """
    pares = (("projeto_musica", "titulo_musica"), ("nome_voz", "titulo_audio_voz"))
    for a, b in pares:
        partes = [str(dados.get(c) or "").strip() for c in (a, b)]
        if any(partes):
            return " – ".join(x for x in partes if x)
    return ""


def registrar(tarefa, tamanhos=None, teste=False, rotulo=None):
    """Grava uma linha por imagem do lote, com tudo que permite reproduzir.

    `tamanhos` mapeia nome do arquivo -> bytes; vem do app, que consulta o
    motor sem baixar a imagem inteira.
    """
    p = tarefa.pedido
    tamanhos = tamanhos or {}
    # Guarda o pedido INTEIRO, menos o que nao faz sentido repetir. Antes so
    # nove campos de geracao eram salvos, e por isso "Reusar parametros" nao
    # tinha como devolver metodo de ampliacao, vista de angulo, posicao da luz
    # ou os controles do rosto: eles nunca chegaram ao banco.
    fora = {"referencias", "caption", "prompt", "teste", "rotulo_teste"}
    dados = p.model_dump() if hasattr(p, "model_dump") else dict(p.__dict__)
    guardado = {k: v for k, v in dados.items() if k not in fora}
    # `referencias` fica fora do que se REUSA de proposito: sao envios
    # temporarios, e devolver esses caminhos ao formulario apontaria para
    # arquivos que podem ja nao existir. Mas nao guardar nada apagava a
    # informacao mais util dos modos de referencia — QUAIS fotos geraram
    # aquilo. Vai numa chave propria, que o "Reusar parametros" nao le: ele
    # escolhe campo a campo, entao chave nova nao volta ao formulario.
    if dados.get("referencias"):
        guardado["referencias_usadas"] = list(dados["referencias"])
    parametros = json.dumps(guardado, ensure_ascii=False)
    # O rotulo de teste continua tendo prioridade: identifica a rodada.
    rotulo = rotulo or nome_dado(dados) or None
    caption = json.dumps(tarefa.caption, ensure_ascii=False) if tarefa.caption else None
    agora = time.time()
    with _conectar() as con:
        for bruto in tarefa.imagens:
            im = json.loads(bruto)
            # OR IGNORE: se o motor devolveu um resultado em cache, o arquivo
            # ja esta na galeria e nao deve entrar de novo.
            con.execute(
                "INSERT OR IGNORE INTO imagens (criada_em, modelo, prompt, prompt_final,"
                " arquivo, subpasta, parametros, caption, largura, altura,"
                " duracao, bytes, teste, rotulo, custo_usd, duracao_video, fps)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (agora, p.modelo, p.prompt, tarefa.prompt_final,
                 im["nome"], im.get("subpasta", ""),
                 json.dumps(guardado | {"finalizacao_musica": im["musica"]}, ensure_ascii=False) if "musica" in im else parametros, caption,
                 tarefa.largura, tarefa.altura, tarefa.duracao,
                 tamanhos.get(im["nome"], 0), 1 if teste else 0,
                 f"{rotulo or 'Música'} · {im['musica']['versao']}" if "musica" in im else rotulo,
                 getattr(tarefa, "custo_usd", 0.0) or 0.0,
                 getattr(tarefa, "duracao_video", 0.0) or 0.0,
                 getattr(tarefa, "fps", 0.0) or 0.0))


def listar(limite=60, antes=None, com_testes=False):
    consulta = "SELECT * FROM imagens"
    filtros, args = [], []
    if antes:
        filtros.append("criada_em < ?")
        args.append(antes)
    if not com_testes:
        filtros.append("teste = 0")
    if filtros:
        consulta += " WHERE " + " AND ".join(filtros)
    consulta += " ORDER BY criada_em DESC LIMIT ?"
    args.append(limite)
    with _conectar() as con:
        linhas = con.execute(consulta, args).fetchall()
    return [{**dict(l),
             "parametros": json.loads(l["parametros"]),
             "caption": json.loads(l["caption"]) if l["caption"] else None}
            for l in linhas]


def obter(item_id: int):
    """Um item da galeria pelo id, ou None."""
    with _conectar() as con:
        l = con.execute("SELECT * FROM imagens WHERE id = ?", (item_id,)).fetchone()
    if l is None:
        return None
    return {**dict(l), "parametros": json.loads(l["parametros"])}


def por_arquivo(subpasta: str, arquivo: str):
    """O registro de um arquivo gerado (o visualizador abre pelo arquivo, nao pelo id)."""
    with _conectar() as con:
        l = con.execute("SELECT * FROM imagens WHERE arquivo = ? AND subpasta = ? ORDER BY id DESC LIMIT 1",
                        (arquivo, subpasta)).fetchone()
    if l is None:
        return None
    return {**dict(l), "parametros": json.loads(l["parametros"]),
            "caption": json.loads(l["caption"]) if l["caption"] else None}


def apagar(item_id: int):
    """Remove so o registro. O arquivo original fica na pasta de saida."""
    with _conectar() as con:
        con.execute("DELETE FROM imagens WHERE id = ?", (item_id,))


def tempos_medidos(minimo=2, ultimas=12) -> dict:
    """Mediana do tempo real por modo, das execucoes mais recentes.

    Substitui a estimativa escrita a mao, que era medida com o modelo ja
    carregado e por isso errava feio: o modo "trocar" estimava 104 s e levou
    470 s quando veio depois do Ideogram. A mediana do uso real ja embute o
    que acontece nesta maquina.

    `minimo` evita anunciar um numero tirado de uma execucao so.
    """
    with _conectar() as con:
        linhas = con.execute(
            "SELECT modelo, duracao FROM imagens"
            " WHERE duracao > 0 ORDER BY criada_em DESC").fetchall()
    por_modo = {}
    for l in linhas:
        v = por_modo.setdefault(l["modelo"], [])
        if len(v) < ultimas:
            v.append(l["duracao"])
    saida = {}
    for modo, vs in por_modo.items():
        if len(vs) < minimo:
            continue
        vs = sorted(vs)
        meio = len(vs) // 2
        mediana = vs[meio] if len(vs) % 2 else (vs[meio - 1] + vs[meio]) / 2
        saida[modo] = {"mediana": round(mediana), "amostras": len(vs),
                       "minimo": round(min(vs)), "maximo": round(max(vs))}
    return saida


def gasto_total() -> dict:
    """Quanto ja foi gasto em modelos por nuvem, e em quantas imagens.

    Sai do banco, e nao de um contador em memoria: assim sobrevive a reinicio
    e conta o que foi feito em sessoes anteriores.
    """
    with _conectar() as con:
        l = con.execute("SELECT COUNT(*) n, COALESCE(SUM(custo_usd), 0) s"
                        " FROM imagens WHERE custo_usd > 0").fetchone()
    return {"imagens": l["n"], "usd": round(l["s"], 4)}


def anotar_custo(imagens, custo_usd: float) -> int:
    """Grava o custo medido nas linhas ja inseridas.

    Existe porque o debito so aparece no saldo alguns segundos depois de a
    imagem ficar pronta. Esperar por ele antes de gravar atrasaria a imagem na
    tela; entao a linha nasce com zero e recebe o valor quando ele existe.
    """
    if not custo_usd:
        return 0
    n = 0
    # Uma cobranca pertence ao envio inteiro. Se o grafo devolve mais de uma
    # imagem, gravar o valor inteiro em cada linha inflaria gasto_total().
    unidades = round(custo_usd * 10000)
    base, sobra = divmod(unidades, len(imagens)) if imagens else (0, 0)
    with _conectar() as con:
        for indice, bruto in enumerate(imagens):
            im = json.loads(bruto)
            cur = con.execute(
                "UPDATE imagens SET custo_usd = ? WHERE arquivo = ? AND subpasta = ?",
                ((base + (indice < sobra)) / 10000,
                 im["nome"], im.get("subpasta", "")))
            n += cur.rowcount
    return n


def salvar_tarefa(registro: dict):
    with _conectar() as con:
        con.execute("""INSERT INTO tarefas(id, criada_em, estado, registro)
            VALUES(?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
            estado=excluded.estado, registro=excluded.registro""",
            (registro["id"], registro["criada_em"], registro["estado"],
             json.dumps(registro, ensure_ascii=False)))


def apagar_tarefa(tarefa_id: str):
    with _conectar() as con:
        con.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))


def carregar_tarefas(limite=100) -> list[dict]:
    # Mantem todas as pendentes mesmo se houver mais que `limite` concluidas.
    with _conectar() as con:
        linhas = con.execute("""SELECT registro FROM tarefas
            WHERE estado NOT IN ('pronto', 'erro') OR id IN
            (SELECT id FROM tarefas ORDER BY criada_em DESC LIMIT ?)
            ORDER BY criada_em DESC""", (limite,)).fetchall()
    return [json.loads(l["registro"]) for l in linhas]


def podar_tarefas(limite=500):
    with _conectar() as con:
        con.execute("""DELETE FROM tarefas WHERE estado IN ('pronto', 'erro')
            AND id NOT IN (SELECT id FROM tarefas ORDER BY criada_em DESC LIMIT ?)""",
            (limite,))
