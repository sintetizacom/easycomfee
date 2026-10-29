"""Abre o app no navegador so quando o servidor ja responde (chamado pelo start.bat).

    pythonw backend/abrir_navegador.py 8600
"""
import sys
import time
import urllib.error
import urllib.request
import webbrowser


def pronto(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except urllib.error.HTTPError:  # respondeu, mesmo com erro: o servidor esta no ar
        return True
    except OSError:
        return False


if __name__ == "__main__":
    url = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else '8600'}"
    for _ in range(240):  # ate 2 minutos
        if pronto(url):
            break
        time.sleep(0.5)
    webbrowser.open(url)
