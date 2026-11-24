"""Voz natural do treinador (vozes neurais em português do Brasil, via edge-tts).

As frases são geradas uma vez e guardadas em dados/voz/ como MP3, então as próximas
reproduções são instantâneas. Precisa de internet só para gerar cada frase pela primeira vez.
Se não houver internet, gerar() devolve None e a página usa a voz do navegador.
"""
import asyncio
import hashlib
import os
import threading
import time

VOZES = {
    "francisca": "pt-BR-FranciscaNeural",
    "antonio": "pt-BR-AntonioNeural",
}
PASTA = os.path.join("dados", "voz")
_travas = {}
_trava_global = threading.Lock()
_indisponivel_ate = 0.0


def _arquivo(texto, voz):
    chave = hashlib.sha1(f"{voz}|{texto}".encode("utf-8")).hexdigest()[:20]
    return os.path.join(PASTA, f"{voz}_{chave}.mp3")


def disponivel():
    return time.time() >= _indisponivel_ate


def gerar(texto, voz="francisca"):
    """Devolve o caminho do MP3 da frase (gera se ainda não existir) ou None se não for possível."""
    global _indisponivel_ate
    voz = voz if voz in VOZES else "francisca"
    texto = " ".join(str(texto).split())[:300]
    if not texto:
        return None
    caminho = _arquivo(texto, voz)
    if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
        return caminho
    if not disponivel():
        return None
    with _trava_global:
        trava = _travas.setdefault(caminho, threading.Lock())
    with trava:  # evita gerar a mesma frase duas vezes ao mesmo tempo
        if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
            return caminho
        try:
            import edge_tts
            os.makedirs(PASTA, exist_ok=True)
            tmp = caminho + f".{threading.get_ident()}.tmp"

            async def _salvar():
                await edge_tts.Communicate(texto, VOZES[voz], rate="+8%", connect_timeout=5).save(tmp)

            asyncio.run(asyncio.wait_for(_salvar(), timeout=12))
            os.replace(tmp, caminho)
            return caminho
        except Exception:  # noqa: BLE001 — sem internet, serviço fora do ar, etc.
            _indisponivel_ate = time.time() + 60  # tenta de novo daqui a 1 minuto
            try:
                os.remove(tmp)
            except (OSError, UnboundLocalError):
                pass
            return None


def preaquecer(frases, voz="francisca"):
    """Gera as frases em segundo plano, para não haver atraso durante o treino."""
    def trabalhar():
        for f in frases:
            if gerar(f, voz) is None and not disponivel():
                break
    threading.Thread(target=trabalhar, daemon=True).start()
