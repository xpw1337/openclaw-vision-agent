# OpenClaw Vision Agent — Product Roadmap

A 4-iteration plan to deliver the Week 1 submission excellently. Scope is fixed at the PRD's Week 1 core — no stretch features. Each iteration is shippable on its own; each later iteration takes the previous one and makes it better. Within an iteration, features are isolated and can be built/tested in any order.

The four iterations correspond to **walking skeleton → spec-complete → robust → polished-and-shipped**.

---

## Iteration 1 — Walking Skeleton

**Goal:** Prove the pipeline end-to-end with the absolute minimum code. Image in, JSON out, displayed somewhere. No annotation, no error handling, no schema rigor. Just one straight line from upload to screen.

**Definition of done:** From a clean clone, `streamlit run app.py` opens a page where uploading a desk photo prints OpenAI's response text. You believe the integration works.

### Features

1. **F1.1 — Project scaffolding**
   - Create the directory tree from PRD §"Project Structure".
   - `.gitignore` (Python defaults + `.env`, `.venv`, `__pycache__`).
   - `.env.example` with `OPENAI_API_KEY=`.
   - `requirements.txt` with the 5 pinned dependencies.
   - Empty `__init__.py` files and `.gitkeep`s.

2. **F1.2 — Minimum vision call** (`core/vision.py`)
   - One function: `analyze_image(image_bytes) -> str`.
   - Resize to ≤2048px, RGBA→RGB, base64 JPEG encode.
   - Call `gpt-4o` with a simple system prompt ("describe this scene as JSON with scene_summary, objects, risks, actions").
   - Return raw `response.choices[0].message.content`. No parsing, no Pydantic yet.

3. **F1.3 — Minimum Streamlit shell** (`app.py`)
   - Title + file uploader (`jpg/jpeg/png/webp`).
   - "Analyze" button → spinner → `st.code(result)` with the raw string.
   - API key read from `.env` via `python-dotenv`. If missing, hard-stop with `st.error`.

4. **F1.4 — Smoke-test commit**
   - Single commit: "iteration 1 — walking skeleton works end-to-end".
   - No GitHub push yet — local repo only.

**What you do NOT have at end of Iteration 1:** structured output, annotation, fallback parsing, real error handling, webcam, README, sample assets, public repo.

---

## Iteration 2 — Spec-Complete

**Goal:** Hit every functional requirement in the PRD. Real Pydantic schema, real annotator, real two-column UI, webcam input. The product now matches the spec, even if rough at the edges.

**Trigger to start:** Iteration 1 demonstrably works on your machine.

### Features (each independent)

1. **F2.1 — Pydantic schema + structured outputs**
   - Define `DetectedObject` and `VisionAnalysis` per PRD §1.
   - Switch `analyze_image` to `client.beta.chat.completions.parse()` with `response_format=VisionAnalysis`.
   - Return a typed `VisionAnalysis` instead of a string.
   - System prompt upgraded per PRD §1: persona, specificity guard, bbox optionality, honesty about uncertainty.

2. **F2.2 — Fallback parser** (`core/parser.py`)
   - `parse_raw_json(raw: str) -> VisionAnalysis` — strips markdown fences, fills missing fields with defaults.
   - `safe_to_dict(analysis) -> dict` — excludes None for clean JSON display.
   - Wired in as the fallback when `response.choices[0].message.parsed` is None.

3. **F2.3 — Pillow annotator — both modes** (`core/annotator.py`)
   - **Bounding-box mode:** semi-transparent rectangles + label-with-confidence text, clamped to [0,1], invalid boxes discarded.
   - **Legend mode (fallback):** top-right numbered list with colored bullets on dark semi-transparent panel.
   - RGBA copy + `Image.alpha_composite` blending.
   - 8-color palette, font scales `max(14, min(w,h)//40)`, `arial.ttf` with `load_default()` fallback.

4. **F2.4 — Webcam input**
   - Radio toggle in `app.py`: "Upload Image" / "Webcam Capture".
   - `st.camera_input()` branch.
   - Same pipeline downstream — input source is abstracted.

5. **F2.5 — Two-column results layout**
   - `st.set_page_config(layout="wide")`.
   - Left: annotated image via `st.image()`.
   - Right: Scene Summary (`st.info`), Detected Objects (markdown list), Risks (one `st.warning` each), Actions (one `st.success` each), Confidence Notes (`st.caption`).
   - Raw JSON in `st.expander` + `st.json` at the bottom.

6. **F2.6 — Public exports** (`core/__init__.py`)
   - Re-export `VisionAnalysis`, `DetectedObject`, `analyze_image`, `annotate_image`, `parse_raw_json`.
   - So `app.py` imports cleanly from `core`.

**What you do NOT have at end of Iteration 2:** comprehensive error handling, EXIF correctness, README, screenshots, GitHub repo. The app works on a happy-path desk photo. Anything else is undefined behavior.

---

## Iteration 3 — Robustness

**Goal:** The app survives every failure case in PRD §5. No raw tracebacks reach the user. Edge-case images render correctly. The prompt produces specific, image-grounded output every time, not generic safety filler.

**Trigger to start:** Iteration 2's happy path is solid.

### Features (each independent)

1. **F3.1 — Full error handling matrix** (PRD §5)
   - Missing `OPENAI_API_KEY` → red banner + `st.stop()` on load.
   - Wrong file type → blocked by `st.file_uploader(type=...)`.
   - Corrupt image → friendly message at `Image.open()`.
   - Tiny image (<50px) → yellow warning, continue.
   - API error (auth/rate/server) → `st.error("Analysis failed: {msg}")`.
   - Content-policy refusal → check `response.choices[0].message.refusal`, raise `ValueError`, show friendly message.
   - Malformed JSON → fallback parser path exercised, partial results rendered.
   - Network timeout → 30s client timeout, clean error.

2. **F3.2 — Image preprocessing hardening**
   - EXIF orientation handling (`ImageOps.exif_transpose`) so phone photos render upright.
   - Resize logic verified on portrait, landscape, square, very-wide panoramas.
   - RGBA, palette (P), grayscale (L) modes all normalized to RGB before encode.

3. **F3.3 — Prompt specificity guard**
   - Refined system prompt with one in-context example of good vs. bad output.
   - Explicit instructions: every `suggested_action` must reference an object visible in `objects`.
   - Confidence notes must mention the actual image (lighting, angle, occlusion) — not boilerplate.

4. **F3.4 — Annotator edge cases**
   - Empty `objects` list → image returned untouched, optional "no objects detected" caption.
   - All-invalid bboxes → graceful fallback to legend mode (not a blank image).
   - Very long labels → truncated with ellipsis to keep the legend readable.
   - Label collision avoidance for bbox mode (don't stack labels on the exact same pixel).

5. **F3.5 — UX states**
   - Empty state before upload: helpful instructions, sample-image hint.
   - Loading state: `st.spinner("Analyzing your workspace...")`.
   - Post-analysis: results stay until next upload/analyze (don't flicker).

**What you do NOT have at end of Iteration 3:** README, architecture doc, sample inputs/outputs, screenshots, GitHub repo. The product works correctly under stress, but the submission package isn't built.

---

## Iteration 4 — Polish & Ship

**Goal:** The submission Spencer actually sees. Excellent README, honest documentation, real sample assets, demo screenshots, public GitHub repo. Every checkbox in the PRD §"Verification Checklist" passes.

**Trigger to start:** Iteration 3 is robust and you've used the app on 3+ real photos without surprises.

### Features (each independent)

1. **F4.1 — README excellence**
   - Title + one-liner.
   - **Quick Start in exactly 4 commands** (clone, install, set key, run).
   - Architecture overview (pipeline text diagram).
   - "What works / what's partial / what would improve with more time" — honest, specific, no hedging.
   - Assumptions & limitations (model hallucinations, bbox inaccuracy, confidence as self-assessment, not safety-critical).
   - Tech stack rationale (Streamlit, gpt-4o, Pillow, Pydantic — one line of *why* each).
   - Sample input/output references with embedded screenshots.

2. **F4.2 — Architecture doc** (`docs/architecture.md`)
   - Pipeline diagram (text/Mermaid).
   - Component responsibilities table (vision / parser / annotator / app).
   - Why each tech choice — same content as README but expanded with tradeoffs considered and rejected.

3. **F4.3 — Sample inputs**
   - 2–3 real desk photos in `sample_inputs/` (your own desk, varied difficulty: clean, cluttered, edge-case lighting).
   - Filenames descriptive: `desk_cluttered_cables.jpg`, `desk_coffee_near_laptop.jpg`.

4. **F4.4 — Sample outputs**
   - Corresponding `.json` files in `sample_outputs/` — actual output captured from a run, not hand-written.
   - Demonstrates the schema for anyone reading the repo without running it.

5. **F4.5 — Demo screenshots**
   - 2–3 PNGs in `assets/`: full app post-analysis, annotated image close-up, error state.
   - Referenced inline in the README.

6. **F4.6 — Verification pass against PRD §"Verification Checklist"**
   - Walk every checkbox manually. Each must pass.
   - Fix anything that doesn't. This is the final QA gate.

7. **F4.7 — Git history cleanup + GitHub push**
   - Review commits — squash noise, ensure messages tell a coherent story.
   - `gh repo create xpw1337/openclaw-vision-agent --public --source=. --push`.
   - Verify the public URL renders the README correctly.
   - Test the Quick Start by cloning into a temp directory yourself.

**Definition of done for the whole project:** the public GitHub URL can be sent to Spencer with zero additional explanation.

---

## Cross-Iteration Notes

- **Ship each iteration.** Don't start N+1 with N broken. Commit at the end of each iteration so you can roll back.
- **Resist scope creep.** If something feels like a mode selector, history, OCR, action envelope, eval harness, or backend abstraction — it's Week 2. Cut it.
- **The point of 4 iterations is not 4× the features — it's 4× the confidence.** The product surface stays the same throughout. Each pass makes it more correct, more honest, more demo-ready.
- **Iteration 1 must look embarrassing.** If it doesn't, you're over-building too early.
