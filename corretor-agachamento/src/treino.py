"""Treino guiado: séries, repetições, contagem regressiva, descanso e mensagens de voz.

O tempo recebido em atualizar() é o relógio real (segundos desde o início, sem as pausas),
para que a contagem regressiva e o descanso durem o que mostram, mesmo analisando um vídeo.

Fases:  preparando -> executando -> descanso -> executando -> ... -> concluido
O treino recebe a cada frame o estado do analisador e decide a fase.
As mensagens de voz viram "eventos" numerados, que a interface web lê e fala.
"""
from collections import Counter
from dataclasses import dataclass

from .analisador_agachamento import AVISO_FADIGA, DICAS, classificar_nota, dados_repeticao, medidas_formatadas

PREPARANDO, EXECUTANDO, DESCANSO, CONCLUIDO = "preparando", "executando", "descanso", "concluido"
NUMEROS = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
           "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito",
           "dezenove", "vinte"]


def por_extenso(n):
    return NUMEROS[n] if 0 <= n < len(NUMEROS) else str(n)


@dataclass
class ConfigTreino:
    series: int = 3
    repeticoes: int = 10      # meta por série; 0 = modo livre (sem meta)
    descanso_s: int = 45
    contagem_s: int = 3       # contagem regressiva antes de cada série


class Treino:
    def __init__(self, analisador, config=None):
        self.analisador = analisador
        self.config = config or ConfigTreino()
        self.fase = PREPARANDO
        self.serie = 1
        self.eventos = []          # [{"id", "texto", "tipo"}]
        self._ultimo_alerta = {}   # alerta -> tempo em que foi falado
        self._contagem_inicio = None
        self._ultimo_numero = None
        self._fim_descanso = None
        self._reps_vistas = 0
        self._series_com_fadiga = set()
        self._inicio_serie_reps = 0
        self.restante_s = 0
        self.inicio_s = None
        self.fim_s = None
        self._evento("Prepare-se. Fique de corpo inteiro na frente da câmera.", "info")

    def frases_fixas(self):
        """Frases que o treino pode falar, para a voz natural gerar com antecedência."""
        from .analisador_agachamento import DICAS as D
        n = max(self.config.repeticoes, 20)
        frases = [por_extenso(i) for i in range(1, min(n, len(NUMEROS) - 1) + 1)]
        frases += list(D.values()) + ["Afaste-se para aparecer de corpo inteiro", "Vamos começar!",
                                      "Prepare-se. Fique de corpo inteiro na frente da câmera.",
                                      "Valendo! Pode começar.", "Próxima série.", "Treino encerrado."]
        for s in range(1, self.config.series + 1):
            frases.append(f"Série {por_extenso(s)}. {por_extenso(self.config.repeticoes)} repetições. Valendo!")
        if self.config.descanso_s:
            frases.append(f"Série concluída. Descanse {self.config.descanso_s} segundos.")
        return frases

    # ------------------------------------------------------------------ eventos (voz)
    def _evento(self, texto, tipo="info"):
        self.eventos.append({"id": len(self.eventos) + 1, "texto": texto, "tipo": tipo})

    def eventos_desde(self, ultimo_id):
        return [e for e in self.eventos if e["id"] > ultimo_id]

    # ------------------------------------------------------------------ propriedades
    @property
    def livre(self):
        return self.config.repeticoes <= 0

    @property
    def reps_na_serie(self):
        return len(self.analisador.repeticoes) - self._inicio_serie_reps

    @property
    def deve_analisar(self):
        """Durante a contagem e o descanso as repetições não são contadas."""
        return self.fase == EXECUTANDO

    # ------------------------------------------------------------------ ciclo
    def atualizar(self, estado, tempo_s):
        if self.fase == PREPARANDO:
            self._preparando(estado, tempo_s)
        elif self.fase == EXECUTANDO:
            self._executando(estado, tempo_s)
        elif self.fase == DESCANSO:
            self._descanso(tempo_s)

    def _preparando(self, estado, tempo_s):
        if not estado.pessoa_detectada:
            self._contagem_inicio, self._ultimo_numero = None, None
            self.restante_s = self.config.contagem_s
            return
        if self._contagem_inicio is None:
            self._contagem_inicio = tempo_s
            if self.serie == 1:
                self._evento("Vamos começar!", "info")
        restante = self.config.contagem_s - (tempo_s - self._contagem_inicio)
        numero = max(int(restante) + 1, 0) if restante > 0 else 0
        self.restante_s = max(restante, 0)
        if numero != self._ultimo_numero and numero > 0:
            self._evento(por_extenso(numero), "contagem")
        self._ultimo_numero = numero
        if restante <= 0:
            self._iniciar_serie(tempo_s)

    def _iniciar_serie(self, tempo_s):
        self.fase = EXECUTANDO
        if self.inicio_s is None:
            self.inicio_s = tempo_s
        self.analisador.reiniciar_movimento()
        self._inicio_serie_reps = len(self.analisador.repeticoes)
        self._reps_vistas = len(self.analisador.repeticoes)
        if self.livre:
            self._evento("Valendo! Pode começar.", "inicio")
        else:
            self._evento(f"Série {por_extenso(self.serie)}. "
                         f"{por_extenso(self.config.repeticoes)} repetições. Valendo!", "inicio")

    def _executando(self, estado, tempo_s):
        # Repetições novas
        reps = self.analisador.repeticoes
        while self._reps_vistas < len(reps):
            r = reps[self._reps_vistas]
            r.serie = self.serie
            self._reps_vistas += 1
            n = r.numero - self._inicio_serie_reps
            # o número e a dica vão em mensagens separadas: as frases fixas ficam em cache na voz natural
            self._evento(por_extenso(n), "rep_ok" if r.correta else "rep_erro")
            if not r.correta:
                self._evento(DICAS[r.erros[0]], "dica")
            if self._fadiga(r):
                self._evento(DICAS[AVISO_FADIGA], "aviso")

        # Alertas em tempo real (no máximo um a cada 4 s para não falar demais)
        for alerta in estado.alertas:
            if tempo_s - self._ultimo_alerta.get(alerta, -99) > 4:
                self._ultimo_alerta[alerta] = tempo_s
                self._evento(alerta, "alerta")
                break

        if not self.livre and self.reps_na_serie >= self.config.repeticoes:
            if self.serie >= self.config.series:
                self.concluir(tempo_s)
            elif self.config.descanso_s > 0:
                self.fase = DESCANSO
                self._fim_descanso = tempo_s + self.config.descanso_s
                self.restante_s = self.config.descanso_s
                self._evento(f"Série concluída. Descanse {self.config.descanso_s} segundos.", "descanso")
            else:
                self._proxima_serie(tempo_s)

    def _fadiga(self, r):
        """Sinal de fadiga: nas últimas repetições da série a nota ou a profundidade caem bastante
        em relação às primeiras. Avisa uma vez por série (é um aviso, não um erro da repetição)."""
        da_serie = [x for x in self.analisador.repeticoes if x.serie == self.serie]
        if len(da_serie) < 4 or self.serie in self._series_com_fadiga:
            return False
        inicio, fim = da_serie[:2], da_serie[-2:]
        queda_nota = sum(x.nota for x in inicio) / 2 - sum(x.nota for x in fim) / 2
        perda_profundidade = sum(x.angulo_minimo_joelho for x in fim) / 2 - sum(x.angulo_minimo_joelho for x in inicio) / 2
        if len({x.vista for x in inicio + fim}) > 1:
            # o ângulo do joelho medido de frente e de lado difere alguns graus: trocar a posição
            # da câmera no meio da série não é sinal de cansaço
            perda_profundidade = 0
        if queda_nota >= 20 or perda_profundidade >= 12:
            r.avisos.append(AVISO_FADIGA)
            self._series_com_fadiga.add(self.serie)
            return True
        return False

    def _descanso(self, tempo_s):
        self.restante_s = max(self._fim_descanso - tempo_s, 0)
        if self.restante_s <= 0:
            self._proxima_serie(tempo_s)

    def _proxima_serie(self, tempo_s):
        self.serie += 1
        self.fase = PREPARANDO
        self._contagem_inicio, self._ultimo_numero = None, None
        self._evento("Próxima série.", "info")

    def pular_descanso(self, tempo_s):
        if self.fase == DESCANSO:
            self._proxima_serie(tempo_s)

    def concluir(self, tempo_s):
        if self.fase == CONCLUIDO:
            return
        self.fase = CONCLUIDO
        self.fim_s = tempo_s
        r = self.resumo()
        if r["total"]:
            self._evento(f"Treino concluído! {r['percentual_acerto']} por cento de acerto. "
                         f"Nota média {r['nota_media']}.", "fim")
        else:
            self._evento("Treino encerrado.", "fim")

    # ------------------------------------------------------------------ resultados
    def resumo(self):
        reps = self.analisador.repeticoes
        total = len(reps)
        corretas = sum(r.correta for r in reps)
        erros = Counter(e for r in reps for e in r.erros)
        nota_media = round(sum(r.nota for r in reps) / total) if total else 0
        principal = erros.most_common(1)[0][0] if erros else None
        return {
            "series_planejadas": self.config.series if not self.livre else None,
            "repeticoes_meta": self.config.repeticoes if not self.livre else None,
            "series_feitas": max((r.serie for r in reps), default=0),
            "total": total,
            "corretas": corretas,
            "percentual_acerto": round(100 * corretas / total) if total else 0,
            "nota_media": nota_media,
            "classificacao": classificar_nota(nota_media) if total else "-",
            "melhor_nota": max((r.nota for r in reps), default=0),
            "duracao_s": round((self.fim_s or 0) - (self.inicio_s or 0)) if self.inicio_s is not None else 0,
            "erros": dict(erros.most_common()),
            "dica": DICAS[principal] if principal else "Ótima execução! Mantenha o padrão.",
            "series_com_fadiga": sorted(self._series_com_fadiga),
            "repeticoes": [{**dados_repeticao(r), "medidas": medidas_formatadas(r)} for r in reps],
        }
