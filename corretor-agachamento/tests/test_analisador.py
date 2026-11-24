import math
import random

from src.analisador_agachamento import (ERRO_JOELHO, ERRO_PROFUNDIDADE, ERRO_TRONCO,
                                        AnalisadorAgachamento)
from src.geometria import angulo_com_vertical, angulo_entre_pontos
from src.relatorio import resumo_texto, salvar_csv
from tests.sintetico import angulos_repeticao, pose_frontal, pose_lateral

FPS = 30


def rodar(analisador, poses, t0=0.0):
    """Processa as poses e devolve uma cópia do estado de cada frame."""
    import copy
    estados = []
    for i, pose in enumerate(poses):
        estados.append(copy.deepcopy(analisador.processar(pose, t0 + i / FPS)))
    return estados


# ---------------------------------------------------------------- geometria
def test_angulos_basicos():
    assert math.isclose(angulo_entre_pontos((0, 1), (0, 0), (1, 0)), 90, abs_tol=1e-6)
    assert math.isclose(angulo_entre_pontos((0, 1), (0, 0), (0, -1)), 180, abs_tol=1e-6)
    assert math.isclose(angulo_com_vertical((0, -1), (0, 0)), 0, abs_tol=1e-6)
    assert math.isclose(angulo_com_vertical((1, -1), (0, 0)), 45, abs_tol=1e-6)


def test_gerador_sintetico_produz_angulo_pedido():
    p = pose_lateral(90)
    ang = angulo_entre_pontos(p.mundo["quadril_esq"], p.mundo["joelho_esq"], p.mundo["tornozelo_esq"])
    assert math.isclose(ang, 90, abs_tol=0.5)


# ---------------------------------------------------------------- vista lateral
def test_conta_repeticoes_corretas():
    a = AnalisadorAgachamento()
    poses = [pose_lateral(ang, 30) for _ in range(3) for ang in angulos_repeticao(85)]
    estado = rodar(a, poses)[-1]
    assert estado.vista == "lateral"
    assert estado.total == 3 and estado.corretas == 3


def test_agachamento_raso():
    a = AnalisadorAgachamento()
    estado = rodar(a, [pose_lateral(ang, 30) for ang in angulos_repeticao(125)])[-1]
    assert estado.total == 1
    assert a.repeticoes[0].erros == [ERRO_PROFUNDIDADE]


def test_tronco_inclinado_gera_alerta_e_erro():
    a = AnalisadorAgachamento()
    estados = rodar(a, [pose_lateral(ang, 65) for ang in angulos_repeticao(85)])
    assert any("tronco" in alerta for e in estados for alerta in e.alertas)
    # inclinar muito o tronco também joga o peso para a frente do pé: os dois erros aparecem
    assert a.repeticoes[0].erros[0] == ERRO_TRONCO


def test_ruido_perto_do_limite_nao_cria_repeticoes_falsas():
    random.seed(1)
    a = AnalisadorAgachamento()
    poses = [pose_lateral(170 + random.uniform(-4, 4), 20) for _ in range(200)]
    assert rodar(a, poses)[-1].total == 0


# ---------------------------------------------------------------- vista frontal
def test_joelhos_para_dentro_na_vista_frontal():
    a = AnalisadorAgachamento()
    poses = []
    for ang in angulos_repeticao(88):
        fundo = ang < 130  # joelhos "fecham" na parte de baixo do movimento
        poses.append(pose_frontal(ang, razao_joelhos=0.55 if fundo else 1.0))
    estado = rodar(a, poses)[-1]
    assert estado.vista == "frontal"
    assert ERRO_JOELHO in a.repeticoes[0].erros


def test_vista_frontal_correta():
    a = AnalisadorAgachamento()
    estado = rodar(a, [pose_frontal(ang, 1.05) for ang in angulos_repeticao(88)])[-1]
    assert estado.total == 1 and estado.corretas == 1


# ---------------------------------------------------------------- outros
def test_sem_pessoa():
    estado = AnalisadorAgachamento().processar(None, 0.0)
    assert not estado.pessoa_detectada and estado.alertas


def test_zerar():
    a = AnalisadorAgachamento()
    rodar(a, [pose_lateral(ang) for ang in angulos_repeticao(85)])
    a.zerar()
    assert a.repeticoes == []


def test_relatorio(tmp_path):
    a = AnalisadorAgachamento()
    rodar(a, [pose_lateral(ang, 30) for ang in angulos_repeticao(85)]
          + [pose_lateral(ang, 30) for ang in angulos_repeticao(125)])
    caminho = salvar_csv(a.repeticoes, str(tmp_path / "s.csv"))
    linhas = open(caminho, encoding="utf-8-sig").read().strip().splitlines()
    assert len(linhas) == 3
    assert "Corretas: 1 (50%)" in resumo_texto(a.repeticoes)


# ---------------------------------------------------------------- contagem adaptativa
def test_conta_mesmo_sem_esticar_totalmente_a_perna():
    """Na prática o joelho 'em pé' costuma medir 150–165°. Cada repetição precisa contar."""
    a = AnalisadorAgachamento()
    poses = [pose_lateral(168, 30)] * 10
    for _ in range(4):
        poses += [pose_lateral(ang, 30) for ang in angulos_repeticao(85, em_pe=152)]
    estados = rodar(a, poses)
    totais = [e.total for e in estados]
    assert totais[-1] == 4
    # conta uma a uma, durante o movimento (não tudo de uma vez no fim)
    assert sorted(set(totais)) == [0, 1, 2, 3, 4]


def test_movimento_pequeno_nao_conta():
    a = AnalisadorAgachamento()
    poses = [pose_lateral(ang, 20) for ang in angulos_repeticao(150)]  # só 22° de amplitude
    assert rodar(a, poses)[-1].total == 0


def test_lado_nao_fica_trocando():
    a = AnalisadorAgachamento()
    p1, p2 = pose_lateral(170), pose_lateral(170)
    p2.visibilidade.update({k: 0.7 for k in p2.visibilidade if k.endswith("_dir")})
    p2.visibilidade.update({k: 0.65 for k in p2.visibilidade if k.endswith("_esq")})
    a.processar(p1, 0.0)
    assert a.processar(p2, 0.1).lado == "esq"  # diferença pequena: mantém o lado


# ---------------------------------------------------------------- critérios detalhados
from src.analisador_agachamento import ERRO_ALINHAMENTO, ERRO_BASE, ERRO_CALCANHAR, ERRO_SIMETRIA  # noqa: E402


def _rep_lateral(**kw):
    a = AnalisadorAgachamento()
    poses = [pose_lateral(172, 20)] * 15
    poses += [pose_lateral(ang, kw.get("tronco", 30), kw.get("calcanhar", 0.0) if ang < 140 else 0.0,
                           kw.get("canela") if ang < 140 else None)
              for ang in angulos_repeticao(kw.get("minimo", 85))]
    rodar(a, poses)
    return a.repeticoes[0]


def _rep_frontal(**kw):
    a = AnalisadorAgachamento()
    rodar(a, [pose_frontal(ang, **kw) for ang in angulos_repeticao(88)])
    return a.repeticoes[0]


def test_lateral_mede_todas_as_articulacoes():
    r = _rep_lateral()
    assert r.correta
    assert set(r.notas) == {"profundidade", "tronco", "alinhamento", "calcanhar", "subida", "equilibrio",
                            "extensao", "controle", "ritmo"}
    assert r.angulo_minimo_quadril is not None and r.descida_s > 0


def test_calcanhar_saindo_do_chao():
    r = _rep_lateral(calcanhar=0.15)
    assert ERRO_CALCANHAR in r.erros


def test_tronco_desalinhado_da_canela():
    # canela quase em pé (20°) e tronco a 49°: passa do limite relativo (25°), não do absoluto (50°)
    r = _rep_lateral(tronco=49, canela=20)
    assert ERRO_ALINHAMENTO in r.erros and ERRO_TRONCO not in r.erros


def test_frontal_correto_mede_simetria_e_base():
    r = _rep_frontal()
    assert r.correta
    assert {"joelhos", "simetria", "base"} <= set(r.notas)


def test_assimetria_entre_as_pernas():
    assert ERRO_SIMETRIA in _rep_frontal(assimetria=28).erros
    assert ERRO_SIMETRIA in _rep_frontal(desvio=0.3).erros


def test_base_dos_pes():
    assert ERRO_BASE in _rep_frontal(base=0.6).erros
    assert ERRO_BASE in _rep_frontal(base=2.4).erros


# ---------------------------------------------------------------- critérios de prevenção de lesão
from src.analisador_agachamento import (ERRO_CABECA, ERRO_EQUILIBRIO, ERRO_EXTENSAO, ERRO_LINHA_PE,  # noqa: E402
                                        ERRO_OMBROS, ERRO_QUIQUE, ERRO_SUBIDA)


def test_quadril_subindo_antes_do_peito():
    a = AnalisadorAgachamento()
    descida = [pose_lateral(ang, 30) for ang in angulos_repeticao(85)[:31]]
    # na subida o tronco deita até 48° antes de voltar (o quadril sobe primeiro)
    subida = [pose_lateral(ang, 30 + 25 * min(i / 10, 1) * (1 - i / 30)) for i, ang in enumerate(angulos_repeticao(85)[31:])]
    rodar(a, [pose_lateral(172, 20)] * 10 + descida + subida)
    assert ERRO_SUBIDA in a.repeticoes[0].erros


def test_peso_fora_do_meio_do_pe():
    a = AnalisadorAgachamento()
    rodar(a, [pose_lateral(172, 20, pe_x=-0.2)] * 10 + [pose_lateral(ang, 30, pe_x=-0.2) for ang in angulos_repeticao(85)])
    assert ERRO_EQUILIBRIO in a.repeticoes[0].erros


def test_cabeca_desalinhada():
    a = AnalisadorAgachamento()
    rodar(a, [pose_lateral(ang, 30, cabeca=70 if ang < 140 else 0) for ang in angulos_repeticao(85)])
    assert ERRO_CABECA in a.repeticoes[0].erros
    b = AnalisadorAgachamento()
    rodar(b, [pose_lateral(ang, 30, cabeca=10) for ang in angulos_repeticao(85)])
    assert b.repeticoes[0].correta


def test_sem_extensao_completa_entre_repeticoes():
    a = AnalisadorAgachamento()
    poses = [pose_lateral(172, 20)] * 15 + [pose_lateral(ang, 30) for ang in angulos_repeticao(85)]
    poses += [pose_lateral(ang, 30) for ang in angulos_repeticao(85, em_pe=148)]  # volta só até 148°
    poses += [pose_lateral(ang, 30) for ang in angulos_repeticao(85, em_pe=148)]
    rodar(a, poses)
    assert ERRO_EXTENSAO not in a.repeticoes[0].erros
    assert ERRO_EXTENSAO in a.repeticoes[-1].erros


def test_quique_no_fundo():
    a = AnalisadorAgachamento()
    rodar(a, [pose_lateral(172, 20)] * 10 + [pose_lateral(ang, 30) for ang in angulos_repeticao(85, frames=9)])
    assert ERRO_QUIQUE in a.repeticoes[0].erros
    b = AnalisadorAgachamento()
    rodar(b, [pose_lateral(172, 20)] * 10 + [pose_lateral(ang, 30) for ang in angulos_repeticao(85, frames=40)])
    assert ERRO_QUIQUE not in b.repeticoes[0].erros


def test_joelho_fora_da_linha_do_pe_em_uma_perna():
    r = _rep_frontal(razao_dir=0.55)  # só o joelho direito entra; a média dos dois ainda passa
    assert ERRO_LINHA_PE in r.erros


def test_ombros_desnivelados():
    assert ERRO_OMBROS in _rep_frontal(ombros=14).erros
    assert ERRO_OMBROS not in _rep_frontal(ombros=2).erros


# ---------------------------------------------------------------- posição da câmera
def test_detecta_vista_lateral_frontal_e_diagonal():
    a = AnalisadorAgachamento()
    assert a.processar(pose_lateral(170), 0).vista == "lateral"
    b = AnalisadorAgachamento()
    assert b.processar(pose_frontal(170), 0).vista == "frontal"
    c = AnalisadorAgachamento()
    assert c.processar(pose_frontal(170, giro=45), 0).vista == "diagonal"


def test_diagonal_avalia_so_criterios_3d():
    # na diagonal a imagem distorce quadril, ombros e pés: esses critérios não podem gerar erro
    a = AnalisadorAgachamento()
    rodar(a, [pose_frontal(ang, giro=45, desvio=0.4, ombros=15) for ang in angulos_repeticao(88)])
    r = a.repeticoes[0]
    assert r.vista == "diagonal" and r.correta
    assert {"profundidade", "tronco", "subida", "extensao", "controle", "ritmo"} == set(r.notas)


def test_joelho_para_fora_da_linha_nao_e_erro():
    r = _rep_frontal(razao_joelhos=1.35)  # joelhos abertos, acompanhando os pés
    assert r.correta


# ---------------------------------------------------------------- robustez com vídeo real
def test_extensao_tem_referencia_por_posicao_de_camera():
    # de lado o joelho em pé mede ~172°; de frente o modelo estima ~158°. Mudar de lado para frente
    # não pode virar erro de "não estendeu".
    a = AnalisadorAgachamento()
    poses = [pose_lateral(172, 20)] * 10 + [pose_lateral(ang, 30) for ang in angulos_repeticao(85)]
    poses += [pose_frontal(158)] * 15 + [pose_frontal(ang) for ang in angulos_repeticao(85, em_pe=158)]
    rodar(a, poses)
    assert a.repeticoes[-1].vista == "frontal"
    assert ERRO_EXTENSAO not in a.repeticoes[-1].erros


def test_um_quadro_errado_do_modelo_nao_vira_erro():
    a = AnalisadorAgachamento()
    poses = [pose_frontal(ang) for ang in angulos_repeticao(88)]
    poses[30] = pose_frontal(88, ombros=25, desvio=0.5)  # um único quadro com pontos fora do lugar
    rodar(a, poses)
    assert a.repeticoes[0].correta


def test_quadril_inclinado_de_frente():
    a = AnalisadorAgachamento()
    poses = []
    for ang in angulos_repeticao(88):
        p = pose_frontal(ang)
        if ang < 140:  # quadril direito 10° mais baixo
            x, y = p.imagem["quadril_dir"]
            dx = x - p.imagem["quadril_esq"][0]
            p.imagem["quadril_dir"] = (x, p.imagem["quadril_esq"][1] + dx * math.tan(math.radians(10)))
        poses.append(p)
    rodar(a, poses)
    assert ERRO_SIMETRIA in a.repeticoes[0].erros
