"""Regras de análise do agachamento: contagem de repetições, medidas de cada articulação e erros.

Fluxo por frame:
  pose -> medidas (joelho, quadril, tronco, canela, calcanhar, abertura dos joelhos, simetria, base)
       -> suavização -> máquina de estados (em pé / descendo / subindo)
       -> alertas em tempo real e avaliação de cada repetição concluída.

Vista lateral (de lado): profundidade, tronco, tronco × canela, calcanhar, quadril subindo antes do peito,
                        peso no meio do pé e cabeça alinhada.
Vista frontal (de frente): profundidade, joelhos para dentro (valgo), joelho na linha do pé, simetria,
                          ombros nivelados e base dos pés.
Nas duas: extensão completa no topo, controle no fundo (sem quique) e ritmo. A fadiga é avaliada na série (treino.py).
"""
import math
from dataclasses import dataclass, field

from .geometria import SuavizadorEMA, angulo_com_vertical, angulo_entre_pontos, distancia

EM_PE, DESCENDO, SUBINDO = "Em pé", "Descendo", "Subindo"

ERRO_PROFUNDIDADE = "Profundidade insuficiente"
ERRO_TRONCO = "Tronco muito inclinado"
ERRO_ALINHAMENTO = "Tronco à frente da canela"
ERRO_CALCANHAR = "Calcanhar saindo do chão"
ERRO_JOELHO = "Joelhos para dentro"
ERRO_SIMETRIA = "Movimento assimétrico"
ERRO_BASE = "Base dos pés inadequada"
ERRO_SUBIDA = "Quadril subindo antes do peito"
ERRO_EQUILIBRIO = "Peso fora do meio do pé"
ERRO_EXTENSAO = "Não estendeu totalmente"
ERRO_LINHA_PE = "Joelho fora da linha do pé"
ERRO_OMBROS = "Ombros desnivelados"
ERRO_QUIQUE = "Quique no fundo"
ERRO_CABECA = "Cabeça desalinhada"
AVISO_FADIGA = "Sinal de fadiga"

DICAS = {
    ERRO_PROFUNDIDADE: "Desça até a coxa ficar paralela ao chão",
    ERRO_TRONCO: "Mantenha o peito aberto e o tronco mais reto",
    ERRO_ALINHAMENTO: "Deixe o tronco mais paralelo à canela",
    ERRO_CALCANHAR: "Mantenha os calcanhares no chão",
    ERRO_JOELHO: "Empurre os joelhos para fora, na direção dos pés",
    ERRO_SIMETRIA: "Distribua o peso igualmente nas duas pernas",
    ERRO_BASE: "Ajuste os pés na largura dos ombros",
    ERRO_SUBIDA: "Suba o peito junto com o quadril",
    ERRO_EQUILIBRIO: "Mantenha o peso no meio do pé",
    ERRO_EXTENSAO: "Suba até ficar totalmente em pé",
    ERRO_LINHA_PE: "Mantenha cada joelho na direção da ponta do pé",
    ERRO_OMBROS: "Mantenha os ombros nivelados",
    ERRO_QUIQUE: "Controle a descida e não quique no fundo",
    ERRO_CABECA: "Olhe para a frente, com o pescoço alinhado ao tronco",
    AVISO_FADIGA: "A técnica está caindo. Se precisar, encerre a série",
}


@dataclass
class Limites:
    """Valores de referência (em graus ou proporção). Podem ser ajustados nos testes."""
    # Contagem adaptativa: a referência "em pé" é o maior ângulo do joelho visto recentemente,
    # porque a perna esticada não mede 180° na prática (varia com a pessoa, a câmera e o modelo).
    queda_inicio: float = 15.0        # a repetição começa quando o joelho dobra 15° abaixo da referência
    folga_fim: float = 12.0           # termina quando volta a 12° da referência (ou a 40% da amplitude)
    amplitude_minima: float = 30.0    # movimentos menores que isso não contam como repetição
    referencia_minima: float = 135.0  # só começa a contar se a pessoa esteve de pé (evita contar sentada)
    fundo: float = 30.0               # "parte baixa" do movimento: joelho 30° abaixo da referência
    # Critérios
    joelho_profundidade: float = 100.0   # o menor ângulo do joelho deve chegar a este valor
    tronco_maximo: float = 50.0          # inclinação máxima do tronco em relação à vertical
    alinhamento_maximo: float = 25.0     # tronco pode inclinar no máximo 25° a mais que a canela
    calcanhar_maximo: float = 0.08       # subida do calcanhar, em fração do comprimento da canela
    razao_joelhos_minima: float = 0.75   # distância entre joelhos / distância entre tornozelos
    assimetria_joelhos_maxima: float = 15.0  # diferença entre o ângulo dos dois joelhos
    desvio_quadril_maximo: float = 0.15  # quadril fora do centro dos pés, em fração da base
    inclinacao_quadril_maxima: float = 7.0  # linha dos quadris inclinada (um lado mais baixo)
    base_minima: float = 0.8             # distância entre tornozelos / largura dos ombros
    base_maxima: float = 2.0
    subida_quadril_maxima: float = 12.0  # o tronco não deve inclinar mais de 12° além do fundo durante a subida
    equilibrio_maximo: float = 0.6       # meio do tronco fora do meio do pé, em comprimentos de pé
    extensao_deficit_maximo: float = 15.0  # joelho no topo até 15° abaixo do "em pé" da pessoa
    linha_pe_maxima: float = 0.2         # joelho fora da linha quadril → ponta do pé, em fração da base
    ombros_maximo: float = 8.0           # inclinação da linha dos ombros
    velocidade_fundo_maxima: float = 130.0  # °/s de chegada e de saída do fundo (as duas altas = quique)
    cabeca_maxima: float = 50.0          # ângulo entre pescoço e tronco
    giro_frontal: float = 25.0           # giro do corpo (3D) abaixo disso = câmera de frente
    giro_lateral: float = 65.0           # acima disso = câmera de lado; entre os dois = diagonal


def _interpolar(x, pontos):
    """Interpolação linear por partes: pontos = [(x0, y0), (x1, y1), ...] com x crescente."""
    if x <= pontos[0][0]:
        return pontos[0][1]
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pontos[-1][1]


# Curvas de pontuação (0 a 100) de cada critério. No limite de erro a nota do critério é 70.
def nota_profundidade(angulo_min):
    return _interpolar(angulo_min, [(90, 100), (100, 70), (140, 0)])


def nota_tronco(tronco_max):
    return _interpolar(tronco_max, [(40, 100), (50, 70), (75, 0)])


def nota_alinhamento(diferenca_max):
    return _interpolar(diferenca_max, [(10, 100), (25, 70), (45, 0)])


def nota_calcanhar(subida_max):
    return _interpolar(subida_max, [(0.03, 100), (0.08, 70), (0.2, 0)])


def nota_joelhos(razao_min):
    return _interpolar(-razao_min, [(-0.9, 100), (-0.75, 70), (-0.45, 0)])


def nota_simetria(dif_joelhos, desvio_quadril, inclinacao_quadril=None):
    a = _interpolar(dif_joelhos or 0, [(8, 100), (15, 70), (35, 0)])
    b = _interpolar(desvio_quadril or 0, [(0.08, 100), (0.15, 70), (0.35, 0)])
    c = _interpolar(inclinacao_quadril or 0, [(3, 100), (7, 70), (15, 0)])
    return min(a, b, c)


def nota_base(razao):
    return _interpolar(razao, [(0.5, 0), (0.8, 70), (0.9, 100), (1.8, 100), (2.0, 70), (2.6, 0)])


def nota_subida(graus):
    return _interpolar(graus, [(5, 100), (12, 70), (25, 0)])


def nota_equilibrio(desvio):
    return _interpolar(desvio, [(0.3, 100), (0.6, 70), (1.0, 0)])


def nota_extensao(deficit):
    return _interpolar(deficit, [(6, 100), (15, 70), (30, 0)])


def nota_linha_pe(desvio):
    return _interpolar(desvio, [(0.1, 100), (0.2, 70), (0.4, 0)])


def nota_ombros(graus):
    return _interpolar(graus, [(3, 100), (8, 70), (15, 0)])


def nota_controle(velocidade):
    return _interpolar(velocidade, [(90, 100), (130, 70), (220, 0)])


def nota_cabeca(graus):
    return _interpolar(graus, [(30, 100), (50, 70), (70, 0)])


def nota_ritmo(descida_s):
    return _interpolar(descida_s, [(0.25, 40), (0.6, 100)])


def classificar_nota(nota):
    if nota >= 85:
        return "Excelente"
    if nota >= 70:
        return "Boa"
    if nota >= 50:
        return "Regular"
    return "Precisa melhorar"


@dataclass
class Repeticao:
    numero: int
    angulo_minimo_joelho: float
    tronco_maximo: float = None
    alinhamento_maximo: float = None      # (tronco − canela) no fundo do agachamento, vista lateral
    calcanhar_maximo: float = None        # subida do calcanhar, vista lateral
    razao_joelhos_minima: float = None    # vista frontal
    assimetria_joelhos: float = None      # vista frontal
    desvio_quadril: float = None          # vista frontal
    base: float = None                    # vista frontal, no início da repetição
    angulo_minimo_quadril: float = None
    subida_tronco: float = None           # quanto o tronco inclinou além do fundo durante a subida
    equilibrio_maximo: float = None       # meio do tronco fora do meio do pé (comprimentos de pé)
    extensao_deficit: float = None        # quanto faltou para ficar totalmente em pé antes da repetição
    linha_pe_maxima: float = None         # joelho fora da linha quadril → ponta do pé (fração da base)
    ombros_maximo: float = None           # inclinação da linha dos ombros (graus)
    velocidade_fundo: float = None        # °/s ao chegar e sair do fundo (o menor dos dois)
    cabeca_maxima: float = None           # ângulo entre pescoço e tronco (graus)
    inclinacao_quadril: float = None      # inclinação da linha dos quadris na parte baixa (vista frontal)
    avisos: list = field(default_factory=list)
    vistas: set = field(default_factory=set, repr=False)
    amostras: dict = field(default_factory=dict, repr=False)
    tronco_fundo: float = None
    tronco_max_subida: float = None
    vista: str = ""
    duracao_s: float = 0.0
    descida_s: float = None
    erros: list = field(default_factory=list)
    nota: int = 0
    notas: dict = field(default_factory=dict)  # nota de cada critério
    serie: int = 1
    angulo_referencia: float = 0.0  # ângulo "em pé" no início da repetição

    @property
    def correta(self):
        return not self.erros

    def calcular_nota(self):
        """Nota de 0 a 100. Mistura o pior critério de técnica (60%) com a média (40%),
        para que um erro grave não seja escondido pelos outros critérios.
        O ritmo entra só na média: é uma recomendação, não um erro."""
        n = {"profundidade": nota_profundidade(self.angulo_minimo_joelho)}
        if self.tronco_maximo is not None:
            n["tronco"] = nota_tronco(self.tronco_maximo)
        if self.alinhamento_maximo is not None:
            n["alinhamento"] = nota_alinhamento(self.alinhamento_maximo)
        if self.calcanhar_maximo is not None:
            n["calcanhar"] = nota_calcanhar(self.calcanhar_maximo)
        if self.razao_joelhos_minima is not None:
            n["joelhos"] = nota_joelhos(self.razao_joelhos_minima)
        if self.assimetria_joelhos is not None or self.desvio_quadril is not None or self.inclinacao_quadril is not None:
            n["simetria"] = nota_simetria(self.assimetria_joelhos, self.desvio_quadril, self.inclinacao_quadril)
        if self.base is not None:
            n["base"] = nota_base(self.base)
        if self.subida_tronco is not None:
            n["subida"] = nota_subida(self.subida_tronco)
        if self.equilibrio_maximo is not None:
            n["equilibrio"] = nota_equilibrio(self.equilibrio_maximo)
        if self.linha_pe_maxima is not None:
            n["linha_pe"] = nota_linha_pe(self.linha_pe_maxima)
        if self.ombros_maximo is not None:
            n["ombros"] = nota_ombros(self.ombros_maximo)
        if self.cabeca_maxima is not None:
            n["cabeca"] = nota_cabeca(self.cabeca_maxima)
        if self.extensao_deficit is not None:
            n["extensao"] = nota_extensao(self.extensao_deficit)
        if self.velocidade_fundo is not None:
            n["controle"] = nota_controle(self.velocidade_fundo)
        tecnica = list(n.values())
        descida = self.descida_s if self.descida_s is not None else self.duracao_s / 2
        n["ritmo"] = nota_ritmo(descida)
        media = sum(n.values()) / len(n)
        self.notas = {k: round(v) for k, v in n.items()}
        self.nota = round(0.6 * min(tecnica) + 0.4 * media)
        return self.nota


@dataclass
class Estado:
    """O que a interface precisa mostrar a cada frame."""
    pessoa_detectada: bool = False
    vista: str = "-"
    fase: str = EM_PE
    angulo_joelho: float = None
    angulo_quadril: float = None
    inclinacao_tronco: float = None
    inclinacao_canela: float = None
    alinhamento: float = None      # tronco − canela (graus)
    calcanhar: float = None        # subida do calcanhar (fração da canela)
    razao_joelhos: float = None
    assimetria_joelhos: float = None
    desvio_quadril: float = None
    base: float = None
    equilibrio: float = None       # meio do tronco em relação ao meio do pé (comprimentos de pé, + = à frente)
    ombros: float = None           # inclinação da linha dos ombros
    inclinacao_quadril: float = None  # inclinação da linha dos quadris
    linha_pe: float = None         # maior desvio do joelho em relação à linha quadril → ponta do pé
    cabeca: float = None           # ângulo pescoço × tronco
    alertas: list = field(default_factory=list)
    lado: str = "esq"
    total: int = 0
    corretas: int = 0
    ultima: Repeticao = None


class AnalisadorAgachamento:
    def __init__(self, limites=None, vista="auto"):
        self.limites = limites or Limites()
        self.vista_fixa = vista  # "auto", "lateral" ou "frontal"
        self.repeticoes = []
        self._suav = {k: SuavizadorEMA(0.5) for k in (
            "joelho", "quadril", "tronco", "canela", "calcanhar", "razao", "assimetria", "desvio", "base",
            "equilibrio", "ombros", "linha_pe", "cabeca", "incl_quadril")}
        self._razao_vista = SuavizadorEMA(0.35)  # giro do corpo (posição da câmera)
        self._base_calcanhar = SuavizadorEMA(0.1)
        self.zerar()

    def zerar(self):
        self.repeticoes.clear()
        for s in [*self._suav.values(), self._razao_vista, self._base_calcanhar]:
            s.zerar()
        self._fase = EM_PE
        self._rep_atual = None
        self._inicio_rep = 0.0
        self._t_minimo = 0.0
        self._topo = None
        self._t_topo = 0.0
        self._lado = None
        self._vista = None
        self._persistencia = {}
        # maior ângulo do joelho em pé visto no treino, separado por posição de câmera: o mesmo joelho
        # esticado mede ~175° de lado e ~160° de frente (o modelo estima pior a profundidade de frente)
        self._ref_extensao = {}
        self._vista_da_ref = None
        self._amostras = []        # (tempo, ângulo do joelho) da repetição atual, para medir o quique
        self._estado = Estado()

    def reiniciar_movimento(self):
        """Descarta uma repetição em andamento (ex.: ao voltar do descanso), mantendo as concluídas."""
        self._fase = EM_PE
        self._rep_atual = None
        self._estado.fase = EM_PE

    # ------------------------------------------------------------------ medidas
    def _detectar_vista(self, pose):
        """Posição da câmera pelo giro do corpo em 3D: o ângulo da linha dos quadris e dos ombros em
        relação ao plano da câmera. ~0° = de frente, ~90° = de lado, no meio = diagonal.
        Na diagonal, as medidas feitas na imagem (2D) ficam distorcidas, então só os critérios 3D valem."""
        if self.vista_fixa != "auto":
            return self.vista_fixa
        m = pose.mundo

        def giro(a, b):
            dx, dz = m[a][0] - m[b][0], m[a][2] - m[b][2]
            return math.degrees(math.atan2(abs(dz), abs(dx)))
        g = self._razao_vista.atualizar((giro("quadril_esq", "quadril_dir") + giro("ombro_esq", "ombro_dir")) / 2)
        L, atual = self.limites, self._vista
        # histerese de 5°: a vista só muda quando passa com folga do limite
        if atual == "frontal" and g < L.giro_frontal + 5 or atual != "frontal" and g < L.giro_frontal:
            self._vista = "frontal"
        elif atual == "lateral" and g > L.giro_lateral - 5 or atual != "lateral" and g > L.giro_lateral:
            self._vista = "lateral"
        else:
            self._vista = "diagonal"
        return self._vista

    def _lado_mais_visivel(self, pose):
        """Lado do corpo virado para a câmera. Só troca de lado com uma diferença clara de
        visibilidade, para o ângulo não ficar pulando entre a perna da frente e a de trás."""
        v = pose.visibilidade
        esq = sum(v[f"{p}_esq"] for p in ("ombro", "quadril", "joelho", "tornozelo"))
        dir_ = sum(v[f"{p}_dir"] for p in ("ombro", "quadril", "joelho", "tornozelo"))
        melhor = "esq" if esq >= dir_ else "dir"
        if self._lado is None or (melhor != self._lado and abs(esq - dir_) > 0.4):
            self._lado = melhor
        return self._lado

    @staticmethod
    def _angulo_joelho_lado(pose, s):
        m = pose.mundo
        return angulo_entre_pontos(m[f"quadril_{s}"], m[f"joelho_{s}"], m[f"tornozelo_{s}"])

    @staticmethod
    def _angulo_quadril_lado(pose, s):
        m = pose.mundo
        return angulo_entre_pontos(m[f"ombro_{s}"], m[f"quadril_{s}"], m[f"joelho_{s}"])

    def _medir(self, pose, lado, vista, e):
        """Calcula todas as medidas do frame e guarda (suavizadas) no estado."""
        img, S = pose.imagem, self._suav
        if vista == "diagonal":
            # só medidas 3D, que não dependem da posição da câmera
            e.angulo_joelho = S["joelho"].atualizar(self._angulo_joelho_lado(pose, lado))
            e.angulo_quadril = S["quadril"].atualizar(self._angulo_quadril_lado(pose, lado))
            m = pose.mundo
            meio = lambda a, b: tuple((x + y) / 2 for x, y in zip(m[a], m[b]))
            mo, mq = meio("ombro_esq", "ombro_dir"), meio("quadril_esq", "quadril_dir")
            e.inclinacao_tronco = S["tronco"].atualizar(angulo_entre_pontos(mo, mq, (mq[0], mq[1] - 1.0, mq[2])))
            for campo in ("inclinacao_canela", "alinhamento", "calcanhar", "equilibrio", "cabeca", "razao_joelhos",
                          "assimetria_joelhos", "desvio_quadril", "base", "ombros", "linha_pe", "inclinacao_quadril"):
                setattr(e, campo, None)
            return
        if vista == "frontal":
            ang_e, ang_d = self._angulo_joelho_lado(pose, "esq"), self._angulo_joelho_lado(pose, "dir")
            e.angulo_joelho = S["joelho"].atualizar((ang_e + ang_d) / 2)
            e.angulo_quadril = S["quadril"].atualizar(
                (self._angulo_quadril_lado(pose, "esq") + self._angulo_quadril_lado(pose, "dir")) / 2)
            entre_tornozelos = abs(img["tornozelo_esq"][0] - img["tornozelo_dir"][0])
            largura_ombros = abs(img["ombro_esq"][0] - img["ombro_dir"][0])
            if entre_tornozelos >= 1:
                e.razao_joelhos = S["razao"].atualizar(abs(img["joelho_esq"][0] - img["joelho_dir"][0]) / entre_tornozelos)
                centro_pes = (img["tornozelo_esq"][0] + img["tornozelo_dir"][0]) / 2
                centro_quadril = (img["quadril_esq"][0] + img["quadril_dir"][0]) / 2
                e.desvio_quadril = S["desvio"].atualizar(abs(centro_quadril - centro_pes) / entre_tornozelos)
            if largura_ombros >= 1:
                e.base = S["base"].atualizar(entre_tornozelos / largura_ombros)
            e.assimetria_joelhos = S["assimetria"].atualizar(abs(ang_e - ang_d))
            oe, od = img["ombro_esq"], img["ombro_dir"]
            e.ombros = S["ombros"].atualizar(math.degrees(math.atan2(abs(oe[1] - od[1]), abs(oe[0] - od[0]) or 1e-6)))
            qe, qd = img["quadril_esq"], img["quadril_dir"]
            e.inclinacao_quadril = S["incl_quadril"].atualizar(math.degrees(math.atan2(abs(qe[1] - qd[1]), abs(qe[0] - qd[0]) or 1e-6)))
            e.linha_pe = None
            if entre_tornozelos >= 1 and pose.visivel("pe_esq", "pe_dir", minimo=0.3):
                desvios = []
                for l in ("esq", "dir"):
                    q, j, t = img[f"quadril_{l}"], img[f"joelho_{l}"], img[f"pe_{l}"]
                    if abs(t[1] - q[1]) < 1:
                        continue
                    x_linha = q[0] + (t[0] - q[0]) * (j[1] - q[1]) / (t[1] - q[1])
                    # só conta o joelho indo para DENTRO da linha (valgo); joelho para fora acompanha o pé
                    centro = (img["tornozelo_esq"][0] + img["tornozelo_dir"][0]) / 2
                    desvios.append(max(abs(x_linha - centro) - abs(j[0] - centro), 0.0) / entre_tornozelos)
                if desvios:
                    e.linha_pe = S["linha_pe"].atualizar(max(desvios))
            e.inclinacao_tronco = e.inclinacao_canela = e.alinhamento = e.calcanhar = None
            e.equilibrio = e.cabeca = None
        else:
            e.angulo_joelho = S["joelho"].atualizar(self._angulo_joelho_lado(pose, lado))
            e.angulo_quadril = S["quadril"].atualizar(self._angulo_quadril_lado(pose, lado))
            e.inclinacao_tronco = S["tronco"].atualizar(angulo_com_vertical(img[f"ombro_{lado}"], img[f"quadril_{lado}"]))
            e.inclinacao_canela = S["canela"].atualizar(angulo_com_vertical(img[f"joelho_{lado}"], img[f"tornozelo_{lado}"]))
            e.alinhamento = e.inclinacao_tronco - e.inclinacao_canela
            e.calcanhar = None
            if pose.visivel(f"calcanhar_{lado}", f"pe_{lado}"):
                canela = distancia(img[f"joelho_{lado}"], img[f"tornozelo_{lado}"]) or 1.0
                # quanto o calcanhar está acima da ponta do pé (y cresce para baixo na imagem)
                elevacao = (img[f"pe_{lado}"][1] - img[f"calcanhar_{lado}"][1]) / canela
                if self._fase == EM_PE:  # em pé, aprende a posição normal do pé
                    self._base_calcanhar.atualizar(elevacao)
                base = self._base_calcanhar.valor if self._base_calcanhar.valor is not None else elevacao
                e.calcanhar = S["calcanhar"].atualizar(max(elevacao - base, 0.0))
            e.equilibrio = None
            if pose.visivel(f"calcanhar_{lado}", f"pe_{lado}"):
                c, p_ = img[f"calcanhar_{lado}"], img[f"pe_{lado}"]
                comprimento_pe = abs(p_[0] - c[0])
                if comprimento_pe >= 1:
                    meio_pe = (c[0] + p_[0]) / 2
                    meio_tronco = (img[f"ombro_{lado}"][0] + img[f"quadril_{lado}"][0]) / 2
                    frente = 1 if p_[0] > c[0] else -1  # para que lado o pé aponta
                    e.equilibrio = S["equilibrio"].atualizar(frente * (meio_tronco - meio_pe) / comprimento_pe)
            e.cabeca = None
            if pose.visivel(f"orelha_{lado}", minimo=0.5):
                q, o, ore = img[f"quadril_{lado}"], img[f"ombro_{lado}"], img[f"orelha_{lado}"]
                e.cabeca = S["cabeca"].atualizar(angulo_entre_pontos(
                    (2 * o[0] - q[0], 2 * o[1] - q[1]), o, ore))  # 0° = cabeça na linha do tronco
            e.razao_joelhos = e.assimetria_joelhos = e.desvio_quadril = e.base = None
            e.ombros = e.linha_pe = e.inclinacao_quadril = None

    # ------------------------------------------------------------------ processamento
    def processar(self, pose, tempo_s):
        """Atualiza a análise com a pose de um frame. Devolve um Estado para a interface."""
        e = self._estado
        e.alertas = []
        if pose is None or not self._pernas_visiveis(pose):
            e.pessoa_detectada = False
            e.alertas = ["Afaste-se para aparecer de corpo inteiro"]
            return e

        e.pessoa_detectada = True
        vista = self._detectar_vista(pose)
        lado = self._lado_mais_visivel(pose)
        e.vista, e.lado = vista, lado
        self._medir(pose, lado, vista, e)
        self._atualizar_fase(e, vista, tempo_s)
        self._alertas_tempo_real(e)
        # um alerta só aparece se continuar por 4 quadros seguidos (evita avisos por um erro isolado do modelo)
        self._persistencia = {a: self._persistencia.get(a, 0) + 1 for a in e.alertas}
        e.alertas = [a for a in e.alertas if self._persistencia[a] >= 4]
        return e

    def _pernas_visiveis(self, pose):
        # Precisa ver quadril, joelho e tornozelo de pelo menos um lado
        return (pose.visivel("quadril_esq", "joelho_esq", "tornozelo_esq")
                or pose.visivel("quadril_dir", "joelho_dir", "tornozelo_dir"))

    def _atualizar_fase(self, e, vista, tempo_s):
        L, ang = self.limites, e.angulo_joelho
        if self._fase == EM_PE:
            # referência "em pé": sobe na hora com o ângulo e desce devagar (4° por segundo)
            if self._topo is None or ang >= self._topo:
                self._topo = ang
            else:
                self._topo = max(ang, self._topo - 4.0 * max(tempo_s - self._t_topo, 0.0))
            self._t_topo = tempo_s
            if vista != self._vista_da_ref:  # mudou a posição: a referência recomeça (vídeo com cortes, pessoa girou)
                self._ref_extensao.pop(vista, None)
                self._vista_da_ref = vista
            self._ref_extensao[vista] = max(self._ref_extensao.get(vista, ang), ang)
            topo = min(self._topo, 180.0)
            if topo >= L.referencia_minima and ang < topo - L.queda_inicio:
                self._fase = DESCENDO
                self._inicio_rep = self._t_minimo = tempo_s
                self._rep_atual = Repeticao(numero=len(self.repeticoes) + 1, angulo_minimo_joelho=ang,
                                            vista=vista, angulo_referencia=topo, base=e.base,
                                            extensao_deficit=max(min(self._ref_extensao[vista], 180.0) - topo, 0.0))
                self._amostras = [(self._t_topo, topo), (tempo_s, ang)]
        else:
            r = self._rep_atual
            self._amostras.append((tempo_s, ang))
            if ang < r.angulo_minimo_joelho:
                r.angulo_minimo_joelho = ang
                self._t_minimo = tempo_s
                r.tronco_fundo = e.inclinacao_tronco
                # alinhamento tronco × canela: vale a posição do fundo do agachamento
                if e.alinhamento is not None and ang < r.angulo_referencia - self.limites.fundo:
                    r.alinhamento_maximo = e.alinhamento
                self._fase = DESCENDO
            elif ang > r.angulo_minimo_joelho + 8:  # folga para não oscilar entre fases
                self._fase = SUBINDO
            self._registrar_medidas(r, e)
            amplitude = r.angulo_referencia - r.angulo_minimo_joelho
            # termina quando a pessoa já subiu boa parte do caminho de volta. Assim conta também quem não
            # estica totalmente; a falta de extensão é avaliada à parte (critério "extensão no topo")
            if ang >= r.angulo_referencia - max(L.folga_fim, 0.4 * amplitude):
                if amplitude >= L.amplitude_minima:
                    self._finalizar_repeticao(tempo_s)
                else:  # movimento pequeno (ajuste de postura): não conta
                    self._rep_atual = None
                    self._fase = EM_PE
                self._topo, self._t_topo = ang, tempo_s
        e.fase = self._fase

    def _registrar_medidas(self, r, e):
        """Guarda os valores de cada medida durante a repetição. No fim, vale o percentil 80 (o "pior valor
        típico") e não o máximo absoluto: um quadro isolado em que o modelo erra a posição de um ponto não
        pode, sozinho, transformar uma repetição boa em erro."""
        no_fundo = e.angulo_joelho < r.angulo_referencia - self.limites.fundo
        r.vistas.add(e.vista)
        guardar = lambda chave, v: v is not None and r.amostras.setdefault(chave, []).append(v)
        if e.angulo_quadril is not None:
            r.angulo_minimo_quadril = e.angulo_quadril if r.angulo_minimo_quadril is None else min(r.angulo_minimo_quadril, e.angulo_quadril)
        guardar("tronco", e.inclinacao_tronco)
        guardar("calcanhar", e.calcanhar)
        guardar("ombros", e.ombros)
        guardar("cabeca", e.cabeca)
        if self._fase == SUBINDO:
            guardar("tronco_subida", e.inclinacao_tronco)
        if no_fundo:  # medidas que só fazem sentido na parte baixa do agachamento
            guardar("razao_joelhos", None if e.razao_joelhos is None else -e.razao_joelhos)  # menor = pior
            guardar("assimetria", e.assimetria_joelhos)
            guardar("desvio_quadril", e.desvio_quadril)
            guardar("inclinacao_quadril", e.inclinacao_quadril)
            guardar("equilibrio", None if e.equilibrio is None else abs(e.equilibrio))
            guardar("linha_pe", e.linha_pe)

    @staticmethod
    def _p80(valores):
        v = sorted(valores)
        return v[min(int(round(0.8 * (len(v) - 1))), len(v) - 1)] if v else None

    def _resumir_medidas(self, r):
        a = {k: self._p80(v) for k, v in r.amostras.items()}
        r.tronco_maximo = a.get("tronco")
        r.calcanhar_maximo = a.get("calcanhar")
        r.ombros_maximo = a.get("ombros")
        r.cabeca_maxima = a.get("cabeca")
        r.tronco_max_subida = a.get("tronco_subida")
        r.razao_joelhos_minima = None if a.get("razao_joelhos") is None else -a["razao_joelhos"]
        r.assimetria_joelhos = a.get("assimetria")
        r.desvio_quadril = a.get("desvio_quadril")
        r.inclinacao_quadril = a.get("inclinacao_quadril")
        r.equilibrio_maximo = a.get("equilibrio")
        r.linha_pe_maxima = a.get("linha_pe")
        if len(r.vistas) > 1:
            # a câmera (ou a pessoa) mudou de posição durante a repetição: as medidas feitas na imagem
            # misturam duas vistas e não são confiáveis. Ficam só as medidas 3D.
            for campo in ("alinhamento_maximo", "calcanhar_maximo", "equilibrio_maximo", "cabeca_maxima",
                          "razao_joelhos_minima", "linha_pe_maxima", "assimetria_joelhos", "desvio_quadril",
                          "inclinacao_quadril", "ombros_maximo", "base"):
                setattr(r, campo, None)
            r.vista = "mista"

    def _finalizar_repeticao(self, tempo_s):
        L, r = self.limites, self._rep_atual
        r.duracao_s = round(tempo_s - self._inicio_rep, 2)
        r.descida_s = round(self._t_minimo - self._inicio_rep, 2)
        self._resumir_medidas(r)
        if r.tronco_fundo is not None and r.tronco_max_subida is not None:
            r.subida_tronco = max(r.tronco_max_subida - r.tronco_fundo, 0.0)
        r.velocidade_fundo = self._velocidade_no_fundo()
        if r.angulo_minimo_joelho > L.joelho_profundidade:
            r.erros.append(ERRO_PROFUNDIDADE)
        if r.tronco_maximo is not None and r.tronco_maximo > L.tronco_maximo:
            r.erros.append(ERRO_TRONCO)
        elif r.alinhamento_maximo is not None and r.alinhamento_maximo > L.alinhamento_maximo:
            r.erros.append(ERRO_ALINHAMENTO)  # só quando o tronco não passou do limite absoluto
        if r.calcanhar_maximo is not None and r.calcanhar_maximo > L.calcanhar_maximo:
            r.erros.append(ERRO_CALCANHAR)
        if r.razao_joelhos_minima is not None and r.razao_joelhos_minima < L.razao_joelhos_minima:
            r.erros.append(ERRO_JOELHO)
        if ((r.assimetria_joelhos or 0) > L.assimetria_joelhos_maxima
                or (r.desvio_quadril or 0) > L.desvio_quadril_maximo
                or (r.inclinacao_quadril or 0) > L.inclinacao_quadril_maxima):
            r.erros.append(ERRO_SIMETRIA)
        if r.base is not None and not (L.base_minima <= r.base <= L.base_maxima):
            r.erros.append(ERRO_BASE)
        if (r.linha_pe_maxima or 0) > L.linha_pe_maxima and ERRO_JOELHO not in r.erros:
            r.erros.append(ERRO_LINHA_PE)
        if (r.ombros_maximo or 0) > L.ombros_maximo:
            r.erros.append(ERRO_OMBROS)
        if (r.subida_tronco or 0) > L.subida_quadril_maxima:
            r.erros.append(ERRO_SUBIDA)
        if (r.equilibrio_maximo or 0) > L.equilibrio_maximo:
            r.erros.append(ERRO_EQUILIBRIO)
        if (r.cabeca_maxima or 0) > L.cabeca_maxima:
            r.erros.append(ERRO_CABECA)
        if (r.extensao_deficit or 0) > L.extensao_deficit_maximo:
            r.erros.append(ERRO_EXTENSAO)
        if (r.velocidade_fundo or 0) > L.velocidade_fundo_maxima:
            r.erros.append(ERRO_QUIQUE)
        r.calcular_nota()
        self.repeticoes.append(r)
        self._rep_atual = None
        self._fase = EM_PE
        e = self._estado
        e.total = len(self.repeticoes)
        e.corretas = sum(rep.correta for rep in self.repeticoes)
        e.ultima = r

    def _velocidade_no_fundo(self, janela=0.25):
        """Velocidade (°/s) do joelho ao chegar e ao sair do ponto mais baixo. Devolve a menor das duas:
        só é quique quando a pessoa chega rápido E volta rápido, sem controlar o fundo."""
        a = self._amostras
        if len(a) < 4:
            return None
        i_min = min(range(len(a)), key=lambda i: a[i][1])
        t_min, ang_min = a[i_min]
        antes = [p for p in a[:i_min] if p[0] >= t_min - janela] or a[:1]
        depois = [p for p in a[i_min + 1:] if p[0] <= t_min + janela] or a[-1:]
        v = []
        for t, ang in (antes[0], depois[-1]):
            if abs(t - t_min) > 1e-6:
                v.append(abs(ang - ang_min) / abs(t - t_min))
        return min(v) if len(v) == 2 else None

    def _alertas_tempo_real(self, e):
        """Correções faladas e mostradas durante o movimento, da mais importante para a menos."""
        L, r = self.limites, self._rep_atual
        if e.fase == EM_PE or r is None:
            return
        no_fundo = e.angulo_joelho < r.angulo_referencia - L.fundo
        if e.inclinacao_tronco is not None and e.inclinacao_tronco > L.tronco_maximo:
            e.alertas.append(DICAS[ERRO_TRONCO])
        if e.calcanhar is not None and e.calcanhar > L.calcanhar_maximo:
            e.alertas.append(DICAS[ERRO_CALCANHAR])
        if no_fundo and e.razao_joelhos is not None and e.razao_joelhos < L.razao_joelhos_minima:
            e.alertas.append(DICAS[ERRO_JOELHO])
        if no_fundo and ((e.desvio_quadril or 0) > L.desvio_quadril_maximo
                         or (e.assimetria_joelhos or 0) > L.assimetria_joelhos_maxima):
            e.alertas.append(DICAS[ERRO_SIMETRIA])
        if (e.fase == SUBINDO and e.inclinacao_tronco is not None and r.tronco_fundo is not None
                and e.inclinacao_tronco > r.tronco_fundo + L.subida_quadril_maxima):
            e.alertas.append(DICAS[ERRO_SUBIDA])
        if no_fundo and e.equilibrio is not None and abs(e.equilibrio) > L.equilibrio_maximo:
            e.alertas.append(DICAS[ERRO_EQUILIBRIO])
        if no_fundo and e.linha_pe is not None and e.linha_pe > L.linha_pe_maxima and not (
                e.razao_joelhos is not None and e.razao_joelhos < L.razao_joelhos_minima):
            e.alertas.append(DICAS[ERRO_LINHA_PE])
        if e.ombros is not None and e.ombros > L.ombros_maximo:
            e.alertas.append(DICAS[ERRO_OMBROS])
        if e.fase == SUBINDO and r.angulo_minimo_joelho > L.joelho_profundidade:
            e.alertas.append(DICAS[ERRO_PROFUNDIDADE])


# ---------------------------------------------------------------- formatos para a interface e o relatório
def _r(v, casas=1):
    return None if v is None else round(v, casas)


def dados_repeticao(r):
    """Medidas brutas de uma repetição (para o histórico e o relatório)."""
    return {
        "serie": r.serie, "numero": r.numero, "nota": r.nota, "notas": r.notas, "correta": r.correta,
        "erros": r.erros, "vista": r.vista,
        "angulo_minimo_joelho": _r(r.angulo_minimo_joelho),
        "angulo_minimo_quadril": _r(r.angulo_minimo_quadril),
        "tronco_maximo": _r(r.tronco_maximo),
        "alinhamento_maximo": _r(r.alinhamento_maximo),
        "calcanhar_maximo": _r(r.calcanhar_maximo, 3),
        "razao_joelhos_minima": _r(r.razao_joelhos_minima, 2),
        "assimetria_joelhos": _r(r.assimetria_joelhos),
        "desvio_quadril": _r(r.desvio_quadril, 2),
        "inclinacao_quadril": _r(r.inclinacao_quadril),
        "base": _r(r.base, 2),
        "subida_tronco": _r(r.subida_tronco),
        "equilibrio_maximo": _r(r.equilibrio_maximo, 2),
        "extensao_deficit": _r(r.extensao_deficit),
        "linha_pe_maxima": _r(r.linha_pe_maxima, 2),
        "ombros_maximo": _r(r.ombros_maximo),
        "velocidade_fundo": _r(r.velocidade_fundo, 0),
        "cabeca_maxima": _r(r.cabeca_maxima),
        "avisos": r.avisos,
        "duracao_s": r.duracao_s, "descida_s": r.descida_s,
    }


def medidas_formatadas(r):
    """Valor medido de cada critério, em texto curto, para mostrar ao lado da nota."""
    m = {"profundidade": f"joelho {r.angulo_minimo_joelho:.0f}°"}
    if r.tronco_maximo is not None:
        m["tronco"] = f"{r.tronco_maximo:.0f}° da vertical"
    if r.alinhamento_maximo is not None:
        m["alinhamento"] = f"{r.alinhamento_maximo:+.0f}° em relação à canela"
    if r.calcanhar_maximo is not None:
        m["calcanhar"] = "no chão" if r.calcanhar_maximo < 0.03 else f"subiu {100 * r.calcanhar_maximo:.0f}% da canela"
    if r.razao_joelhos_minima is not None:
        m["joelhos"] = f"abertura {100 * r.razao_joelhos_minima:.0f}%"
    if r.assimetria_joelhos is not None or r.desvio_quadril is not None:
        m["simetria"] = (f"quadril inclinado {r.inclinacao_quadril or 0:.0f}° · {100 * (r.desvio_quadril or 0):.0f}% fora do centro · "
                         f"{r.assimetria_joelhos or 0:.0f}° entre joelhos")
    if r.base is not None:
        m["base"] = f"pés a {r.base:.1f}× os ombros".replace(".", ",")
    if r.subida_tronco is not None:
        m["subida"] = f"tronco +{r.subida_tronco:.0f}° na subida"
    if r.equilibrio_maximo is not None:
        m["equilibrio"] = "sobre o meio do pé" if r.equilibrio_maximo < 0.3 else f"{r.equilibrio_maximo:.1f} pé fora do centro".replace(".", ",")
    if r.linha_pe_maxima is not None:
        m["linha_pe"] = f"desvio de {100 * r.linha_pe_maxima:.0f}% da base"
    if r.ombros_maximo is not None:
        m["ombros"] = f"inclinação de {r.ombros_maximo:.0f}°"
    if r.cabeca_maxima is not None:
        m["cabeca"] = f"{r.cabeca_maxima:.0f}° em relação ao tronco"
    if r.extensao_deficit is not None:
        m["extensao"] = "completa" if r.extensao_deficit < 6 else f"faltaram {r.extensao_deficit:.0f}°"
    if r.velocidade_fundo is not None:
        m["controle"] = f"{r.velocidade_fundo:.0f}°/s no fundo"
    if r.descida_s is not None:
        m["ritmo"] = f"descida em {r.descida_s:.1f} s".replace(".", ",")
    return m
