import time
import threading

from PIL import Image

from app.queue import publisher
from app.layer2.openrouter_client import analyze_image
from app.layer2.report_parser import parse_report

_stop = threading.Event()


def _process_one(post_id: int, image_path: str):
    try:
        image = Image.open(image_path).convert("RGB")
        raw = analyze_image(image)
        report = parse_report(raw["raw"])
    except Exception as e:
        print(f"[worker] post {post_id} EXCEPTION: {type(e).__name__}: {e}")
        report = {
            "nsfw_score": 0.5,
            "nsfw_reason": str(e),
            "text_risk_score": 0.5,
            "text_reason": str(e),
            "ai_generated_score": 0.5,
            "ai_generated_reason": str(e),
            "final_verdict": "UNCERTAIN",
            "overall_reason": f"Layer 2 error: {type(e).__name__}: {e}",
        }

    verdict = report.get("final_verdict", "UNCERTAIN")
    # EVERY verdict must move to a terminal status, never back to 'under_review'
    status = {
        "VIOLATION": "removed",
        "SAFE": "safe",
        "UNCERTAIN": "needs_review",
    }.get(verdict, "needs_review")

    publisher.update_status(post_id, status, report)
    reason = report.get("overall_reason", "")[:120]
    print(f"[worker] post {post_id} -> {status} ({verdict}) | {reason}")


def run_worker(poll_interval: float = 3.0):
    publisher.init_db()
    print("[worker] started. polling for posts...")
    while not _stop.is_set():
        try:
            rows = publisher.get_pending(limit=5)
            if not rows:
                time.sleep(poll_interval)
                continue
            for post_id, image_path, _ in rows:
                if _stop.is_set():
                    break
                _process_one(post_id, image_path)
        except Exception as e:
            print(f"[worker] loop error: {e}")
            time.sleep(poll_interval)
    print("[worker] stopped.")


def start_background_worker(poll_interval: float = 3.0) -> threading.Thread:
    t = threading.Thread(target=run_worker, args=(poll_interval,), daemon=True)
    t.start()
    return t


def stop_background_worker():
    _stop.set()


if __name__ == "__main__":
    run_worker()
