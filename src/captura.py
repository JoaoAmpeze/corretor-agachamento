"""Leitura da webcam numa thread separada, guardando sempre só o quadro mais recente.

Por que isso deixa o app mais rápido:
  - Se a análise de um quadro demora mais que o intervalo da câmera (ex.: 50 ms contra 33 ms),
    o OpenCV vai acumulando quadros num buffer interno e o vídeo fica cada vez mais atrasado.
    Aqui a câmera é lida o tempo todo e os quadros velhos são descartados: a análise pega
    sempre o mais novo, então o atraso fica no máximo de um quadro.
  - Pede à câmera o formato MJPG: muitas webcams USB entregam 720p a só 5–10 fps no formato
    padrão (YUY2) e 30 fps em MJPG.
"""
import platform
import threading
import time

import cv2


class CapturaWebcam:
    def __init__(self, indice, largura=1280, altura=720, fps=30):
        if platform.system() == "Windows":
            self.cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(indice)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # nem todo driver respeita; a thread garante o resto
        self._cond = threading.Condition()
        self._frame = None
        self._id = 0
        self._ativo = self.cap.isOpened()
        self._thread = threading.Thread(target=self._ler, daemon=True)
        if self._ativo:
            self._thread.start()

    def isOpened(self):  # mesmo nome do cv2.VideoCapture
        return self._ativo

    def _ler(self):
        falhas = 0
        while self._ativo:
            ok, frame = self.cap.read()
            if not ok:
                falhas += 1
                if falhas > 50:  # câmera desconectada
                    break
                time.sleep(0.01)
                continue
            falhas = 0
            with self._cond:
                self._frame = frame
                self._id += 1
                self._cond.notify_all()
        with self._cond:
            self._ativo = False
            self._cond.notify_all()

    def ler(self, ultimo_id=0, timeout=1.0):
        """Espera um quadro mais novo que `ultimo_id`. Devolve (id, frame) ou (ultimo_id, None)."""
        with self._cond:
            self._cond.wait_for(lambda: self._id > ultimo_id or not self._ativo, timeout)
            if self._id > ultimo_id:
                return self._id, self._frame
            return ultimo_id, None

    def read(self):
        """Mesmo formato do cv2.VideoCapture.read(): (ok, frame), sempre com um quadro novo."""
        frame = None
        while frame is None and self._ativo:  # a 1ª imagem pode demorar alguns segundos para chegar
            self._ultimo_lido, frame = self.ler(getattr(self, "_ultimo_lido", 0))
        return frame is not None, frame

    def get(self, propriedade):
        return self.cap.get(propriedade)

    @property
    def resolucao(self):
        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def release(self):
        self._ativo = False
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        self.cap.release()
