"""Detecção dos pontos do corpo com o MediaPipe Pose Landmarker (modelo BlazePose)."""
import os
import sys
import urllib.request
from dataclasses import dataclass, field

import cv2
import numpy as np

# Índices dos 33 pontos do BlazePose usados no projeto
PONTOS = {
    "nariz": 0,
    "orelha_esq": 7, "orelha_dir": 8,
    "ombro_esq": 11, "ombro_dir": 12,
    "cotovelo_esq": 13, "cotovelo_dir": 14,
    "punho_esq": 15, "punho_dir": 16,
    "quadril_esq": 23, "quadril_dir": 24,
    "joelho_esq": 25, "joelho_dir": 26,
    "tornozelo_esq": 27, "tornozelo_dir": 28,
    "calcanhar_esq": 29, "calcanhar_dir": 30,
    "pe_esq": 31, "pe_dir": 32,
}

# Ligações desenhadas para formar o "esqueleto" na tela
CONEXOES = [
    ("orelha_esq", "ombro_esq"), ("orelha_dir", "ombro_dir"),
    ("ombro_esq", "ombro_dir"), ("ombro_esq", "cotovelo_esq"), ("cotovelo_esq", "punho_esq"),
    ("ombro_dir", "cotovelo_dir"), ("cotovelo_dir", "punho_dir"),
    ("ombro_esq", "quadril_esq"), ("ombro_dir", "quadril_dir"), ("quadril_esq", "quadril_dir"),
    ("quadril_esq", "joelho_esq"), ("joelho_esq", "tornozelo_esq"),
    ("quadril_dir", "joelho_dir"), ("joelho_dir", "tornozelo_dir"),
    ("tornozelo_esq", "calcanhar_esq"), ("calcanhar_esq", "pe_esq"), ("tornozelo_esq", "pe_esq"),
    ("tornozelo_dir", "calcanhar_dir"), ("calcanhar_dir", "pe_dir"), ("tornozelo_dir", "pe_dir"),
]

URL_MODELOS = {
    "lite": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "full": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "heavy": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
}


@dataclass
class Pose:
    """Pontos do corpo detectados em um frame.

    imagem: coordenadas em pixels (x, y) — usadas para medidas 2D e para desenhar.
    mundo:  coordenadas 3D em metros, com origem no quadril — usadas para o ângulo do joelho,
            que assim não depende do ângulo da câmera.
    visibilidade: confiança (0 a 1) de que o ponto está visível.
    """
    imagem: dict = field(default_factory=dict)
    mundo: dict = field(default_factory=dict)
    visibilidade: dict = field(default_factory=dict)

    def visivel(self, *nomes, minimo=0.5):
        return all(self.visibilidade.get(n, 0.0) >= minimo for n in nomes)


def garantir_modelo(variante="full", pasta="models"):
    """Baixa o arquivo do modelo na primeira execução e devolve o caminho dele."""
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"pose_landmarker_{variante}.task")
    if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
        return caminho
    url = URL_MODELOS[variante]
    print(f"Baixando o modelo '{variante}' (só na primeira vez)...")
    try:
        urllib.request.urlretrieve(url, caminho + ".tmp")
        os.replace(caminho + ".tmp", caminho)
    except Exception as erro:  # noqa: BLE001
        if os.path.exists(caminho + ".tmp"):
            os.remove(caminho + ".tmp")
        sys.exit(f"Não foi possível baixar o modelo ({erro}).\n"
                 f"Baixe manualmente em:\n  {url}\ne salve como: {caminho}")
    return caminho


class DetectorPose:
    """Envolve o PoseLandmarker do MediaPipe no modo de vídeo (usa o frame anterior para rastrear)."""

    def __init__(self, caminho_modelo, confianca=0.5):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        opcoes = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=caminho_modelo),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=confianca,
            min_pose_presence_confidence=confianca,
            min_tracking_confidence=confianca,
        )
        self._detector = vision.PoseLandmarker.create_from_options(opcoes)
        self._ultimo_ts = -1

    def detectar(self, frame_bgr, timestamp_ms):
        """Recebe um frame BGR do OpenCV e devolve um objeto Pose (ou None se não achar ninguém)."""
        # O MediaPipe exige timestamps sempre crescentes
        timestamp_ms = max(int(timestamp_ms), self._ultimo_ts + 1)
        self._ultimo_ts = timestamp_ms

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        resultado = self._detector.detect_for_video(imagem, timestamp_ms)
        if not resultado.pose_landmarks:
            return None

        altura, largura = frame_bgr.shape[:2]
        pontos_img = resultado.pose_landmarks[0]
        pontos_mundo = resultado.pose_world_landmarks[0]
        pose = Pose()
        for nome, i in PONTOS.items():
            p = pontos_img[i]
            pose.imagem[nome] = (p.x * largura, p.y * altura)
            pose.visibilidade[nome] = p.visibility if p.visibility is not None else 1.0
            w = pontos_mundo[i]
            pose.mundo[nome] = (w.x, w.y, w.z)
        return pose

    def fechar(self):
        self._detector.close()
