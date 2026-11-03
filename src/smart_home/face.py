"""Optional consented-image comparison, separate from all door controls.

This module was added during restoration. The supplied archive did not contain
the candidate-reported facial-recognition implementation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

from .controller import CommandError

COMMIT = "48b10fa505aeb51fbd127fc60a5c660040e823b7"
MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "folder": "face_detection_yunet", "bytes": 232589,
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "license": "MIT",
    },
    "face_recognition_sface_2021dec.onnx": {
        "folder": "face_recognition_sface", "bytes": 38696353,
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "license": "Apache-2.0",
    },
}


def verify_models(directory: Path) -> None:
    for name, info in MODELS.items():
        p = directory / name
        if not p.is_file() or p.stat().st_size != info["bytes"]:
            raise CommandError("Face models are missing. Run: python -m smart_home.models models")
        if hashlib.sha256(p.read_bytes()).hexdigest() != info["sha256"]:
            raise CommandError(f"Model integrity check failed: {name}.")


def download_models(directory: Path) -> None:
    """Explicit, bounded download from pinned OpenCV Zoo; never runs on import."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, info in MODELS.items():
        target = directory / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == info["sha256"]:
            continue
        url = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/" + COMMIT +
               "/models/" + str(info["folder"]) + "/" + name)
        temp = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SmartHomePortfolio/1"})
            with urllib.request.urlopen(request, timeout=45) as response:
                with tempfile.NamedTemporaryFile(dir=directory, delete=False) as out:
                    temp = Path(out.name)
                    count = 0
                    while chunk := response.read(1024 * 1024):
                        count += len(chunk)
                        if count > info["bytes"]:
                            raise CommandError("Model download exceeded its expected size.")
                        out.write(chunk)
            if temp.stat().st_size != info["bytes"] or hashlib.sha256(temp.read_bytes()).hexdigest() != info["sha256"]:
                raise CommandError("Model download did not match the pinned OpenCV digest.")
            temp.replace(target)
            license_url = ("https://raw.githubusercontent.com/opencv/opencv_zoo/" + COMMIT +
                           "/models/" + str(info["folder"]) + "/LICENSE")
            with urllib.request.urlopen(license_url, timeout=20) as source:
                license_text = source.read(100_000)
            (directory / (str(info["folder"]) + "_LICENSE.txt")).write_bytes(license_text)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
    verify_models(directory)
    (directory / "source.json").write_text(json.dumps({"repository": "opencv/opencv_zoo",
        "commit": COMMIT, "models": MODELS}, indent=2) + "\n")


def compare(reference: Path, probe: Path, directory: Path) -> dict[str, object]:
    try:
        import cv2
    except ImportError as e:
        raise CommandError("Install the face extra: pip install '.[face]'.") from e
    verify_models(directory)
    cv2.setNumThreads(1)
    detector = cv2.FaceDetectorYN.create(str(directory / "face_detection_yunet_2023mar.onnx"),
                                        "", (320, 320), score_threshold=0.9)
    recognizer = cv2.FaceRecognizerSF.create(
        str(directory / "face_recognition_sface_2021dec.onnx"), "")
    features = []
    for path in (reference, probe):
        if not path.is_file() or path.stat().st_size > 20_000_000:
            raise CommandError("Use a local image file smaller than20MB.")
        image = cv2.imread(str(path))
        if image is None or image.shape[0] * image.shape[1] > 30_000_000:
            raise CommandError("Cannot read this image, or its dimensions are too large.")
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
        if faces is None or len(faces) != 1:
            raise CommandError("Each image must contain exactly one clearly detected face.")
        crop = recognizer.alignCrop(image, faces[0])
        features.append(recognizer.feature(crop).copy())
    score = float(recognizer.match(features[0], features[1], cv2.FaceRecognizerSF_FR_COSINE))
    return {"mode": "offline_image_comparison", "cosine_similarity": round(score, 6),
            "reference_threshold": 0.363, "above_reference_threshold": score >= 0.363,
            "door_action": "none", "stores_face_images_or_embeddings": False,
            "limit": "The OpenCV tutorial threshold is a demonstration reference, not a validated "
                     "access-control decision. No liveness or spoof resistance is provided."}
