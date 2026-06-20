"""
Fire/smoke detection model backends.

StubBackend: deterministic randomised results for pipeline testing (no GPU/model needed).
ONNXBackend: loads a real ONNX checkpoint (e.g. YOLO fine-tuned on fire/smoke) from
             DETECTION_MODEL_PATH.  Falls back to StubBackend if onnxruntime is not
             installed or the path is unset.

Public surface is unchanged — call run_fire_detection(frame) exactly as before.
"""

import hashlib
import logging
import os
import random
from abc import ABC, abstractmethod
from typing import Optional

from shared.models import DroneFrame

logger = logging.getLogger(__name__)

DetectResult = tuple[str, float, Optional[list[float]]]


class ModelBackend(ABC):
    @abstractmethod
    def detect(self, frame: DroneFrame) -> DetectResult:
        """Return (fire_class, confidence, bounding_box).

        fire_class: "none" | "smoke" | "flame"
        bounding_box: [x1, y1, x2, y2] normalised, or None when fire_class == "none"
        """


class StubBackend(ModelBackend):
    """Deterministic stub seeded from drone_id + timestamp — no inference needed."""

    def detect(self, frame: DroneFrame) -> DetectResult:
        seed = hashlib.sha256(f"{frame.drone_id}{frame.timestamp}".encode()).hexdigest()
        rng = random.Random(seed)
        roll = rng.random()

        if roll < 0.6:
            return "none", 0.0, None
        if roll < 0.85:
            return "smoke", round(rng.uniform(0.5, 0.85), 2), [0.30, 0.20, 0.60, 0.50]
        return "flame", round(rng.uniform(0.7, 0.98), 2), [0.35, 0.40, 0.55, 0.70]


class ONNXBackend(ModelBackend):
    """Runs a real ONNX model (e.g. YOLOv8-fire) for inference.

    In production the service would fetch the image from frame.frame_url (S3/GCS)
    and pass it through the model.  This skeleton passes a dummy tensor so the
    class can be exercised without a media pipeline.

    Expected model I/O contract:
      input  — float32 NCHW tensor, shape [1, 3, H, W], values in [0, 1]
      output — float32 array with columns [x1, y1, x2, y2, confidence, class_id]
               class_id: 0 = smoke, 1 = flame  (adjust CLASSES below to match your model)
    """

    CLASSES = {0: "smoke", 1: "flame"}
    CONFIDENCE_THRESHOLD = 0.4
    INPUT_SIZE = (640, 640)

    def __init__(self, model_path: str) -> None:
        import onnxruntime as ort  # deferred so ImportError is catchable by factory

        self._session = ort.InferenceSession(
            model_path,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self._input_name: str = self._session.get_inputs()[0].name
        logger.info("ONNXBackend loaded model from %s", model_path)

    def detect(self, frame: DroneFrame) -> DetectResult:
        import numpy as np

        # In production: download frame.frame_url, decode, resize, normalise.
        # Here we pass a zero tensor so the class is exercisable end-to-end.
        h, w = self.INPUT_SIZE
        dummy = np.zeros((1, 3, h, w), dtype=np.float32)

        outputs = self._session.run(None, {self._input_name: dummy})
        detections = outputs[0]  # shape [N, 6]

        if detections is None or len(detections) == 0:
            return "none", 0.0, None

        # Pick highest-confidence detection above threshold.
        best = max(
            (d for d in detections if d[4] >= self.CONFIDENCE_THRESHOLD),
            key=lambda d: d[4],
            default=None,
        )
        if best is None:
            return "none", 0.0, None

        x1, y1, x2, y2, confidence, class_id = best[:6]
        fire_class = self.CLASSES.get(int(class_id), "smoke")
        bbox = [float(x1), float(y1), float(x2), float(y2)]
        return fire_class, round(float(confidence), 2), bbox


def _load_backend() -> ModelBackend:
    model_path = os.environ.get("DETECTION_MODEL_PATH", "")
    if model_path:
        try:
            backend = ONNXBackend(model_path)
            logger.info("Detection using ONNXBackend (%s)", model_path)
            return backend
        except ImportError:
            logger.warning(
                "onnxruntime not installed — falling back to StubBackend. "
                "Install it with: pip install onnxruntime  (or onnxruntime-gpu)"
            )
        except Exception as exc:
            logger.warning("Failed to load ONNX model %s (%s) — falling back to StubBackend", model_path, exc)

    logger.info("Detection using StubBackend (set DETECTION_MODEL_PATH to use a real model)")
    return StubBackend()


_backend: ModelBackend = _load_backend()


def run_fire_detection(frame: DroneFrame) -> DetectResult:
    """Public entry point — unchanged signature, routes through the active backend."""
    return _backend.detect(frame)
