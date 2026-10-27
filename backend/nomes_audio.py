"""Nomes seguros e legíveis para arquivos de áudio gerados."""
import re
import unicodedata


def nome_audio(partes, padrao):
    limpas = []
    for valor in partes:
        texto = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
        texto = re.sub(r"[^a-zA-Z0-9 _-]", "", texto)
        texto = re.sub(r"\s+", " ", texto).strip(" ._-")[:60].rstrip()
        if texto:
            limpas.append(texto)
    return " - ".join(limpas) or padrao
