# coding: utf-8
"""Roda DENTRO do ambiente do separador (ComfyUI-Installs\\separador), nao no
do app: o audio-separator traz torch e onnxruntime proprios, e mistura-los ao
backend ou ao motor arriscaria quebrar os dois.

Uso: python separador_externo.py ENTRADA MODELO PASTA_SAIDA PASTA_MODELOS
Imprime, na ultima linha, um JSON com a lista de arquivos gerados.
"""
import json
import logging
import sys

from audio_separator.separator import Separator

entrada, modelo, saida, modelos = sys.argv[1:5]
sep = Separator(output_dir=saida, model_file_dir=modelos, output_format="FLAC",
                log_level=logging.WARNING)
sep.load_model(modelo)
arquivos = sep.separate(entrada)
print(json.dumps({"arquivos": arquivos}), flush=True)
