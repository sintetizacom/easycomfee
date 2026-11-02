"""Minhas vozes: vozes feitas no Design ou no Clone, guardadas para narrar depois.

Uma voz do Design e a descricao + a seed do audio que o usuario gostou (o mesmo
par devolve o mesmo timbre); uma do Clone e a gravacao de referencia (que fica na
pasta input do motor) + a transcricao. O audio que gerou a voz serve de amostra.
"""
import json
import pathlib
import re
import time
import uuid

ARQUIVO = pathlib.Path(__file__).parent / "minhas_vozes.json"


def listar() -> list[dict]:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(vozes: list[dict]) -> None:
    tmp = ARQUIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(vozes, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQUIVO)


def voz_de(parametros: dict, nome: str, arquivo: str, subpasta: str) -> dict:
    """A voz salva a partir do pedido que gerou o audio. ValueError se nao for Design/Clone."""
    nome = re.sub(r"\s+", " ", nome).strip()[:40]
    if not nome:
        raise ValueError("Give the voice a name.")
    if parametros.get("modelo") != "voz" or parametros.get("modo_voz") not in ("criar", "clonar"):
        raise ValueError("Only voices made with Design a voice or Clone a voice can be saved.")
    base = {"id": uuid.uuid4().hex[:12], "nome": nome, "tipo": parametros["modo_voz"],
            "amostra": {"nome": arquivo, "subpasta": subpasta}, "criada_em": time.time()}
    if parametros["modo_voz"] == "criar":
        if not (parametros.get("instrucao_voz") or "").strip() or parametros.get("seed") is None:
            raise ValueError("This audio has no voice description saved.")
        return base | {"instrucao": parametros["instrucao_voz"], "seed": int(parametros["seed"])}
    ref = parametros.get("referencia_voz") or ""
    if not ref.startswith("refaudio_") or pathlib.PurePosixPath(ref).name != ref or "\\" in ref:
        raise ValueError("This audio has no reference recording saved.")
    return base | {"referencia": ref, "transcricao": parametros.get("transcricao_voz") or ""}


def salvar(voz: dict) -> dict:
    vozes = listar()
    vozes.append(voz)
    _gravar(vozes)
    return voz


def remover(voz_id: str) -> bool:
    vozes = listar()
    resto = [v for v in vozes if v["id"] != voz_id]
    if len(resto) == len(vozes):
        return False
    _gravar(resto)
    return True
