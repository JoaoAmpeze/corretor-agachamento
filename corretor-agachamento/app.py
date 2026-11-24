"""Corretor de Agachamento — aplicativo web local.

Execução:  python app.py   (abre http://localhost:5000 no navegador)

O Python faz todo o processamento (câmera/vídeo -> MediaPipe -> regras) e envia para o navegador:
  - o vídeo com o esqueleto desenhado (stream MJPEG em /video)
  - o estado do treino em JSON (/api/estado), lido pela página várias vezes por segundo.
"""
import argparse
import inspect
import os
import threading
import time
import webbrowser

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from src import historico, voz
from src.analisador_agachamento import AnalisadorAgachamento, medidas_formatadas
from src.captura import CapturaWebcam
from src.detector_pose import DetectorPose, garantir_modelo
from src.interface import Interface
from src.relatorio import salvar_csv
from src.treino import CONCLUIDO, ConfigTreino, Treino

PASTA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PASTA_UPLOADS = "uploads"
EXTENSOES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

# Modos de desempenho: trocam o modelo do MediaPipe e o tamanho da imagem processada.
#   rápido      -> modelo lite  + 960x540  (notebooks mais simples, sem placa de vídeo)
#   equilibrado -> modelo full  + 1280x720 (padrão)
#   preciso     -> modelo heavy + 1280x720 (PC mais forte; melhor quando a pessoa está longe)
DESEMPENHO = {
    "rapido": {"modelo": "lite", "lado_maior": 960, "jpeg": 70},
    "equilibrado": {"modelo": "full", "lado_maior": 1280, "jpeg": 75},
    "preciso": {"modelo": "heavy", "lado_maior": 1280, "jpeg": 75},
}
MODO_DO_MODELO = {v["modelo"]: k for k, v in DESEMPENHO.items()}


def quadro_vazio(texto, largura=1280, altura=720):
    img = np.full((altura, largura, 3), (32, 26, 22), np.uint8)
    tam = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 2)[0]
    cv2.putText(img, texto, ((largura - tam[0]) // 2, altura // 2), cv2.FONT_HERSHEY_SIMPLEX,
                1.1, (150, 150, 150), 2, cv2.LINE_AA)
    return cv2.imencode(".jpg", img)[1].tobytes()


class Motor:
    """Roda a captura e a análise numa thread separada do servidor web."""

    def __init__(self, fabrica_detector=None, variante_modelo="full"):
        self._fabrica_detector = fabrica_detector or (lambda variante: DetectorPose(garantir_modelo(variante)))
        self.desempenho_padrao = MODO_DO_MODELO.get(variante_modelo, "equilibrado")
        self.desempenho = self.desempenho_padrao
        self._trava = threading.Condition()  # protege o quadro/estado e avisa o stream quando há quadro novo
        self._jpeg_id = 0
        self.fps = 0.0
        self._thread = None
        self._parar = threading.Event()
        self.pausado = False
        self.treino = None
        self.analisador = None
        self.fonte = ""
        self.erro = None
        self.sessao_id = None
        self._jpeg = quadro_vazio("Camera desligada")
        self._estado_analise = None
        self._tempo_atual = 0.0
        self.fim_do_video = False

    # ------------------------------------------------------------------ controle
    @property
    def rodando(self):
        return self._thread is not None and self._thread.is_alive()

    def iniciar(self, fonte, config, vista="auto", desempenho=None):
        self.parar()
        self.desempenho = desempenho if desempenho in DESEMPENHO else self.desempenho_padrao
        self.fps = 0.0
        self.erro, self.sessao_id, self.pausado, self.fim_do_video = None, None, False, False
        self.fonte = fonte
        if not fonte.isdigit():
            # num vídeo gravado a pessoa não para para descansar: as séries seguem direto
            config.contagem_s, config.descanso_s = 0, 0
        self.analisador = AnalisadorAgachamento(vista=vista)
        self.treino = Treino(self.analisador, config)
        self._estado_analise = None
        self._parar.clear()
        self._publicar(quadro_vazio("Abrindo a camera..."))
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()

    def parar(self):
        if self.rodando:
            self._parar.set()
            self._thread.join(timeout=5)

    def pausar(self, pausado):
        self.pausado = bool(pausado)

    def pular_descanso(self):
        if self.treino:
            self.treino.pular_descanso(self._tempo_atual)

    # ------------------------------------------------------------------ laço principal
    def _abrir_captura(self):
        if self.fonte.isdigit():
            lado = DESEMPENHO[self.desempenho]["lado_maior"]
            return CapturaWebcam(int(self.fonte), lado, lado * 9 // 16), True
        return cv2.VideoCapture(self.fonte), False

    def _criar_detector(self):
        variante = DESEMPENHO[self.desempenho]["modelo"]
        if inspect.signature(self._fabrica_detector).parameters:
            return self._fabrica_detector(variante)
        return self._fabrica_detector()  # fábricas de teste sem parâmetro

    def _publicar(self, jpeg, estado=None):
        """Troca o quadro mostrado na página e acorda quem está esperando por ele (o stream /video)."""
        with self._trava:
            self._jpeg = jpeg
            self._jpeg_id += 1
            if estado is not None:
                self._estado_analise = estado
            self._trava.notify_all()

    def _laco(self):
        detector = None
        cap = None
        try:
            if self.desempenho != self.desempenho_padrao:
                self._publicar(quadro_vazio("Carregando o modelo..."))
            detector = self._criar_detector()  # antes da câmera: na 1ª vez o modelo pode ser baixado
            cap, webcam = self._abrir_captura()
            if not cap.isOpened():
                raise RuntimeError(f"Não foi possível abrir a fonte de vídeo ({self.fonte}).")
            config = DESEMPENHO[self.desempenho]
            fps_video = (cap.get(cv2.CAP_PROP_FPS) or 30) if not webcam else 30
            interface = None
            inicio = time.time()
            pausado_total, inicio_pausa = 0.0, None
            frame_idx, quadro_id = 0, 0
            ultimo_quadro = None
            self._tempo_atual = 0.0

            while not self._parar.is_set() and self.treino.fase != CONCLUIDO:
                if self.pausado:
                    inicio_pausa = inicio_pausa or time.time()
                    time.sleep(0.05)
                    continue
                if inicio_pausa:
                    pausado_total += time.time() - inicio_pausa
                    inicio_pausa = None

                if webcam:
                    # sempre o quadro mais novo (os que chegaram durante a análise anterior são descartados)
                    quadro_id, frame = cap.ler(quadro_id)
                    if frame is None:
                        if not cap.isOpened():
                            raise RuntimeError("A câmera parou de enviar imagens (foi desconectada?).")
                        continue
                    frame = cv2.flip(frame, 1)  # espelho; também cria uma cópia, a thread da câmera segue livre
                else:
                    ok, frame = cap.read()
                    if not ok:
                        self.fim_do_video = True
                        break
                h, w = frame.shape[:2]
                lado_maior = config["lado_maior"]
                if max(h, w) > lado_maior:  # vídeos grandes (inclusive em pé, do celular) são reduzidos
                    escala = lado_maior / max(h, w)
                    frame = cv2.resize(frame, (int(w * escala), int(h * escala)), interpolation=cv2.INTER_AREA)
                # relógio real (sem as pausas): usado na contagem regressiva, no descanso e na duração
                relogio = time.time() - inicio - pausado_total
                if webcam:
                    tempo_s = relogio
                else:
                    # tempo do vídeo: usado na duração de cada repetição
                    tempo_s = frame_idx / fps_video
                    atraso = tempo_s - relogio  # reproduz o vídeo na velocidade real
                    if atraso > 0:
                        time.sleep(atraso)
                        relogio = time.time() - inicio - pausado_total
                frame_idx += 1
                self._tempo_atual = relogio

                pose = detector.detectar(frame, tempo_s * 1000)
                if self.treino.deve_analisar:
                    estado = self.analisador.processar(pose, tempo_s)
                else:
                    # fora da série: só verifica se a pessoa aparece inteira (para a contagem regressiva)
                    estado = self.analisador.processar(pose, tempo_s)
                    self.analisador.reiniciar_movimento()
                    estado.alertas = [a for a in estado.alertas if a.startswith("Afaste")]
                self.treino.atualizar(estado, relogio)

                if interface is None or interface.lado_menor != min(frame.shape[:2]):
                    interface = Interface(min(frame.shape[:2]))
                interface.desenhar_esqueleto(frame, pose, estado)
                jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config["jpeg"]])[1].tobytes()
                self._publicar(jpeg, estado)

                # quadros analisados por segundo (média móvel), mostrado na tela
                agora = time.perf_counter()
                if ultimo_quadro is not None:
                    inst = 1 / max(agora - ultimo_quadro, 1e-3)
                    self.fps = inst if self.fps == 0 else self.fps * 0.9 + inst * 0.1
                ultimo_quadro = agora
        except Exception as erro:  # noqa: BLE001
            self.erro = str(erro)
        finally:
            if cap is not None:
                cap.release()
            if detector is not None:
                detector.fechar()
            self._finalizar()

    def _finalizar(self):
        if self.treino is None:
            return
        self.treino.concluir(getattr(self, "_tempo_atual", 0.0))
        resumo = self.treino.resumo()
        if resumo["total"] > 0:
            sessao = historico.salvar_sessao(resumo, fonte=os.path.basename(self.fonte))
            self.sessao_id = sessao["id"]
            os.makedirs("resultados", exist_ok=True)
            salvar_csv(self.analisador.repeticoes, os.path.join("resultados", f"sessao_{sessao['id']}.csv"))
        self._publicar(quadro_vazio("Treino encerrado" if not self.erro else "Erro: veja a mensagem na tela"))

    # ------------------------------------------------------------------ dados para a página
    def jpeg(self):
        with self._trava:
            return self._jpeg

    def jpeg_novo(self, ultimo_id, timeout=1.0):
        """Espera um quadro diferente de `ultimo_id` (ou o tempo acabar) e devolve (id, jpeg)."""
        with self._trava:
            self._trava.wait_for(lambda: self._jpeg_id != ultimo_id, timeout)
            return self._jpeg_id, self._jpeg

    def estado(self, desde_evento=0):
        t = self.treino
        if t is None:
            return {"ativo": False, "erro": self.erro}
        with self._trava:
            e = self._estado_analise
        reps = self.analisador.repeticoes
        ultima = reps[-1] if reps else None
        total = len(reps)
        corretas = sum(r.correta for r in reps)
        return {
            "ativo": self.rodando,
            "pausado": self.pausado,
            "erro": self.erro,
            "sessao_id": self.sessao_id,
            "video": not self.fonte.isdigit(),
            "fim_do_video": self.fim_do_video,
            "fps": round(self.fps, 1),
            "desempenho": self.desempenho,
            "fase": t.fase,
            "serie": t.serie,
            "series": t.config.series,
            "meta": t.config.repeticoes,
            "reps_na_serie": t.reps_na_serie,
            "restante_s": round(t.restante_s, 1),
            "descanso_s": t.config.descanso_s,
            "total": total,
            "corretas": corretas,
            "percentual": round(100 * corretas / total) if total else None,
            "nota_media": round(sum(r.nota for r in reps) / total) if total else None,
            "analise": None if e is None else {
                "pessoa": e.pessoa_detectada,
                "vista": e.vista,
                "movimento": e.fase,
                "joelho": None if e.angulo_joelho is None else round(e.angulo_joelho),
                "quadril": None if e.angulo_quadril is None else round(e.angulo_quadril),
                "tronco": None if e.inclinacao_tronco is None else round(e.inclinacao_tronco),
                "canela": None if e.inclinacao_canela is None else round(e.inclinacao_canela),
                "calcanhar": None if e.calcanhar is None else round(100 * e.calcanhar),
                "abertura": None if e.razao_joelhos is None else round(e.razao_joelhos, 2),
                "simetria": None if e.assimetria_joelhos is None else round(e.assimetria_joelhos),
                "base": None if e.base is None else round(e.base, 1),
                "equilibrio": None if e.equilibrio is None else round(e.equilibrio, 2),
                "ombros": None if e.ombros is None else round(e.ombros),
                "linha_pe": None if e.linha_pe is None else round(100 * e.linha_pe),
                "cabeca": None if e.cabeca is None else round(e.cabeca),
                "alertas": e.alertas,
            },
            "ultima": None if ultima is None else {
                "serie": ultima.serie, "numero": ultima.numero, "nota": ultima.nota,
                "notas": ultima.notas, "erros": ultima.erros, "correta": ultima.correta, "avisos": ultima.avisos,
                "medidas": medidas_formatadas(ultima),
            },
            "reps": [{"serie": r.serie, "nota": r.nota, "correta": r.correta} for r in reps],
            "eventos": t.eventos_desde(desde_evento),
        }


def criar_app(motor=None):
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False  # mantém a ordem dos erros (do mais frequente para o menos)
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
    motor = motor or Motor()
    app.motor = motor

    @app.get("/")
    def pagina():
        return send_from_directory(PASTA_WEB, "index.html")

    @app.get("/web/<path:arquivo>")
    def estaticos(arquivo):
        return send_from_directory(PASTA_WEB, arquivo)

    @app.get("/video")
    def video():
        def gerar():
            # só envia quando há quadro novo; sem quadro novo em 1 s, reenvia o atual (mantém a conexão viva)
            ultimo = -1
            while True:
                ultimo, jpeg = motor.jpeg_novo(ultimo)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode()
                       + b"\r\n\r\n" + jpeg + b"\r\n")
        return Response(gerar(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.post("/api/iniciar")
    def iniciar():
        d = request.get_json(force=True)
        fonte = str(d.get("fonte", "0"))
        if not fonte.isdigit() and not os.path.exists(fonte):
            return jsonify({"erro": "Vídeo não encontrado. Envie o arquivo novamente."}), 400
        config = ConfigTreino(series=max(int(d.get("series", 3)), 1),
                              repeticoes=max(int(d.get("repeticoes", 10)), 0),
                              descanso_s=max(int(d.get("descanso", 45)), 0),
                              contagem_s=max(int(d.get("contagem", 3)), 0))
        motor.iniciar(fonte, config, vista=d.get("vista", "auto"), desempenho=d.get("desempenho"))
        if d.get("voz") in voz.VOZES:
            voz.preaquecer(motor.treino.frases_fixas(), d["voz"])
        return jsonify({"ok": True})

    @app.get("/api/voz")
    def falar():
        caminho = voz.gerar(request.args.get("t", ""), request.args.get("v", "francisca"))
        if caminho is None:
            return jsonify({"erro": "Voz natural indisponível (sem internet?)."}), 503
        resposta = send_from_directory(os.path.abspath(os.path.dirname(caminho)), os.path.basename(caminho),
                                       mimetype="audio/mpeg")
        resposta.headers["Cache-Control"] = "public, max-age=31536000"
        return resposta

    @app.post("/api/parar")
    def parar():
        motor.parar()
        return jsonify({"ok": True, "sessao_id": motor.sessao_id})

    @app.post("/api/pausar")
    def pausar():
        motor.pausar(request.get_json(force=True).get("pausado", True))
        return jsonify({"ok": True})

    @app.post("/api/pular-descanso")
    def pular():
        motor.pular_descanso()
        return jsonify({"ok": True})

    @app.get("/api/info")
    def info():
        return jsonify({"desempenho": motor.desempenho_padrao})

    @app.get("/api/estado")
    def estado():
        return jsonify(motor.estado(int(request.args.get("desde", 0))))

    @app.post("/api/upload")
    def upload():
        arquivo = request.files.get("video")
        if not arquivo or not arquivo.filename:
            return jsonify({"erro": "Nenhum arquivo enviado."}), 400
        nome = secure_filename(arquivo.filename) or "video.mp4"
        if os.path.splitext(nome)[1].lower() not in EXTENSOES_VIDEO:
            return jsonify({"erro": "Formato não suportado. Use MP4, MOV, AVI, MKV ou WEBM."}), 400
        os.makedirs(PASTA_UPLOADS, exist_ok=True)
        caminho = os.path.join(PASTA_UPLOADS, nome)
        arquivo.save(caminho)
        return jsonify({"fonte": caminho, "nome": nome})

    @app.get("/api/historico")
    def listar():
        sessoes = historico.carregar()
        # a lista não precisa dos detalhes de cada repetição
        return jsonify([{k: v for k, v in s.items() if k != "repeticoes"} for s in sessoes])

    @app.get("/api/historico/<sessao_id>")
    def detalhe(sessao_id):
        s = historico.buscar(sessao_id)
        return (jsonify(s), 200) if s else (jsonify({"erro": "Sessão não encontrada."}), 404)

    @app.delete("/api/historico/<sessao_id>")
    def apagar(sessao_id):
        historico.apagar(sessao_id)
        return jsonify({"ok": True})

    return app


def main():
    p = argparse.ArgumentParser(description="Corretor de Agachamento — aplicativo web local")
    p.add_argument("--porta", type=int, default=5000)
    p.add_argument("--modelo", default="full", choices=["lite", "full", "heavy"])
    p.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador automaticamente.")
    args = p.parse_args()

    garantir_modelo(args.modelo)  # baixa o modelo antes de abrir a página
    # gera em segundo plano as frases mais comuns da voz natural (números e dicas)
    voz.preaquecer(Treino(AnalisadorAgachamento(), ConfigTreino()).frases_fixas(), "francisca")
    app = criar_app(Motor(variante_modelo=args.modelo))
    url = f"http://localhost:{args.porta}"
    print(f"\nCorretor de Agachamento rodando em {url}  (Ctrl+C para sair)\n")
    if not args.sem_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=args.porta, threaded=True, debug=False)


if __name__ == "__main__":
    main()
