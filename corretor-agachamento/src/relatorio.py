"""Salva o resumo da sessão em CSV e mostra um resumo no terminal."""
import csv
import os
from collections import Counter

from .analisador_agachamento import dados_repeticao


def salvar_csv(repeticoes, caminho):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        colunas = ["serie", "numero", "vista", "nota", "correta", "erros", "angulo_minimo_joelho",
                   "angulo_minimo_quadril", "tronco_maximo", "alinhamento_maximo", "calcanhar_maximo",
                   "razao_joelhos_minima", "assimetria_joelhos", "desvio_quadril", "base", "descida_s", "duracao_s"]
        w.writerow(colunas)
        for r in repeticoes:
            d = dados_repeticao(r)
            d["correta"] = "sim" if r.correta else "não"
            d["erros"] = " | ".join(r.erros)
            w.writerow(["" if d[c] is None else d[c] for c in colunas])
    return caminho


def resumo_texto(repeticoes):
    total = len(repeticoes)
    if total == 0:
        return "Nenhuma repetição registrada."
    corretas = sum(r.correta for r in repeticoes)
    erros = Counter(e for r in repeticoes for e in r.erros)
    linhas = [f"Repetições: {total} | Corretas: {corretas} ({100 * corretas / total:.0f}%)"]
    for erro, n in erros.most_common():
        linhas.append(f"  - {erro}: {n}")
    return "\n".join(linhas)
