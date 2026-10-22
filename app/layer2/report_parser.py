import json
import re

_DEFAULTS = {
    "nsfw_score": 0.5,
    "nsfw_reason": "",
    "text_risk_score": 0.5,
    "text_reason": "",
    "ai_generated_score": 0.5,
    "ai_generated_reason": "",
    "final_verdict": "UNCERTAIN",
    "overall_reason": "",
}


def _validate(obj: dict) -> dict:
    if not isinstance(obj, dict):
        return _fallback("Non-dict response")
    out = {**_DEFAULTS, **obj}
    for k in ("nsfw_score", "text_risk_score", "ai_generated_score"):
        try:
            out[k] = max(0.0, min(1.0, float(out[k])))
        except (TypeError, ValueError):
            out[k] = 0.5
    if out["final_verdict"] not in ("SAFE", "VIOLATION", "UNCERTAIN"):
        out["final_verdict"] = "UNCERTAIN"
    return out


def _fallback(reason: str) -> dict:
    out = dict(_DEFAULTS)
    out["overall_reason"] = reason
    return out


def _recover_partial(raw: str) -> dict:
    """Extract whatever fields we can from truncated / malformed JSON."""
    out = dict(_DEFAULTS)

    # numeric fields
    for field in ("nsfw_score", "text_risk_score", "ai_generated_score"):
        m = re.search(rf'"{field}"\s*:\s*([0-9]*\.?[0-9]+)', raw)
        if m:
            try:
                out[field] = max(0.0, min(1.0, float(m.group(1))))
            except ValueError:
                pass

    # string fields (closed)
    for field in ("nsfw_reason", "text_reason", "ai_generated_reason", "overall_reason"):
        m = re.search(rf'"{field}"\s*:\s*"([^"\\]*)"', raw)
        if m:
            out[field] = m.group(1)
            continue
        # string that got cut off before the closing quote
        m = re.search(rf'"{field}"\s*:\s*"([^"]*)$', raw, re.DOTALL)
        if m:
            out[field] = m.group(1).strip() + " [truncated]"

    # verdict
    m = re.search(r'"final_verdict"\s*:\s*"(SAFE|VIOLATION|UNCERTAIN)"', raw)
    if m:
        out["final_verdict"] = m.group(1)
    else:
        # infer from whatever score we recovered
        if out["nsfw_score"] >= 0.7 or out["text_risk_score"] >= 0.7:
            out["final_verdict"] = "VIOLATION"
        elif out["nsfw_score"] <= 0.2 and out["text_risk_score"] <= 0.2:
            out["final_verdict"] = "SAFE"

    # keep the truncated flag visible
    if not out["overall_reason"]:
        out["overall_reason"] = "Recovered from truncated/malformed JSON"

    return out


def parse_report(raw_content: str) -> dict:
    if not raw_content or not raw_content.strip():
        return _fallback("Empty response from VLM")

    # 1. direct parse
    try:
        return _validate(json.loads(raw_content))
    except json.JSONDecodeError:
        pass

    # 2. fenced json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
    if m:
        try:
            return _validate(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    # 3. first balanced {...} block
    m = re.search(r"(\{.*\})", raw_content, re.DOTALL)
    if m:
        try:
            return _validate(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    # 4. recover partial fields from broken JSON
    recovered = _recover_partial(raw_content)
    if any(recovered[k] != _DEFAULTS[k] for k in ("nsfw_score", "nsfw_reason")):
        recovered["overall_reason"] = (
            recovered["overall_reason"]
            + f" | raw[:120]={raw_content[:120]!r}"
        )
        return recovered

    return _fallback(f"Could not parse JSON from response: {raw_content[:200]}")