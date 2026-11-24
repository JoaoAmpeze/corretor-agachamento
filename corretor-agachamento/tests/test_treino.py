import copy

from src.analisador_agachamento import AnalisadorAgachamento, Repeticao, classificar_nota
from src.treino import CONCLUIDO, DESCANSO, EXECUTANDO, PREPARANDO, ConfigTreino, Treino
from tests.sintetico import angulos_repeticao, pose_lateral

FPS = 30


class Simulador:
    """Alimenta analisador + treino frame a frame, como o app faz."""

    def __init__(self, config):
        self.analisador = AnalisadorAgachamento()
        self.treino = Treino(self.analisador, config)
        self.t = 0.0

    def frame(self, pose):
        self.t += 1 / FPS
        estado = self.analisador.processar(pose, self.t)
        if not self.treino.deve_analisar:
            self.analisador.reiniciar_movimento()
        self.treino.atualizar(estado, self.t)
        return copy.deepcopy(estado)

    def parado(self, segundos):
        for _ in range(int(segundos * FPS)):
            self.frame(pose_lateral(172, 20))

    def rep(self, minimo=85, tronco=30):
        for ang in angulos_repeticao(minimo):
            self.frame(pose_lateral(ang, tronco))
        self.parado(0.2)


# ---------------------------------------------------------------- nota
def test_nota_repeticao_perfeita_e_com_erro():
    boa = Repeticao(1, angulo_minimo_joelho=88, tronco_maximo=30, duracao_s=2.0)
    assert boa.calcular_nota() == 100
    rasa = Repeticao(1, angulo_minimo_joelho=120, tronco_maximo=30, duracao_s=2.0)
    assert rasa.calcular_nota() < 60
    assert classificar_nota(boa.nota) == "Excelente"


def test_ritmo_rapido_reduz_nota_sem_virar_erro():
    rapida = Repeticao(1, angulo_minimo_joelho=88, tronco_maximo=30, duracao_s=0.5)
    rapida.calcular_nota()
    assert rapida.correta and 75 < rapida.nota < 100


# ---------------------------------------------------------------- treino guiado
def test_contagem_regressiva_espera_a_pessoa():
    s = Simulador(ConfigTreino(series=1, repeticoes=2, descanso_s=0, contagem_s=3))
    for _ in range(60):
        s.frame(None)
    assert s.treino.fase == PREPARANDO
    s.parado(3.2)
    assert s.treino.fase == EXECUTANDO
    assert any(e["texto"] == "três" for e in s.treino.eventos)


def test_series_descanso_e_conclusao():
    s = Simulador(ConfigTreino(series=2, repeticoes=2, descanso_s=8, contagem_s=1))
    s.parado(1.2)
    s.rep(); s.rep()
    assert s.treino.fase == DESCANSO
    # agachamentos feitos durante o descanso não contam
    s.rep()
    assert len(s.analisador.repeticoes) == 2
    s.parado(6)  # descanso de 8 s = ~2,3 s da repetição acima + 6 s parado
    assert s.treino.fase == PREPARANDO and s.treino.serie == 2
    s.parado(1.2)
    s.rep(); s.rep(minimo=125)
    assert s.treino.fase == CONCLUIDO
    r = s.treino.resumo()
    assert r["total"] == 4 and r["corretas"] == 3 and r["percentual_acerto"] == 75
    assert r["series_feitas"] == 2
    assert [x["serie"] for x in r["repeticoes"]] == [1, 1, 2, 2]
    assert "Desça" in r["dica"]
    assert s.treino.eventos[-1]["tipo"] == "fim"


def test_eventos_de_voz_por_repeticao():
    s = Simulador(ConfigTreino(series=1, repeticoes=0, contagem_s=0))
    s.parado(0.2)
    s.rep()
    s.rep(tronco=65)
    tipos = [e["tipo"] for e in s.treino.eventos]
    assert "rep_ok" in tipos and "rep_erro" in tipos and "dica" in tipos and "alerta" in tipos
    assert s.treino.eventos_desde(len(s.treino.eventos)) == []


def test_pular_descanso():
    s = Simulador(ConfigTreino(series=2, repeticoes=1, descanso_s=60, contagem_s=0))
    s.parado(0.2)
    s.rep()
    assert s.treino.fase == DESCANSO
    s.treino.pular_descanso(s.t)
    assert s.treino.fase == PREPARANDO and s.treino.serie == 2


def test_aviso_de_fadiga_na_serie():
    s = Simulador(ConfigTreino(series=1, repeticoes=0, contagem_s=0))
    s.parado(0.3)
    s.rep(84); s.rep(86); s.rep(105); s.rep(115)  # profundidade caindo ao longo da série
    assert any(e["tipo"] == "aviso" for e in s.treino.eventos)
    assert s.treino.resumo()["series_com_fadiga"] == [1]
    assert "Sinal de fadiga" in s.analisador.repeticoes[-1].avisos


def test_sem_fadiga_quando_a_tecnica_se_mantem():
    s = Simulador(ConfigTreino(series=1, repeticoes=0, contagem_s=0))
    s.parado(0.3)
    for _ in range(5):
        s.rep(85)
    assert s.treino.resumo()["series_com_fadiga"] == []


def test_trocar_a_camera_de_posicao_nao_e_fadiga():
    # de frente o joelho mede alguns graus a mais que de lado: não é perda de profundidade
    an = AnalisadorAgachamento()
    treino = Treino(an, ConfigTreino(series=1, repeticoes=0, contagem_s=0))
    for i, (ang, vista) in enumerate([(84, "lateral"), (86, "lateral"), (97, "frontal"), (98, "frontal")]):
        r = Repeticao(i + 1, angulo_minimo_joelho=ang, tronco_maximo=30, duracao_s=2.0)
        r.vista, r.serie = vista, 1
        r.calcular_nota()
        an.repeticoes.append(r)
    assert not treino._fadiga(an.repeticoes[-1])
