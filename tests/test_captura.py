"""Testa a leitura da webcam em thread com uma câmera falsa de 30 fps (sem hardware)."""
import time

import numpy as np

from src import captura


class CameraFalsa:
    def __init__(self, *args):
        self.n = 0
        self.inicio = time.time()

    def set(self, *args):
        return True

    def get(self, *args):
        return 30

    def isOpened(self):
        return True

    def read(self):
        self.n += 1
        espera = self.inicio + self.n / 30 - time.time()
        if espera > 0:
            time.sleep(espera)
        return True, np.full((72, 128, 3), self.n % 256, np.uint8)

    def release(self):
        pass


def test_analise_lenta_recebe_sempre_o_quadro_mais_recente(monkeypatch):
    monkeypatch.setattr(captura.cv2, "VideoCapture", CameraFalsa)
    cam = captura.CapturaWebcam(0)
    try:
        ultimo, ids = 0, []
        for _ in range(10):
            ultimo, frame = cam.ler(ultimo)
            assert frame is not None
            ids.append(ultimo)
            time.sleep(0.08)  # análise lenta (~12 fps) com a câmera a 30 fps
        assert len(set(ids)) == len(ids)            # nunca o mesmo quadro duas vezes
        assert ids[-1] - ids[0] >= 15               # quadros velhos foram pulados
        assert cam._id - ids[-1] <= 4               # atraso pequeno no fim (não acumula)
        ok, frame = cam.read()                      # interface igual à do cv2.VideoCapture
        assert ok and frame.shape == (72, 128, 3)
    finally:
        cam.release()
    assert not cam.isOpened()
