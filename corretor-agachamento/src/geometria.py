"""Funções geométricas usadas na análise do agachamento."""
import numpy as np


def angulo_entre_pontos(a, b, c):
    """Ângulo (em graus) no ponto B formado pelos segmentos B->A e B->C.

    Funciona com pontos 2D (pixels) ou 3D (metros).
    Ex.: quadril (A), joelho (B) e tornozelo (C) dão o ângulo do joelho:
    ~180° com a perna esticada e ~90° com a coxa paralela ao chão.
    """
    a, b, c = np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)
    ba, bc = a - b, c - b
    norma = np.linalg.norm(ba) * np.linalg.norm(bc)
    if norma == 0:
        return float("nan")
    cos = np.clip(np.dot(ba, bc) / norma, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def angulo_com_vertical(topo, base):
    """Ângulo (em graus) entre o segmento base->topo e a linha vertical.

    0° = segmento em pé (tronco reto); 90° = segmento deitado.
    Usa apenas x e y, então serve para coordenadas de imagem.
    """
    v = np.asarray(topo, float)[:2] - np.asarray(base, float)[:2]
    norma = np.linalg.norm(v)
    if norma == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(abs(v[1]) / norma, 0.0, 1.0))))


def distancia(a, b):
    """Distância euclidiana entre dois pontos (2D ou 3D)."""
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


class SuavizadorEMA:
    """Média móvel exponencial: reduz a tremedeira dos pontos entre frames."""

    def __init__(self, alfa=0.5):
        self.alfa = alfa
        self.valor = None

    def atualizar(self, x):
        if x is None or np.isnan(x):
            return self.valor
        self.valor = x if self.valor is None else self.alfa * x + (1 - self.alfa) * self.valor
        return self.valor

    def zerar(self):
        self.valor = None
