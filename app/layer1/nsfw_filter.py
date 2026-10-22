import numpy as np
from PIL import Image

_classifier = None
_import_ok = True

try:
    from opennsfw_onnx import NSFWClassifier

    print("[layer1] opennsfw-onnx imported OK")
except Exception as e:
    print(f"[layer1] opennsfw-onnx import FAILED: {e}")
    _import_ok = False


def get_classifier():
    global _classifier
    if _classifier is None and _import_ok:
        try:
            _classifier = NSFWClassifier()
            print("[layer1] NSFWClassifier instantiated OK")
        except Exception as e:
            print(f"[layer1] NSFWClassifier() FAILED: {e}")
            _classifier = None
    return _classifier


def get_nsfw_score(image: Image.Image) -> float:
    clf = get_classifier()
    if clf is None:
        return 0.5

    img = image.convert("RGB")

    # Try PIL.Image first (supported natively), then ndarray
    try:
        pred = clf.classify(img)
        return float(pred.nsfw)
    except Exception as e1:
        try:
            pred = clf.classify(np.array(img))
            return float(pred.nsfw)
        except Exception as e2:
            print(f"[layer1] NSFW classify failed: pil_err={e1}, ndarray_err={e2}")
            return 0.5
