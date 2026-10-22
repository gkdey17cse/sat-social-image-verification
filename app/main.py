import os
import uuid
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image

from app.config import AUTO_START_WORKER, UPLOAD_DIR
from app.layer1.decision import run_layer1
from app.models.schemas import Layer1Decision
from app.queue import publisher
from app.queue.worker import start_background_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    publisher.init_db()
    if AUTO_START_WORKER:
        start_background_worker()
        print("[main] background worker started in-process")
    yield


app = FastAPI(title="Image Moderation Pipeline", lifespan=lifespan)


@app.post("/moderate")
async def moderate(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        image = Image.open(BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Invalid image file")

    filename = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    image.save(path, "JPEG", quality=90)

    result = run_layer1(image)

    if result.decision == Layer1Decision.BLOCK:
        return {
            "status": "blocked",
            "reason": result.reason,
            "layer1": result.model_dump(),
        }
    if result.decision == Layer1Decision.PASS:
        return {
            "status": "safe",
            "reason": result.reason,
            "layer1": result.model_dump(),
        }

    post_id = publisher.publish(path, result.model_dump())
    return {
        "status": "under_review",
        "post_id": post_id,
        "reason": result.reason,
        "layer1": result.model_dump(),
    }


@app.get("/posts/{post_id}")
def get_post(post_id: int):
    post = publisher.get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@app.get("/health")
def health():
    return {"ok": True}
