from PIL import Image

from app.config import NSFW_BLOCK_THRESHOLD, NSFW_PASS_THRESHOLD
from app.models.schemas import Layer1Decision, Layer1Result
from app.layer1.nsfw_filter import get_nsfw_score
from app.layer1.text_filter import extract_text, get_text_risk_score


def run_layer1(image: Image.Image) -> Layer1Result:
    nsfw_score = get_nsfw_score(image)
    text = extract_text(image)
    text_score, matched = get_text_risk_score(text)

    # Hard block: very high NSFW
    if nsfw_score >= NSFW_BLOCK_THRESHOLD:
        return Layer1Result(
            decision=Layer1Decision.BLOCK,
            nsfw_score=nsfw_score,
            text_risk_score=text_score,
            extracted_text=text,
            matched_word=matched,
            reason=f"NSFW {nsfw_score:.3f} >= {NSFW_BLOCK_THRESHOLD}",
        )

    # Hard block: high-confidence offensive text
    if text_score >= 0.9:
        return Layer1Result(
            decision=Layer1Decision.BLOCK,
            nsfw_score=nsfw_score,
            text_risk_score=text_score,
            extracted_text=text,
            matched_word=matched,
            reason=f"Offensive text '{matched}' detected",
        )

    # Hard pass: very low NSFW and no text at all
    if nsfw_score <= NSFW_PASS_THRESHOLD and text_score < 0.5 and not text:
        return Layer1Result(
            decision=Layer1Decision.PASS,
            nsfw_score=nsfw_score,
            text_risk_score=text_score,
            extracted_text=text,
            matched_word=matched,
            reason=f"NSFW {nsfw_score:.3f} <= {NSFW_PASS_THRESHOLD}, no text",
        )

    # Everything else -> enqueue for Layer 2
    return Layer1Result(
        decision=Layer1Decision.ENQUEUE,
        nsfw_score=nsfw_score,
        text_risk_score=text_score,
        extracted_text=text,
        matched_word=matched,
        reason=f"Uncertain: nsfw={nsfw_score:.3f}, text_risk={text_score:.3f}",
    )
