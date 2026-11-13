# PROJECT CONTEXT (save as GEMINI.md)

What it is: a book-grounded electrical/electronics/computer-architecture tutor. Students ask doubts; answers come ONLY from our indexed books, with page citations. For "explain topic / teach me / explain deeply" requests the user clicks a video button and gets a 3-4 minute narrated animated video.

Environment: Windows 11, PowerShell, Python 3.13 in `.venv`, Vite + React frontend. Give PowerShell commands only (no bash, no heredocs, no "source"). Run commands from the `ee-tutor` folder.

Layout:
- `api.py`: FastAPI (chat, figure, page, video endpoints). Video: POST `/api/video` returns `job_id`; GET `/api/video/{id}` is polled every 2 s and returns status, title, seconds, error, url.
- `core/tutor.py`: `respond()`, `retrieve()`, video planning and job tracking.
- `core/prompts.py`: `build_system(level)`, the tutor system prompt with a JSON output contract.
- `core/llm.py`: Gemini wrapper, `generate(system, user)`, `llm_ready()`.
- `core/retrieval/hybrid.py`: dense + BM25 + rerank; loads full chunk dicts from `data/processed/*.jsonl`.
- `core/retrieval/index.py`: incremental Chroma indexing.
- `core/ingestion/`: `auto_add.py`, `ingest_pdf.py` (per-page OCR fallback), `topics.py`, `manifest.py`, `chunk.py`.
- `core/video/`: `lesson_plan.py`, `templates.py`, `animate.py`.
- `core/web_search.py`: Tavily fallback, always labeled "not from your sources".
- `frontend/src`: `App.jsx` and components `Composer`, `Message`, `VideoCard`, `Sidebar`.
- `sources.yaml`, `data/raw`, `data/processed`, `data/index` (gitignored).

## Hard rules

1. **Grounding:** Factual content comes only from retrieved book chunks. Never add facts from model memory in book mode.
2. **Animation architecture:** LLMs never write raw HTML, JS or Manim code. They output JSON that picks a template plus parameters, and our code draws the animation. Plot values come from computed data (numpy), never invented by the LLM.
3. **Secrets:** Only via environment variables (`GEMINI_API_KEY`, `GEMINI_MODEL`, `TAVILY_API_KEY`). Never hardcode or print them. `.env` stays gitignored.
4. **Backward compatibility:** Keep API response shapes backward compatible with the existing React frontend.
5. **User data:** Never delete or overwrite user data in `data/` (`chats.json`, index, processed chunks).
6. **Verification:** Every phase ends with tests or a runnable check, plus the exact PowerShell commands to verify.

## Known quirks (do not remove)

- `pyttsx3` truncates long text, so TTS runs per sentence and the parts are concatenated.
- Frames are piped to ffmpeg instead of written as thousands of PNGs, because Windows antivirus makes per-file writes slow.
- Chroma may lock if the backend is running during indexing (suspected).
- OCR runs only on pages with no text layer.

## Known bugs to fix

- `retrieve()` in `core/tutor.py` compares `chunk["page"]` to integers, but some chunks may have `page=None`. Guard it.
- `index.py` records a source as indexed even when it produced 0 chunks. Don't record those; print a warning.
