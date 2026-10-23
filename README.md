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

> **On Apple Silicon (Mac mini, M1/M2/M3/M4):** Ollama uses Metal GPU acceleration by default, so `ollama ps` should report `100% GPU` during inference. Expect **3–10 s per image** for `qwen2.5vl:3b`, versus 20–60 s on CPU-only machines.

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

| Component            | macOS (tested on Mac mini)                           | Windows (tested)                                                             |
| -------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------- |
| Python 3.10+         | `python3 --version` (system Python or pyenv)         | python.org installer or Microsoft Store                                      |
| Homebrew             | `brew --version` (install if missing — see below)    | not required                                                                 |
| Tesseract OCR        | `brew install tesseract tesseract-lang`              | UB-Mannheim `.exe` installer                                                 |
| Ollama (local VLM)   | `brew install --cask ollama` or official `.dmg`      | `irm https://ollama.com/install.ps1 \| iex`                                  |
| Git                  | preinstalled on macOS                                | preinstalled with Git for Windows                                            |

---

## Setup — macOS (Mac mini, primary tested path)

### 0. Install Homebrew (one-time, skip if `brew --version` works)

If `brew --version` prints “command not found”, install Homebrew first:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

At the end of the install, Homebrew prints **Next steps** with three commands. Run them exactly as shown:

```bash
echo >> /Users/<your-user>/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv zsh)"' >> /Users/<your-user>/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv zsh)"
```

Verify:

```bash
brew --version
```

### 1. Clone and create a virtual environment

```bash
git clone <your-repo-url>
cd SOCIAL_MEDIA_IMAGE_Pipeline
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR + language packs

```bash
brew install tesseract
brew install tesseract-lang     # Hindi, Bengali, Gujarati, Tamil, Telugu, etc.
```

Verify (Apple Silicon path is `/opt/homebrew/bin/tesseract`; Intel Mac is `/usr/local/bin/tesseract`):

```bash
which tesseract
tesseract --version
tesseract --list-langs          # should list eng, hin, ben, guj, ...
```

`text_filter.py` auto-detects **all three common paths** (`/opt/homebrew/bin/tesseract`, `/usr/local/bin/tesseract`, `C:\Program Files\Tesseract-OCR\tesseract.exe`) so no manual edit is required across platforms.

### 4. Install Ollama and pull the model

```bash
brew install --cask ollama
```

After the cask finishes, Ollama launches in the background. Open a **new terminal** (or `source ~/.zprofile`) so the CLI is on `PATH`, then:

```bash
ollama --version
ollama pull qwen2.5vl:3b
```

Confirm:

```bash
ollama list
ollama ps       # during inference, should say "100% GPU" on Apple Silicon
```

> **Why the model is not in the repo:** Ollama stores models in `~/.ollama/models` (macOS) or `%USERPROFILE%\.ollama\models` (Windows). Each machine runs `ollama pull` once; the 3.2 GB weights never touch your git repository.

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
API_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_MODEL=qwen2.5vl:3b

# Optional fallback:
# API_PROVIDER=gemini
# GEMINI_API_KEY=...
# GEMINI_MODEL=gemini-3.5-flash-lite
```

---

## Setup — Windows

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

Download the Windows installer:

- **https://github.com/UB-Mannheim/tesseract/wiki** — grab `tesseract-ocr-w64-setup-*.exe`

During install, tick any regional language packs (Hindi, Bengali, etc.). Default path is `C:\Program Files\Tesseract-OCR\tesseract.exe`.

`text_filter.py` probes this path automatically, so **no code edit is needed**.

Verify (optional — if the PATH is broken the code still works):

```powershell
tesseract --version
```

### 4. Install Ollama and pull the model

```powershell
# One-time installer
irm https://ollama.com/install.ps1 | iex
```

Open a **new PowerShell window** (PATH refreshes on restart), then:

```powershell
ollama --version
ollama pull qwen2.5vl:3b
ollama list
ollama ps            # shows CPU/GPU split — "100% GPU" means acceleration is active
```

If you have an NVIDIA GPU, keep drivers up to date; Ollama picks up CUDA automatically.

### 5. Configure environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` with the same content as the macOS section.

---

## Setup — Linux (Debian/Ubuntu, untested)

```bash
# Tesseract (engine + language packs)
sudo apt install -y tesseract-ocr tesseract-ocr-hin tesseract-ocr-ben

# Ollama
curl -fsSL https://ollama.com/install.sh | sh

# App
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5vl:3b
cp .env.example .env
# edit .env
```

---

## Running

Three terminals, all from the project root, all with the venv active.

**macOS / Linux:**

```bash
# Terminal 1 — API + Layer 1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Layer 2 worker
python -m app.queue.worker

# Terminal 3 — UI
streamlit run streamlit_app.py
```

**Windows (PowerShell):**

```powershell
uvicorn app.main:app --reload --port 8000
python -m app.queue.worker
streamlit run streamlit_app.py
```

Open http://localhost:8501, upload an image, and watch the pipeline in action.

> The worker is **required**. Without it, queued posts sit at `under_review` forever because nobody polls the queue.

---

## Performance tuning (Ollama)

If image analysis is slow, apply these in order:

1. **Resize before encoding.** Already handled in `openrouter_client._encode_image` — caps the image at 1024 px on the long edge, cutting vision tokens by 90 %+.
2. **Keep the model warm.** Set `OLLAMA_KEEP_ALIVE` once:
   - **macOS / Linux** (current session):
     ```bash
     export OLLAMA_KEEP_ALIVE=-1
     ```
     Permanent (append to `~/.zshrc` or `~/.zprofile`):
     ```bash
     echo 'export OLLAMA_KEEP_ALIVE=-1' >> ~/.zshrc
     ```
   - **Windows** (current session):
     ```powershell
     $env:OLLAMA_KEEP_ALIVE = "-1"
     ```
     Permanent: System Properties → Environment Variables → New → `OLLAMA_KEEP_ALIVE=-1`.
3. **Worker warm-up.** `worker.py` sends a small dummy image on startup so the first real upload does not pay the cold-load cost.
4. **Check the processor.** During inference, run `ollama ps`:
   - `100% GPU` — Apple Silicon Metal, or CUDA on Windows — optimal.
   - `100% CPU` — no acceleration. On macOS this means Ollama was started under Rosetta or the Apple Silicon build failed; reinstall via `brew install --cask ollama`.
5. **Downgrade the model** if speed is still not enough:
   ```bash
   ollama pull moondream       # 1.7 GB, ~3-10 s/image, weaker on text/AI-detection
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
- The Ollama model directory (it is outside the repo anyway)

If you ever want to reset state, **stop uvicorn and the worker first**, then:

- **macOS / Linux:**
  ```bash
  rm -f moderation.db
  rm -rf uploads/*
  ```
- **Windows:**
  ```powershell
  Remove-Item moderation.db
  Remove-Item uploads\* -Force
  ```

> Deleting `moderation.db` while uvicorn or the worker is running fails on both platforms because SQLite holds the file open. `Ctrl+C` in both terminals first.

---

## Testing Layer 2 in isolation

Save as `test_ollama.py` in the project root, activate the venv, and run:

```python
# test_ollama.py
import os
from PIL import Image
from app.layer2.openrouter_client import analyze_image

files = [f for f in os.listdir("uploads") if f.lower().endswith((".jpg", ".jpeg", ".png"))]
if not files:
    raise SystemExit("Upload an image via Streamlit first.")

res = analyze_image(Image.open(os.path.join("uploads", files[0])))
print("RAW:\n", res["raw"])
print("\nUSAGE:", res["usage"])
```

Run it:

```bash
# macOS / Linux
python test_ollama.py

# Windows
python test_ollama.py
```

First call is the slowest (model loads into memory); subsequent calls should be several seconds on GPU, 20–60 s on CPU.

---

## Common issues

| Symptom                                           | Fix (macOS)                                                                                                       | Fix (Windows)                                                                                                       |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `brew: command not found`                         | Install Homebrew (Setup §0) then run the three “Next steps” commands                                              | N/A                                                                                                                 |
| `ollama: command not found` after install         | Open a **new** terminal, or `source ~/.zprofile`                                                                  | Open a **new** PowerShell window                                                                                    |
| `tesseract: not recognized`                       | `which tesseract` should show `/opt/homebrew/bin/tesseract`; if not, reinstall via brew                            | Reinstall the UB-Mannheim `.exe`; `text_filter.py` auto-detects `C:\Program Files\Tesseract-OCR\tesseract.exe`      |
| Missing regional languages                        | `brew install tesseract-lang`                                                                                     | Tick language packs during the installer, or rerun the installer                                                    |
| `opennsfw-onnx import failed`                     | `pip install --upgrade opennsfw-onnx onnxruntime`                                                                 | Same                                                                                                                |
| `GEMINI 400 INVALID_ARGUMENT`                     | Remove `response_format` / `reasoning_effort` from the payload — Gemini-only, and rejected for some values        | Same                                                                                                                |
| `429 Too Many Requests`                           | Cloud provider daily cap; switch to `API_PROVIDER=ollama`                                                         | Same                                                                                                                |
| Layer 2 stuck at `needs_review`                   | Requeue: `python -c "import sqlite3; c=sqlite3.connect('moderation.db'); c.execute(\"UPDATE posts SET status='under_review' WHERE status='needs_review'\"); c.commit()"` | Same command                                                                                                        |
| Worker loops on the same post                     | Ensure `worker._process_one` maps **every** verdict to a terminal status (`removed` / `safe` / `needs_review`), never back to `under_review` | Same                                                                                                                |
| `2–3 minutes per image`                           | `ollama ps` should say `100% GPU` on Apple Silicon; if it says CPU, reinstall Ollama via brew cask                  | `ollama ps` should say `100% GPU` if NVIDIA; else update drivers                                                    |
| `Remove-Item : ... being used by another process` | `Ctrl+C` uvicorn + worker, then `rm -f moderation.db`                                                             | `Ctrl+C` both, then `Remove-Item moderation.db`                                                                     |

---

## License

Internal project. Add your own license header here before making the repo public.
