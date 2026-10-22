# Image Moderation Pipeline

Two-layer cascaded moderation for uploaded images.

- **Layer 1 — Fast in-process gate (synchronous, CPU only)**
  - NSFW: [`opennsfw-onnx`](https://pypi.org/project/opennsfw-onnx/) (ResNet-50, ~22 MB)
  - Text: Tesseract OCR + multilingual offensive-word lexicon
  - `NSFW ≥ 0.95` → **BLOCK** immediately
  - `NSFW ≤ 0.15` AND no extracted text → **PASS** immediately
  - Everything else → publish with "under review" tag and enqueue for Layer 2

- **Layer 2 — Background VLM worker (asynchronous)**
  - Sends each queued image to a vision-language model, which returns a single JSON report:
    NSFW score + reason, text-risk score + reason, AI-generated score + reason, final verdict.
  - `VIOLATION` → post removed with a user-visible reason
  - `SAFE` → tag cleared
  - `UNCERTAIN` → flagged `needs_review` for manual moderation
  - **Runs as a separate process**, so users are never blocked

- **Streamlit UI** for manual upload and end-to-end testing.

---

## Provider options for Layer 2

The VLM is swappable by setting `API_PROVIDER` in `.env`:

| Provider           | Env value    | Pros                                         | Cons                                                  |
| ------------------ | ------------ | -------------------------------------------- | ----------------------------------------------------- |
| **Ollama (local)** | `ollama`     | No API key, no rate limits, private, offline | Slow on CPU (20–60 s/image); needs a GPU for sub-10 s |
| **Google Gemini**  | `gemini`     | Fast, generous free tier (~1,500 req/day)    | Requires API key                                      |
| **OpenRouter**     | `openrouter` | Many model options                           | Free tier is 50 req/day; frequently rate-limited      |

The default in `.env.example` is **Ollama** — fully local, works without any account.

---

## Repository layout

```
project-root/
├── app/
│   ├── config.py                 # env loading, provider selection, thresholds
│   ├── main.py                   # FastAPI: /moderate, /posts/{id}, /health
│   ├── models/schemas.py         # Pydantic models
│   ├── layer1/
│   │   ├── nsfw_filter.py        # opennsfw-onnx wrapper
│   │   ├── text_filter.py        # Tesseract OCR + offensive-word lexicon
│   │   └── decision.py           # block / pass / enqueue logic
│   ├── layer2/
│   │   ├── prompts.py            # moderation question template
│   │   ├── openrouter_client.py  # VLM client (Ollama/Gemini/OpenRouter)
│   │   └── report_parser.py      # parses + repairs VLM JSON output
│   └── queue/
│       ├── publisher.py          # SQLite queue
│       └── worker.py             # background consumer
├── streamlit_app.py              # test UI
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

`uploads/`, `moderation.db`, `venv/`, and `.env` are **not** in the repo — they are created on first run and are per-machine.

---

## Prerequisites

- **Python 3.10+**
- **Tesseract OCR** (OS-level binary — NOT a pip package)
- **Ollama** (if using the local provider)

---

## Setup — Windows (tested)

### 1. Clone and create a virtual environment

```powershell
git clone <your-repo-url>
cd SOCIAL_MEDIA_IMAGE_Pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 3. Install Tesseract OCR

Download and run the official Windows installer:

- **https://github.com/UB-Mannheim/tesseract/wiki** — grab `tesseract-ocr-w64-setup-*.exe`

During install, tick any regional language packs you need (Hindi, Bengali, etc.).

Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`.

> `pip install pytesseract` does **not** install Tesseract itself. The `text_filter.py` module already probes the common install locations automatically.

Verify:

```powershell
tesseract --version
```

If this fails, you can skip this check — `text_filter.py` will still find the binary via the hardcoded path.

### 4. Install Ollama and pull the model

```powershell
# One-time installer
irm https://ollama.com/install.ps1 | iex

# In a NEW PowerShell window (PATH refreshes on restart)
ollama pull qwen2.5vl:3b
```

Confirm:

```powershell
ollama list
ollama ps            # shows CPU/GPU split during inference
```

If you have an NVIDIA GPU, keep drivers up to date — Ollama picks up CUDA automatically. `ollama ps` should show `100% GPU` when acceleration is active.

> The model lives in `~/.ollama/models`, **not** in this repo. Every device runs `ollama pull` once; the repo stays small.

### 5. Configure environment

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
API_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_MODEL=qwen2.5vl:3b

# Uncomment and fill in if you want Gemini or OpenRouter fallback:
# API_PROVIDER=gemini
# GEMINI_API_KEY=...
# GEMINI_MODEL=gemini-3.5-flash-lite
```

---

## Setup — Linux / macOS

```bash
# Tesseract
sudo apt install tesseract-ocr          # Ubuntu/Debian
brew install tesseract                  # macOS

# Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Then the same steps as Windows:
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5vl:3b
cp .env.example .env
# edit .env, then run
```

---

## Running

Three terminals, all from the project root, all with the venv active:

```powershell
# Terminal 1 — API + Layer 1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Layer 2 worker
python -m app.queue.worker

# Terminal 3 — UI
streamlit run streamlit_app.py
```

Open http://localhost:8501, upload an image, and watch the pipeline in action.

> The worker is **required**. Without it, queued posts sit at `under_review` forever because nobody polls the queue.

---

## Performance tuning (Ollama)

If image analysis is slow, apply these in order:

1. **Resize before encoding.** Already handled in `openrouter_client._encode_image` — caps the image at 1024 px on the long edge, cutting vision tokens by 90 %+.
2. **Keep the model warm.** Set once per session:
   ```powershell
   $env:OLLAMA_KEEP_ALIVE = "-1"
   ```
   Or set it permanently in Windows → System Properties → Environment Variables.
3. **Worker warm-up.** `worker.py` sends a small dummy image on startup so the first real upload does not pay the cold-load cost.
4. **Check the processor.** During inference, run `ollama ps`. `100% CPU` means no GPU — GPU acceleration is the single largest speedup.
5. **Downgrade the model** if CPU-only speed is not enough:
   ```powershell
   ollama pull moondream       # 1.7 GB, ~3-10 s/image on CPU, weaker on text/AI-detection
   ```
   Then set `OLLAMA_MODEL=moondream:latest` in `.env` and restart the worker.

---

## Repository hygiene

`.gitignore` (already in the repo) excludes:

```
venv/
__pycache__/
*.pyc
.env
uploads/
moderation.db
*.log
.ollama/
```

**Never commit**:

- `.env` (contains API keys)
- `uploads/` (user images)
- `moderation.db` (runtime state)
- The Ollama model directory (it's outside the repo anyway)

If you ever want to reset state: stop uvicorn and the worker, then `Remove-Item moderation.db`, and delete `uploads/*`.

---

## Testing Layer 2 in isolation

```python
# test_ollama.py — run from project root, venv active
import os
from PIL import Image
from app.layer2.openrouter_client import analyze_image

files = [f for f in os.listdir("uploads") if f.lower().endswith((".jpg", ".jpeg", ".png"))]
if not files:
    raise SystemExit("Upload an image via Streamlit first.")
res = analyze_image(Image.open(os.path.join("uploads", files[0])))
print(res["raw"])
```

First call will be the slowest (model loads); subsequent calls should be several seconds on GPU, 20–60 s on CPU.

---

## Common issues

| Symptom                         | Fix                                                                                                                                                                       |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `opennsfw-onnx import failed`   | `pip install --upgrade opennsfw-onnx onnxruntime`                                                                                                                         |
| `tesseract: not recognized`     | Reinstall Tesseract, or set `pytesseract.pytesseract.tesseract_cmd` in `text_filter.py`                                                                                   |
| `GEMINI 400 INVALID_ARGUMENT`   | Remove `response_format` / `reasoning_effort` from the payload; they are Gemini-only and Gemini rejects some values                                                       |
| `429 Too Many Requests`         | You're on a cloud provider's free-tier daily cap. Switch to `API_PROVIDER=ollama`                                                                                         |
| Layer 2 stuck at `needs_review` | Re-queue: `python -c "import sqlite3; c=sqlite3.connect('moderation.db'); c.execute(\"UPDATE posts SET status='under_review' WHERE status='needs_review'\"); c.commit()"` |
| Worker loops on the same post   | Old bug; ensure `worker._process_one` maps every verdict to a terminal status (`removed`/`safe`/`needs_review`), never back to `under_review`                             |
| `2–3 minutes per image`         | Check `ollama ps` for CPU-only; apply the performance tuning section above                                                                                                |

---

## License

Internal project. Add your own license header here before making the repo public.
