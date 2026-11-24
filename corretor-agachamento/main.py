"""Corretor de Agachamento — análise da execução do agachamento com visão computacional.

Exemplos:
  python main.py                          # webcam
  python main.py --fonte video.mp4        # vídeo gravado
  python main.py --fonte video.mp4 --salvar-video resultados/saida.mp4
  python main.py --vista lateral          # força a vista (auto, lateral ou frontal)

Teclas: Q ou ESC = sair | R = zerar contagem | S = salvar print | ESPAÇO = pausar
"""
import argparse
import os
import time
from datetime import datetime

import cv2

from src.analisador_agachamento import AnalisadorAgachamento
from src.captura import CapturaWebcam
from src.detector_pose import DetectorPose, garantir_modelo
from src.interface import Interface
from src.relatorio import resumo_texto, salvar_csv


def argumentos():
    p = argparse.ArgumentParser(description="Analisa a execução do agachamento pela câmera ou por vídeo.")
    p.add_argument("--fonte", default="0", help="Índice da webcam (0, 1...) ou caminho de um vídeo.")
    p.add_argument("--vista", default="auto", choices=["auto", "lateral", "frontal"],
                   help="Posição da câmera em relação à pessoa (padrão: detectar automaticamente).")
    p.add_argument("--modelo", default="full", choices=["lite", "full", "heavy"],
                   help="Versão do modelo: lite (mais rápido) ou heavy (mais preciso).")
    p.add_argument("--salvar-video", default=None, help="Salva o vídeo com a análise desenhada.")
    p.add_argument("--sem-janela", action="store_true", help="Processa sem abrir janela (para vídeos).")
    p.add_argument("--largura", type=int, default=1280, help="Largura usada para exibir/processar.")
    return p.parse_args()


def abrir_fonte(fonte):
    webcam = fonte.isdigit()
    # webcam: leitura numa thread, sempre com o quadro mais recente (sem atraso acumulado)
    cap = CapturaWebcam(int(fonte)) if webcam else cv2.VideoCapture(fonte)
    if not cap.isOpened():
        raise SystemExit(f"Não foi possível abrir a fonte de vídeo: {fonte}")
    return cap, webcam


def redimensionar(frame, largura):
    h, w = frame.shape[:2]
    if w == largura:
        return frame
    return cv2.resize(frame, (largura, int(h * largura / w)))


def main():
    args = argumentos()
    os.makedirs("resultados", exist_ok=True)
    sessao = datetime.now().strftime("%Y%m%d_%H%M%S")

    detector = DetectorPose(garantir_modelo(args.modelo))
    analisador = AnalisadorAgachamento(vista=args.vista)
    cap, webcam = abrir_fonte(args.fonte)
    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30

    interface, gravador = None, None
    pausado, frame_idx = False, 0
    inicio, ultimo_t, fps = time.time(), time.time(), 0.0
    frame = None

    while True:
        if not pausado or frame is None:
            ok, bruto = cap.read()
            if not ok:
                break
            bruto = redimensionar(bruto, args.largura)
            if webcam:
                bruto = cv2.flip(bruto, 1)  # efeito espelho, mais natural para quem se vê
            # Tempo do frame: relógio real na webcam, posição no vídeo para arquivos
            tempo_s = (time.time() - inicio) if webcam else frame_idx / fps_video
            frame_idx += 1

            pose = detector.detectar(bruto, tempo_s * 1000)
            estado = analisador.processar(pose, tempo_s)

            frame = bruto.copy()
            if interface is None:
                interface = Interface(min(frame.shape[:2]))
            agora = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(agora - ultimo_t, 1e-6))
            ultimo_t = agora
            interface.desenhar_esqueleto(frame, pose, estado)
            interface.desenhar_painel(frame, estado, fps=fps if webcam else None)

            if args.salvar_video:
                if gravador is None:
                    h, w = frame.shape[:2]
                    gravador = cv2.VideoWriter(args.salvar_video, cv2.VideoWriter_fourcc(*"mp4v"),
                                               fps_video if not webcam else 20, (w, h))
                gravador.write(frame)

        if args.sem_janela:
            continue
        exibido = frame.copy()
        if pausado:
            interface.desenhar_painel(exibido, estado, pausado=True)
        cv2.imshow("Corretor de Agachamento", exibido)
        tecla = cv2.waitKey(1 if not pausado else 50) & 0xFF
        if tecla in (ord("q"), 27):
            break
        if tecla == ord("r"):
            analisador.zerar()
        if tecla == ord("s"):
            caminho = os.path.join("resultados", f"print_{datetime.now():%H%M%S}.png")
            cv2.imwrite(caminho, frame)
            print("Print salvo em", caminho)
        if tecla == ord(" "):
            pausado = not pausado

    cap.release()
    if gravador:
        gravador.release()
    detector.fechar()
    cv2.destroyAllWindows()

    print("\n=== Resumo da sessão ===")
    print(resumo_texto(analisador.repeticoes))
    if analisador.repeticoes:
        caminho = salvar_csv(analisador.repeticoes, os.path.join("resultados", f"sessao_{sessao}.csv"))
        print("Relatório salvo em", caminho)


if __name__ == "__main__":
    main()
