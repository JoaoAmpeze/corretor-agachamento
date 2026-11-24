"""Histórico de treinos salvo em um arquivo JSON local."""
import json
import os
import uuid
from datetime import datetime

ARQUIVO = os.path.join("dados", "historico.json")


def carregar(arquivo=ARQUIVO):
    try:
        with open(arquivo, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def salvar_sessao(resumo, fonte="", arquivo=ARQUIVO):
    sessoes = carregar(arquivo)
    sessao = {"id": uuid.uuid4().hex[:8], "data": datetime.now().isoformat(timespec="seconds"),
              "fonte": fonte, **resumo}
    sessoes.append(sessao)
    os.makedirs(os.path.dirname(arquivo) or ".", exist_ok=True)
    tmp = arquivo + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sessoes, f, ensure_ascii=False, indent=1)
    os.replace(tmp, arquivo)
    return sessao


def buscar(sessao_id, arquivo=ARQUIVO):
    return next((s for s in carregar(arquivo) if s["id"] == sessao_id), None)


def apagar(sessao_id, arquivo=ARQUIVO):
    sessoes = [s for s in carregar(arquivo) if s["id"] != sessao_id]
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(sessoes, f, ensure_ascii=False, indent=1)
