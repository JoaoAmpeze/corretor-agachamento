"""Gera poses artificiais (sem câmera) para testar as regras de análise."""
import math

from src.detector_pose import Pose

PERNA = 0.45   # comprimento da canela e da coxa (m)
TRONCO = 0.55  # quadril até o ombro (m)
PX = 300       # pixels por metro na "imagem"
ORIGEM = (640, 650)  # posição do tornozelo na imagem


def _perna_lateral(angulo_joelho, canela=None):
    """Posições (x, y) relativas ao tornozelo, com y para baixo, para um ângulo de joelho.
    canela: inclinação da canela em relação à vertical (padrão: metade da flexão, canela e coxa simétricas)."""
    c = math.radians((180 - angulo_joelho) / 2 if canela is None else canela)
    d = math.radians(180 - angulo_joelho) - c  # inclinação da coxa
    joelho = (PERNA * math.sin(c), -PERNA * math.cos(c))
    quadril = (joelho[0] - PERNA * math.sin(d), joelho[1] - PERNA * math.cos(d))
    return joelho, quadril


def pose_lateral(angulo_joelho, inclinacao_tronco=30.0, calcanhar=0.0, canela=None, pe_x=0.0, cabeca=None):
    """Vista de lado. calcanhar = quanto o calcanhar sobe, em fração do comprimento da canela;
    pe_x = desloca o pé (calcanhar e ponta) para trás/frente; cabeca = ângulo do pescoço em relação ao tronco."""
    joelho, quadril = _perna_lateral(angulo_joelho, canela)
    t = math.radians(inclinacao_tronco)
    ombro = (quadril[0] + TRONCO * math.sin(t), quadril[1] - TRONCO * math.cos(t))
    pts = {"tornozelo": (0.0, 0.0), "joelho": joelho, "quadril": quadril, "ombro": ombro,
           "calcanhar": (-0.05 + pe_x, 0.06 - calcanhar * PERNA), "pe": (0.17 + pe_x, 0.07)}
    if cabeca is not None:  # orelha: continua a linha do tronco, girada para trás (olhando para cima)
        c = t - math.radians(cabeca)
        pts["orelha"] = (ombro[0] + 0.16 * math.sin(c), ombro[1] - 0.16 * math.cos(c))
    pose = Pose()
    for lado, desloc in (("esq", 0.0), ("dir", 0.02)):
        for nome, (x, y) in pts.items():
            # de lado, um quadril/ombro fica atrás do outro (profundidade z): o corpo está girado 90°
            pose.mundo[f"{nome}_{lado}"] = (x + desloc, y, 0.0 if lado == "esq" else 0.2)
            pose.imagem[f"{nome}_{lado}"] = (ORIGEM[0] + (x + desloc) * PX, ORIGEM[1] + y * PX)
            pose.visibilidade[f"{nome}_{lado}"] = 0.99 if lado == "esq" else 0.6
    _completar(pose)
    return pose


def pose_frontal(angulo_joelho, razao_joelhos=1.0, assimetria=0.0, desvio=0.0, base=0.9, razao_dir=None, ombros=0.0,
                 giro=0.0):
    """Vista de frente.
    assimetria: diferença (graus) entre os joelhos; desvio: quadril fora do centro (fração da base);
    base: distância entre tornozelos / largura dos ombros."""
    pose = Pose()
    meia_base = base * 0.40 / 2
    for lado, sinal in (("esq", -1), ("dir", 1)):
        joelho, quadril = _perna_lateral(angulo_joelho + sinal * assimetria / 2)  # x vira profundidade (z)
        x_pe = sinal * meia_base
        x_quadril = sinal * 0.18 + desvio * 2 * meia_base
        pts = {
            "tornozelo": (x_pe, 0.0, 0.0),
            "joelho": (x_pe * (razao_dir if (razao_dir is not None and lado == "dir") else razao_joelhos), joelho[1], -joelho[0]),
            "quadril": (x_quadril, quadril[1], -quadril[0]),
            "ombro": (sinal * 0.20 + desvio * 2 * meia_base,
                      quadril[1] - TRONCO + sinal * 0.20 * math.tan(math.radians(ombros)), -quadril[0]),
            "calcanhar": (x_pe, 0.05, 0.05),
            "pe": (x_pe * 1.2, 0.06, -0.15),
        }
        for nome, (x, y, z) in pts.items():
            # giro: corpo virado em relação à câmera (0 = de frente); muda só a profundidade em 3D
            z = z + x * math.tan(math.radians(giro))
            pose.mundo[f"{nome}_{lado}"] = (x, y, z)
            pose.imagem[f"{nome}_{lado}"] = (ORIGEM[0] + x * PX, ORIGEM[1] + y * PX)
            pose.visibilidade[f"{nome}_{lado}"] = 0.95
    _completar(pose)
    return pose


def _completar(pose):
    """Preenche os pontos que o analisador não usa (braços, cabeça) para a pose ficar completa."""
    for lado in ("esq", "dir"):
        for nome, base in (("cotovelo", "ombro"), ("punho", "ombro"), ("calcanhar", "tornozelo"),
                           ("pe", "tornozelo")):
            if f"{nome}_{lado}" in pose.imagem:
                continue
            pose.imagem[f"{nome}_{lado}"] = pose.imagem[f"{base}_{lado}"]
            pose.mundo[f"{nome}_{lado}"] = pose.mundo[f"{base}_{lado}"]
            pose.visibilidade[f"{nome}_{lado}"] = 0.9
    pose.imagem["nariz"] = pose.imagem["ombro_esq"]
    pose.mundo["nariz"] = pose.mundo["ombro_esq"]
    pose.visibilidade["nariz"] = 0.9


def angulos_repeticao(minimo, em_pe=172.0, frames=30):
    """Sequência de ângulos do joelho para uma repetição: desce até `minimo` e sobe."""
    descida = [em_pe - (em_pe - minimo) * i / frames for i in range(frames + 1)]
    return descida + descida[-2::-1]
