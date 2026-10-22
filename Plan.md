## Final Architecture (Refined, Brief)

### Layer 1 — In-Process Fast Gate (synchronous, CPU only)

- **NSFW branch**: `opennsfw-onnx` bundled as a Python library, loaded once at app startup. No GPU, no separate service.
- **Text branch**: lightweight OCR (Tesseract) + lexicon/small classifier, runs in the same process.
- **Decision**:
  - NSFW ≥ 0.95 → block immediately
  - NSFW ≤ 0.05 and text clean → pass immediately
  - everything else → publish with "under review" tag, enqueue for Layer 2

### Layer 2 — OpenRouter API VLM (asynchronous, background worker)

- **Model**: `nvidia/nemotron-3.5-content-safety:free` via OpenRouter API key.
- **No self-hosted GPU, no vLLM, no model weights on disk.** Just an HTTP client.
- **Per queue item**, send one request with the image (base64 data URI) and a prompt asking for:
  - NSFW risk
  - Offensive/hateful text risk (including regional languages)
  - AI-generated verdict + confidence
  - Reason for each
- **Decision**: confirmed violation → take down post + show reason; safe → clear "under review" tag.
- Runs one item at a time from a durable queue; network latency is acceptable because it is background.

### Flow

```
User posts image
   │
   ▼
Layer 1 (in-process, fast)
   ├── NSFW ≥ 0.95 → block
   ├── NSFW ≤ 0.05 & text clean → pass
   └── else → publish "under review" + enqueue
                    │
                    ▼
            Background worker
                    │
                    ▼
       Layer 2: OpenRouter VLM call
       → structured report (NSFW, text, AI-gen, reasons)
                    │
                    ├── violation → takedown + reason
                    └── safe → clear tag
```

### Key Changes from Previous Plan

- Removed self-hosted Shieldstral, vLLM, Docker GPU service, GGUF quantization concerns.
- Layer 2 is now a single HTTP client module with an API key in environment variables.
- Everything else (publish-first async, durable queue, explainable takedowns) stays the same.

---

## Final Directory Structure

```
project-root/
├── app/
│   ├── main.py                     # FastAPI/Flask entry point
│   ├── config.py                   # env vars, thresholds, API keys
│   │
│   ├── layer1/
│   │   ├── __init__.py
│   │   ├── nsfw_filter.py          # opennsfw-onnx wrapper (singleton at startup)
│   │   ├── text_filter.py          # OCR + lexicon/lightweight classifier
│   │   └── decision.py             # 0.95 / 0.05 rule logic → BLOCK/PASS/ENQUEUE
│   │
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── publisher.py            # enqueue image reference (Redis/DB-backed)
│   │   └── worker.py               # background consumer, calls Layer 2
│   │
│   ├── layer2/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py    # HTTP client to OpenRouter chat/completions
│   │   ├── prompts.py              # moderation question templates
│   │   └── report_parser.py        # parse VLM output → structured report
│   │
│   └── models/
│       └── schemas.py              # Pydantic models: Report, Decision, Verdict
│
├── tests/
│   ├── test_layer1.py
│   ├── test_layer2.py              # mocked OpenRouter responses
│   └── fixtures/
│       └── sample_images/
│
├── scripts/
│   ├── calibrate_thresholds.py     # tune 0.95/0.05 on labeled sample
│   └── replay_queue.py             # re-run enqueued items for debugging
│
├── .env.example                    # OPENROUTER_API_KEY, thresholds, queue URL
├── requirements.txt                # opennsfw-onnx, pytesseract, fastapi, redis, httpx
├── docker-compose.yml              # app + worker + redis (no GPU service)
└── README.md
```

### What Goes Where

- **`app/layer1/`** — pure in-process code; model loaded once, no network calls.
- **`app/layer2/`** — only HTTP client + prompt/parser; API key read from `.env`.
- **`app/queue/`** — durable queue between the two layers; worker runs as a separate container/process.
- **`docker-compose.yml`** — three services: `app` (API + Layer 1), `worker` (Layer 2 consumer), `redis` (queue). No GPU, no model server.

### Final Notes

- Layer 1 thresholds (0.95 / 0.05) are config values, not code — tune via `scripts/calibrate_thresholds.py`.
- Layer 2 prompts live in `prompts.py` so you can change strictness or add AI-generated detection wording without touching client code.
- OpenRouter model ID stays in `config.py` as `MODEL_ID = "nvidia/nemotron-3.5-content-safety:free"` — swap to another VLM by changing one line.
- Every Layer 2 report is logged (score + reason) for threshold tuning and audit.

This is the finalized design: two layers, no intermediate stage, Layer 1 in-process, Layer 2 as an API-key HTTP call, async publish-first flow with explainable takedowns.