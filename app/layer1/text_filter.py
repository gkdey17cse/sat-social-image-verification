from PIL import Image

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _OCR_OK = True
except Exception as e:
    print(f"[layer1] pytesseract import failed: {e}. OCR disabled.")
    _OCR_OK = False


# Extend this list with region-specific abusive words as needed.
OFFENSIVE_WORDS = {
    "en": ["fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "slut"],
    "hi": ["chutiya", "madarchod", "bhenchod", "gandu", "harami", "saala", "kamina"],
    "bn": ["choda", "magi", "khanki"],
}


def extract_text(image: Image.Image) -> str:
    if not _OCR_OK:
        return ""
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        print(f"[layer1] OCR error: {e}")
        return ""


def get_text_risk_score(text: str) -> tuple[float, str]:
    """Return (score, matched_word). Score is 0.0 or 0.9 for exact matches."""
    if not text:
        return 0.0, ""
    lower = text.lower()
    for lang, words in OFFENSIVE_WORDS.items():
        for w in words:
            if w in lower:
                return 0.9, w
    return 0.0, ""
