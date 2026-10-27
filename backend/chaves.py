"""Leitura da chave de API dos modelos por nuvem.

DESENHO, e o porque de cada escolha:

1. A chave mora em `chaves.json`, ao lado deste arquivo, e esse nome esta no
   .gitignore. Nunca em codigo, nunca em preset, nunca no grafo do workflow.

2. Ela NAO entra no grafo. Os nos de parceiro do ComfyUI declaram a chave como
   entrada OCULTA (`api_key_comfy_org`); quem a fornece e o `execution.py` do
   motor, lendo do campo `extra_data` da requisicao — irmao do grafo, nao parte
   dele. Por isso ela nao aparece no /history nem nos logs do motor, que marca
   esse campo como sensivel (SENSITIVE_EXTRA_DATA_KEYS, execution.py:157).

3. Le-se do disco a cada chamada, sem cache. E uma leitura de ~200 bytes, e em
   troca voce pode trocar a chave com o site no ar, sem reiniciar nada.

4. Nada aqui imprime a chave. As funcoes de diagnostico devolvem so o tamanho e
   os quatro ultimos caracteres, que bastam para confirmar QUAL chave esta
   valendo sem revelar a chave.
"""

import json
import pathlib

import config

ARQUIVO = pathlib.Path(__file__).parent / "chaves.json"

MODELO_DO_ARQUIVO = {
    "comfy_org": "cole-aqui-a-sua-chave",
}


def _lido() -> dict:
    """Conteudo do arquivo, ou vazio se ele nao existe / esta quebrado.

    Um JSON malformado nao pode derrubar o site inteiro: quem nao usa modelo
    por nuvem nem deveria perceber que este arquivo existe.
    """
    if not ARQUIVO.exists():
        return {}
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return dados if isinstance(dados, dict) else {}


def chave() -> str | None:
    """A chave do ComfyUI, ou None se nao houver uma utilizavel.

    O texto de exemplo que vem no arquivo modelo conta como ausencia — senao o
    primeiro erro do usuario seria enviar a palavra 'cole-aqui' para a nuvem e
    receber um 401 sem explicacao.
    """
    bruto = _lido().get("comfy_org")
    if not isinstance(bruto, str):
        return None
    limpo = bruto.strip()
    if not limpo or limpo == MODELO_DO_ARQUIVO["comfy_org"]:
        return None
    return limpo


def extra_data() -> dict:
    """O campo que acompanha o grafo no POST /prompt. Vazio se nao ha chave."""
    k = chave()
    return {"api_key_comfy_org": k} if k else {}


def situacao() -> dict:
    """Diagnostico para a interface. Nunca devolve a chave."""
    k = chave()
    if k is None:
        return {"tem_chave": False, "arquivo": str(ARQUIVO),
                "existe_arquivo": ARQUIVO.exists()}
    return {"tem_chave": True, "arquivo": str(ARQUIVO), "existe_arquivo": True,
            "tamanho": len(k), "final": k[-4:]}


def salvar_chave(k: str) -> None:
    """Grava a chave que o usuario digitou na tela. Vazia apaga. Mantem as
    outras entradas do arquivo (o token do Hugging Face mora nele tambem)."""
    dados = _lido()
    limpo = (k or "").strip()
    if limpo:
        dados["comfy_org"] = limpo
    else:
        dados.pop("comfy_org", None)
    ARQUIVO.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def criar_modelo() -> pathlib.Path:
    """Escreve o arquivo de exemplo, se ainda nao existir. Nunca sobrescreve."""
    if not ARQUIVO.exists():
        ARQUIVO.write_text(
            json.dumps(MODELO_DO_ARQUIVO, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    return ARQUIVO


# Falhas dos nos de nuvem, traduzidas. O motor devolve a mensagem do provedor
# junto de um traceback de 40 linhas; sem isto o usuario ve o traceback.
#
# A ordem importa: "insufficient" antes de "credit", porque a mensagem de saldo
# costuma conter as duas palavras e a primeira e a especifica.
_TRADUCOES = [
    ("unauthorized", "O ComfyUI não reconheceu a chave de API. Confira o "
                     "arquivo chaves.json, pois a chave pode estar ausente, "
                     "incompleta ou já revogada."),
    ("please login", "O ComfyUI não reconheceu a chave de API. Confira o "
                     "arquivo chaves.json, pois a chave pode estar ausente, "
                     "incompleta ou já revogada."),
    ("insufficient", "Créditos insuficientes na conta do ComfyUI. Comprar "
                     "mais créditos libera a geração; nada foi cobrado."),
    ("quota", "A cota do provedor foi atingida. Costuma liberar sozinha; "
              "tentar de novo mais tarde resolve."),
    ("rate limit", "Pedidos demais em pouco tempo. Esperar um instante e "
                   "repetir resolve."),
    ("safety", "O provedor recusou o pedido pelo filtro de conteúdo dele. "
               "Reescrever o texto costuma bastar; nada foi cobrado."),
    ("prohibited", "O provedor recusou o pedido pelo filtro de conteúdo dele. "
                   "Reescrever o texto costuma bastar; nada foi cobrado."),
    ("timeout", "O provedor demorou demais para responder. Tentar de novo "
                "costuma resolver."),
]


def traduzir_erro(bruto: str) -> str | None:
    """Explicacao em portugues, ou None se o erro nao for de nuvem.

    Devolver None e importante: quem chama so substitui a mensagem quando ha
    uma traducao, e um erro desconhecido chega inteiro ao usuario em vez de
    virar um 'algo deu errado' que esconde a causa.
    """
    baixo = (bruto or "").lower()
    for marca, texto in _TRADUCOES:
        if marca in baixo:
            return texto
    return None


# ---------------------------------------------------------------- saldo
BASE_API = "https://api.comfy.org"

# MEDIDO em 18/09/2026, duas vezes, contra precos de tabela diferentes:
#
#   Nano Banana 2  tabela 0.0835 USD -> debito de  8,0645  (96,6 por USD)
#   Nano Banana Pro tabela 0.1608 USD -> debito de 16,4251 (102,2 por USD)
#
# A unidade e o CENTAVO, apesar de o campo se chamar "micros". A variacao em
# torno de 100 vem de o preco do no ser declarado aproximado (`approximate`
# no price_badge): a cobranca real e por token, e a tabela e estimativa.
#
# Por isso o saldo na tela vale como saldo, e o custo antes do botao vale como
# ordem de grandeza. Quem cobra e o extrato.
CENTAVOS_POR_DOLAR = 100.0

# O saldo muda pouco e a chamada sai da maquina. Sem isto, cada abertura de
# painel viraria uma requisicao para fora.
_CACHE: dict = {"quando": 0.0, "valor": None}
VALIDADE_DO_CACHE = 60.0


async def saldo(forcar: bool = False) -> dict:
    """Creditos restantes, em dolares. Nunca levanta excecao.

    Devolve {"ok": False, "motivo": ...} quando nao da para saber — a
    interface precisa distinguir "saldo zero" de "nao consegui perguntar".
    """
    import time

    import httpx

    k = chave()
    if not k:
        return {"ok": False, "motivo": "sem chave"}

    agora = time.time()
    if not forcar and _CACHE["valor"] and agora - _CACHE["quando"] < VALIDADE_DO_CACHE:
        return _CACHE["valor"]

    try:
        async with httpx.AsyncClient(timeout=15, verify=config.ssl_sistema()) as c:
            r = await c.get(f"{BASE_API}/customers/balance",
                            headers={"Authorization": f"Bearer {k}"})
        if r.status_code == 401:
            return {"ok": False, "motivo": "chave recusada"}
        if r.status_code != 200:
            return {"ok": False, "motivo": f"resposta {r.status_code}"}
        d = r.json()
    except Exception as e:
        return {"ok": False, "motivo": f"sem resposta ({type(e).__name__})"}

    bruto = d.get("effective_balance_micros")
    if not isinstance(bruto, (int, float)):
        return {"ok": False, "motivo": "resposta em formato inesperado"}

    valor = {"ok": True,
             # 4 casas, e nao 2: a diferenca entre duas leituras e o custo de
             # uma imagem, e arredondar a centavo jogaria fora o que se quer
             # medir. Quem exibe e que formata.
             "usd": round(bruto / CENTAVOS_POR_DOLAR, 4),
             # Cobrancas ja feitas que ainda nao baixaram do saldo.
             "pendente_usd": round((d.get("pending_charges_micros") or 0)
                                   / CENTAVOS_POR_DOLAR, 2)}
    _CACHE.update({"quando": agora, "valor": valor})
    return valor


# ---- Token do Hugging Face (instalador de modelos) ----------------------
# Os repositorios da Lightricks exigem login e o aceite da licenca uma vez.
# O token mora no mesmo chaves.json, e vale a mesma regra: nunca e impresso.

def hf_token() -> str | None:
    bruto = _lido().get("huggingface")
    return bruto.strip() if isinstance(bruto, str) and bruto.strip() else None


def salvar_hf_token(token: str) -> None:
    dados = _lido()
    if token.strip():
        dados["huggingface"] = token.strip()
    else:
        dados.pop("huggingface", None)
    ARQUIVO.write_text(json.dumps(dados, indent=2), encoding="utf-8")


def situacao_hf() -> dict:
    t = hf_token()
    return {"configurado": bool(t), "final": t[-4:] if t else None}
