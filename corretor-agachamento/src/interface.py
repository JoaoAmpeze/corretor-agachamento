"""Desenho dos resultados sobre o vídeo: esqueleto, painel de informações e alertas."""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .analisador_agachamento import DESCENDO, SUBINDO
from .detector_pose import CONEXOES

VERDE = (88, 209, 48)      # verde Apple (#30d158), em BGR
VERMELHO = (58, 69, 255)   # vermelho Apple (#ff453a)
AMARELO = (10, 214, 255)   # amarelo Apple (#ffd60a)
BRANCO = (255, 255, 255)
CINZA = (40, 40, 40)
ESCURO = (28, 28, 30)


def _carregar_fonte(tamanho):
    # Fontes com acentos; tenta as mais comuns no Windows, Linux e macOS
    for nome in ("arial.ttf", "Arial.ttf", "segoeui.ttf", "DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def _caixa(pontos, forma, margem):
    """Retângulo (x0, y0, x1, y1) que envolve os pontos, com margem e recortado aos limites da imagem."""
    h, w = forma[:2]
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    x0, y0 = max(min(xs) - margem, 0), max(min(ys) - margem, 0)
    x1, y1 = min(max(xs) + margem + 1, w), min(max(ys) + margem + 1, h)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


class Interface:
    def __init__(self, lado_menor_frame):
        """lado_menor_frame: o menor lado do vídeo (altura num vídeo deitado, largura num vídeo em pé)."""
        escala = max(lado_menor_frame / 720, 0.6)
        self.lado_menor = lado_menor_frame
        self.escala = escala
        self.fonte = _carregar_fonte(int(22 * escala))
        self.fonte_grande = _carregar_fonte(int(34 * escala))
        self.fonte_alerta = _carregar_fonte(int(28 * escala))

    # ------------------------------------------------------------------ esqueleto
    def desenhar_esqueleto(self, frame, pose, estado):
        """Desenha o corpo inteiro fino e translúcido e destaca as articulações avaliadas.
        Verde = dentro do padrão, vermelho = erro naquele momento.
        De lado: tronco, quadril, joelho, tornozelo, calcanhar e ponta do pé, com as referências verticais.
        De frente: as duas pernas e os pés, a linha quadril → pé (onde o joelho deveria passar)
        e o centro do quadril em relação ao centro dos pés."""
        if pose is None:
            return
        s = self.escala
        pts = {n: (int(x), int(y)) for n, (x, y) in pose.imagem.items()}
        frontal = estado.vista == "frontal"
        lado = estado.lado
        alertas = " ".join(estado.alertas).lower()
        erro = {"tronco": "peito" in alertas, "calcanhar": "calcanhares" in alertas,
                "joelhos": "joelhos para fora" in alertas, "simetria": "duas pernas" in alertas,
                "equilibrio": "meio do pé" in alertas, "ombros": "ombros nivelados" in alertas,
                "linha_pe": "ponta do pé" in alertas}
        cor = lambda chave: VERMELHO if erro[chave] else VERDE

        # 1) corpo inteiro: linhas finas e translúcidas, só para referência
        #    (a mistura é feita só no retângulo em volta do corpo, não na imagem inteira: bem mais rápido)
        linhas = [(pts[a], pts[b]) for a, b in CONEXOES if a in pts and b in pts and pose.visivel(a, b, minimo=0.3)]
        if linhas:
            esp = max(2, int(2.5 * s))
            caixa = _caixa([p for l in linhas for p in l], frame.shape, margem=esp + 2)
            if caixa:
                x0, y0, x1, y1 = caixa
                roi = frame[y0:y1, x0:x1]
                camada = roi.copy()
                for a, b in linhas:
                    cv2.line(camada, (a[0] - x0, a[1] - y0), (b[0] - x0, b[1] - y0), BRANCO, esp, cv2.LINE_AA)
                cv2.addWeighted(camada, 0.45, roi, 0.55, 0, roi)

        # 2) segmentos avaliados
        segs = []
        if frontal:
            for l in ("esq", "dir"):
                segs += [(f"quadril_{l}", f"joelho_{l}", cor("joelhos")), (f"joelho_{l}", f"tornozelo_{l}", cor("joelhos")),
                         (f"tornozelo_{l}", f"pe_{l}", VERDE)]
            segs += [("quadril_esq", "quadril_dir", cor("simetria")), ("ombro_esq", "ombro_dir", cor("ombros"))]
            # onde o joelho deveria passar: linha do quadril até a ponta do pé
            for l in ("esq", "dir"):
                if pose.visivel(f"pe_{l}", minimo=0.3):
                    self._tracejado(frame, pts[f"quadril_{l}"], pts[f"pe_{l}"], VERMELHO if erro["linha_pe"] else BRANCO,
                                    max(1, int(2 * s)))
            # centro do quadril x centro dos pés
            cq = ((pts["quadril_esq"][0] + pts["quadril_dir"][0]) // 2, (pts["quadril_esq"][1] + pts["quadril_dir"][1]) // 2)
            cp = ((pts["tornozelo_esq"][0] + pts["tornozelo_dir"][0]) // 2, (pts["tornozelo_esq"][1] + pts["tornozelo_dir"][1]) // 2)
            self._tracejado(frame, cq, (cq[0], cp[1]), AMARELO if not erro["simetria"] else VERMELHO, max(1, int(2 * s)))
            cv2.circle(frame, cp, max(4, int(6 * s)), BRANCO, -1, cv2.LINE_AA)
        elif estado.vista == "diagonal":
            # câmera na diagonal: só o que é medido em 3D (pernas e tronco)
            for l in ("esq", "dir"):
                segs += [(f"quadril_{l}", f"joelho_{l}", VERDE), (f"joelho_{l}", f"tornozelo_{l}", VERDE)]
            segs.append((f"ombro_{lado}", f"quadril_{lado}", cor("tronco")))
        else:
            segs += [(f"ombro_{lado}", f"quadril_{lado}", cor("tronco")),
                     (f"quadril_{lado}", f"joelho_{lado}", VERDE), (f"joelho_{lado}", f"tornozelo_{lado}", VERDE),
                     (f"tornozelo_{lado}", f"calcanhar_{lado}", cor("calcanhar")),
                     (f"calcanhar_{lado}", f"pe_{lado}", cor("calcanhar")), (f"tornozelo_{lado}", f"pe_{lado}", cor("calcanhar"))]
            if pose.visivel(f"orelha_{lado}", minimo=0.3):
                segs.append((f"orelha_{lado}", f"ombro_{lado}", VERDE))
            # equilíbrio: linha vertical a partir do meio do pé e o ponto do meio do tronco
            if pose.visivel(f"calcanhar_{lado}", f"pe_{lado}", minimo=0.3):
                c, p_ = pts[f"calcanhar_{lado}"], pts[f"pe_{lado}"]
                meio_pe = ((c[0] + p_[0]) // 2, max(c[1], p_[1]))
                meio_tronco = ((pts[f"ombro_{lado}"][0] + pts[f"quadril_{lado}"][0]) // 2,
                               (pts[f"ombro_{lado}"][1] + pts[f"quadril_{lado}"][1]) // 2)
                cor_eq = VERMELHO if erro["equilibrio"] else AMARELO
                self._tracejado(frame, meio_pe, (meio_pe[0], meio_tronco[1]), cor_eq, max(1, int(2 * s)), traco=6)
                cv2.circle(frame, meio_tronco, max(4, int(6 * s)), cor_eq, -1, cv2.LINE_AA)
                cv2.circle(frame, meio_tronco, max(4, int(6 * s)), ESCURO, max(1, int(2 * s)), cv2.LINE_AA)
        segs = [(a, b, c) for a, b, c in segs if pose.visivel(a, b, minimo=0.3)]
        grosso = max(4, int(7 * s))
        for a, b, _ in segs:
            cv2.line(frame, pts[a], pts[b], ESCURO, grosso + max(3, int(4 * s)), cv2.LINE_AA)
        for a, b, c in segs:
            cv2.line(frame, pts[a], pts[b], c, grosso, cv2.LINE_AA)
        for n in {p for a, b, _ in segs for p in (a, b)}:
            r = max(4, int((5 if n.startswith(("calcanhar", "pe", "orelha")) else 7) * s))
            cv2.circle(frame, pts[n], r, BRANCO, -1, cv2.LINE_AA)
            cv2.circle(frame, pts[n], r, ESCURO, max(1, int(2 * s)), cv2.LINE_AA)

        # 3) referências e ângulos
        if estado.vista == "diagonal":
            if estado.angulo_joelho is not None:
                self._etiqueta(frame, f"{estado.angulo_joelho:.0f}", pts[f"joelho_{lado}"], AMARELO if estado.angulo_joelho > 100 else VERDE)
            if estado.inclinacao_tronco is not None:
                q, o = pts[f"quadril_{lado}"], pts[f"ombro_{lado}"]
                self._etiqueta(frame, f"{estado.inclinacao_tronco:.0f}", ((o[0] + q[0]) // 2, (o[1] + q[1]) // 2), cor("tronco"))
        elif frontal:
            for l in ("esq", "dir"):
                ang = self._angulo_lado(pose, l)
                if ang is not None:
                    # a etiqueta do joelho mais à esquerda vai para a esquerda, a outra para a direita
                    mais_a_esquerda = pts[f"joelho_{l}"][0] <= min(pts["joelho_esq"][0], pts["joelho_dir"][0])
                    self._etiqueta(frame, f"{ang:.0f}", pts[f"joelho_{l}"], AMARELO if ang > 100 else VERDE,
                                   esquerda=mais_a_esquerda)
        else:
            q, o, t, j = pts[f"quadril_{lado}"], pts[f"ombro_{lado}"], pts[f"tornozelo_{lado}"], pts[f"joelho_{lado}"]
            if estado.inclinacao_tronco is not None:
                comp = int(np.hypot(o[0] - q[0], o[1] - q[1]))
                self._tracejado(frame, q, (q[0], q[1] - comp), BRANCO, max(1, int(2 * s)))
                self._etiqueta(frame, f"{estado.inclinacao_tronco:.0f}", ((o[0] + q[0]) // 2, (o[1] + q[1]) // 2), cor("tronco"))
            if estado.inclinacao_canela is not None:  # vertical a partir do tornozelo: inclinação da canela
                comp = int(np.hypot(j[0] - t[0], j[1] - t[1]))
                self._tracejado(frame, t, (t[0], t[1] - comp), BRANCO, max(1, int(2 * s)))
            if estado.angulo_quadril is not None:
                self._etiqueta(frame, f"{estado.angulo_quadril:.0f}", q, BRANCO, esquerda=True)
            if estado.angulo_joelho is not None:
                self._etiqueta(frame, f"{estado.angulo_joelho:.0f}", j, AMARELO if estado.angulo_joelho > 100 else VERDE)

    @staticmethod
    def _angulo_lado(pose, l):
        from .geometria import angulo_entre_pontos
        m = pose.mundo
        if not all(k in m for k in (f"quadril_{l}", f"joelho_{l}", f"tornozelo_{l}")):
            return None
        return angulo_entre_pontos(m[f"quadril_{l}"], m[f"joelho_{l}"], m[f"tornozelo_{l}"])

    def _tracejado(self, frame, a, b, cor, espessura, traco=10):
        comp = max(int(np.hypot(b[0] - a[0], b[1] - a[1])), 1)
        passo = max(int(traco * self.escala), 4)
        for i in range(0, comp, passo * 2):
            p1 = (int(a[0] + (b[0] - a[0]) * i / comp), int(a[1] + (b[1] - a[1]) * i / comp))
            f = min(i + passo, comp) / comp
            p2 = (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f))
            cv2.line(frame, p1, p2, cor, espessura, cv2.LINE_AA)

    def _etiqueta(self, frame, texto, ponto, cor_destaque, esquerda=False):
        """Pílula escura com um ponto colorido e o valor em graus, ao lado do ponto indicado."""
        s = self.escala
        fonte, esc, esp = cv2.FONT_HERSHEY_DUPLEX, 0.95 * s, max(1, int(2 * s))
        (tw, th), _ = cv2.getTextSize(texto, fonte, esc, esp)
        pad, bola, grau = int(10 * s), int(5 * s), int(4 * s)
        largura = pad + bola * 2 + int(8 * s) + tw + grau * 2 + pad
        altura = th + pad * 2
        h, w = frame.shape[:2]
        x = ponto[0] - largura - int(18 * s) if esquerda else ponto[0] + int(18 * s)
        x = min(max(x, 0), w - largura - 1)
        y = min(max(ponto[1] - altura // 2, 0), h - altura - 1)
        r = altura // 2
        # só o pedaço da pílula (com 2 px de folga para a suavização), não a imagem inteira
        x0, y0 = max(x - 2, 0), max(y - 2, 0)
        roi = frame[y0:y + altura + 3, x0:x + largura + 3]
        camada = roi.copy()
        dx, dy = x - x0, y - y0
        cv2.rectangle(camada, (dx + r, dy), (dx + largura - r, dy + altura), ESCURO, -1)
        cv2.circle(camada, (dx + r, dy + r), r, ESCURO, -1, cv2.LINE_AA)
        cv2.circle(camada, (dx + largura - r, dy + r), r, ESCURO, -1, cv2.LINE_AA)
        cv2.addWeighted(camada, 0.82, roi, 0.18, 0, roi)
        cx = x + pad + bola
        cv2.circle(frame, (cx, y + r), bola, cor_destaque, -1, cv2.LINE_AA)
        tx = cx + bola + int(8 * s)
        cv2.putText(frame, texto, (tx, y + r + th // 2), fonte, esc, BRANCO, esp, cv2.LINE_AA)
        cv2.circle(frame, (tx + tw + grau + 1, y + r - th // 2 + grau), grau, BRANCO, max(1, int(1.5 * s)), cv2.LINE_AA)

    # ------------------------------------------------------------------ painel
    def desenhar_painel(self, frame, estado, fps=None, pausado=False):
        h, w = frame.shape[:2]
        s = self.escala
        largura_painel = int(330 * s)

        # Fundos semitransparentes (painel à esquerda e faixa de alerta embaixo),
        # misturados só nos retângulos, sem copiar a imagem inteira
        altura_painel = int((12 + 44 + 38 + (5 if fps else 4) * 30 + 12) * s)
        texto_faixa, cor_faixa = self._mensagem_faixa(estado)
        retangulos = [((0, 0), (largura_painel, altura_painel), CINZA)]
        if texto_faixa:
            retangulos.append(((0, h - int(70 * s)), (w, h), cor_faixa))
        for (x0, y0), (x1, y1), cor in retangulos:
            roi = frame[max(y0, 0):min(y1 + 1, h), max(x0, 0):min(x1 + 1, w)]
            cv2.addWeighted(np.full_like(roi, cor), 0.65, roi, 0.35, 0, roi)

        # Barra de profundidade (quanto mais cheia, mais fundo o agachamento)
        if estado.angulo_joelho is not None:
            self._barra_profundidade(frame, estado.angulo_joelho)

        # Textos (via PIL para aceitar acentos)
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(img)
        x, y, lh = int(16 * s), int(12 * s), int(30 * s)
        d.text((x, y), f"Repetições: {estado.total}", font=self.fonte_grande, fill=(255, 255, 255))
        y += int(44 * s)
        d.text((x, y), f"Corretas: {estado.corretas}   Com erro: {estado.total - estado.corretas}",
               font=self.fonte, fill=(170, 230, 180))
        y += lh + int(8 * s)
        linhas = [
            f"Fase: {estado.fase}",
            f"Joelho: {self._fmt(estado.angulo_joelho, '°')}",
            f"Tronco: {self._fmt(estado.inclinacao_tronco, '°')}" if estado.vista == "lateral"
            else f"Abertura joelhos: {self._fmt(estado.razao_joelhos, '', 2)}",
            f"Vista: {estado.vista}",
        ]
        if fps:
            linhas.append(f"FPS: {fps:.0f}")
        for linha in linhas:
            d.text((x, y), linha, font=self.fonte, fill=(235, 235, 235))
            y += lh
        if pausado:
            d.text((w // 2 - int(60 * s), int(20 * s)), "PAUSADO", font=self.fonte_grande, fill=(255, 220, 0))
        if texto_faixa:
            d.text((int(20 * s), h - int(55 * s)), texto_faixa, font=self.fonte_alerta, fill=(255, 255, 255))
        frame[:] = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    def _barra_profundidade(self, frame, angulo):
        h, w = frame.shape[:2]
        s = self.escala
        x0, x1 = w - int(50 * s), w - int(20 * s)
        y0, y1 = int(80 * s), h - int(120 * s)
        # 170° (em pé) = vazia; 90° (coxa paralela) = cheia
        frac = float(np.clip((170 - angulo) / 80, 0, 1))
        cor = VERDE if angulo <= 100 else AMARELO
        cv2.rectangle(frame, (x0, y0), (x1, y1), BRANCO, 2)
        cv2.rectangle(frame, (x0 + 3, int(y1 - frac * (y1 - y0))), (x1 - 3, y1 - 3), cor, -1)
        alvo = int(y1 - (70 / 80) * (y1 - y0))  # linha do alvo (100°)
        cv2.line(frame, (x0 - 8, alvo), (x1 + 8, alvo), BRANCO, 2)

    def _mensagem_faixa(self, estado):
        if estado.alertas:
            return estado.alertas[0], VERMELHO
        if estado.fase in (DESCENDO, SUBINDO):
            return "", None
        r = estado.ultima
        if r is None:
            return "Posicione-se e comece o agachamento", (120, 90, 40)
        if r.correta:
            return f"Repetição {r.numero}: correta!", (60, 150, 60)
        return f"Repetição {r.numero}: {', '.join(r.erros).lower()}", (40, 110, 220)

    @staticmethod
    def _fmt(valor, sufixo, casas=0):
        return "-" if valor is None else f"{valor:.{casas}f}{sufixo}"

