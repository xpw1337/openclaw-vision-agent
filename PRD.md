# OpenClaw Vision Agent — Product Requirement Document & Build Plan

## Context

Arijit has a take-home assignment from Spencer Brown (CEO, LVL3.ai) due in ~5 days. The task: build an "OpenClaw Vision Agent" prototype — a Streamlit web app where a user uploads an image and gets structured AI analysis back. Demo mode: **Desk Safety Assistant** (upload a desk photo, get safety risks and action items). Week 1 core only — no stretch features.

The evaluator values: working demo, honest communication, clean README, structured output quality, and modular code. "Not looking for perfection; looking for effort."

## Environment (Verified)

| Component | Status |
|-----------|--------|
| Python | 3.14.3 (exceeds 3.10+ requirement) |
| pip | 25.3 |
| git | 2.53.0 |
| gh CLI | 2.87.3, authenticated as `xpw1337` |
| Target dir | `C:\lvl3ai\openclaw-vision-agent` — does not exist yet |

All packages (streamlit, google-genai, Pillow, pydantic) are confirmed compatible with Python 3.14.

## Architecture

```
Image Input (upload / webcam)
  → Validation (format, size)
  → Base64 Encoding (JPEG, max 2048px)
  → Gemini 3.5 Flash (structured output via Pydantic schema)
  → Pydantic Validation (with fallback parser)
  → Pillow Annotation (bounding boxes + legend overlay)
  → Streamlit Display (two-column: annotated image | structured results)
```

## Project Structure

```
openclaw-vision-agent/
├── app.py                    # Streamlit UI — input, display, error states
├── core/
│   ├── __init__.py           # Public exports
│   ├── vision.py             # Pydantic models, image encoding, Gemini API call, system prompt
│   ├── parser.py             # Fallback JSON parsing, dict conversion
│   └── annotator.py          # Pillow annotation — bounding boxes + text legend
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── docs/
│   └── architecture.md
├── sample_inputs/
│   └── .gitkeep
├── sample_outputs/
│   └── .gitkeep
└── assets/
    └── .gitkeep
```

## Dependencies (requirements.txt)

```
streamlit>=1.57.0
google-genai>=1.0.0
Pillow>=12.0.0
pydantic>=2.13.0
python-dotenv>=1.2.0
```

Pin to latest compatible versions at build time. All confirmed compatible with Python 3.14.

## File-by-File Spec

### 1. `core/vision.py` — The Critical Path

**Pydantic models:**
- `DetectedObject`: `label: str`, `confidence: float`, `bbox: list[float] | None` (normalized 0-1, optional)
- `VisionAnalysis`: `scene_summary: str`, `objects: list[DetectedObject]`, `risks_or_opportunities: list[str]`, `suggested_actions: list[str]`, `confidence_notes: str`

**API call pattern — Gemini Structured Outputs:**
- Use `client.models.generate_content()` with `config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=VisionAnalysis)`
- Passing the Pydantic class as `response_schema` guarantees valid JSON matching the schema
- Image sent as inline bytes via `types.Part.from_bytes(data=jpeg, mime_type="image/jpeg")` in the `contents` list
- System prompt sent via `system_instruction` config field (not prepended to user content)
- `temperature: 0.2` for consistency, `max_output_tokens: 2000`, `http_options=types.HttpOptions(timeout=30_000)` (30s in ms)

**Image preprocessing:**
- Resize to max 2048px (longest edge) to control token cost
- Convert RGBA → RGB before JPEG encoding
- JPEG-encode at quality 90 and pass raw bytes (Gemini accepts inline bytes directly; no base64 wrapper needed)

**System prompt strategy:**
- Establish persona: "You are OpenClaw Vision Agent, operating in Desk Safety Assistant mode"
- Instruct specificity: "Be specific to THIS image — never give generic advice not grounded in what you see"
- Bounding box handling: request as optional, provide format (normalized 0-1), explicitly say "omit if uncertain"
- Honesty: "Be honest about uncertainty. These are estimates, not precise measurements."
- No JSON formatting instructions in prompt — the Pydantic schema handles that via structured outputs

**Error handling:**
- Check `response.prompt_feedback.block_reason` and `candidate.finish_reason` — raise ValueError if blocked by safety / content policy
- If `response.parsed` is None, fall back to raw `response.text` → `parser.py`
- 30-second timeout on the Gemini client via `HttpOptions(timeout=30_000)`

### 2. `core/parser.py` — Defense Layer

- `parse_raw_json(raw: str) -> VisionAnalysis`: strips markdown fences, parses JSON, constructs VisionAnalysis with sensible defaults for missing fields
- `safe_to_dict(analysis: VisionAnalysis) -> dict`: converts to dict excluding None values (for clean JSON display)

### 3. `core/annotator.py` — Visual Output

**Two annotation modes:**
- **Objects with bounding boxes:** Semi-transparent colored rectangles + labels with confidence % above each box. Clamp coords to [0,1], discard invalid boxes.
- **Objects without bounding boxes (fallback):** Legend panel in top-right corner — numbered list of objects with colored bullets and confidence scores. Dark semi-transparent background for readability.

**Technical approach:**
- Work on RGBA copy, use separate overlay layer for semi-transparency
- `Image.alpha_composite()` for clean blending
- Font size scales with image: `max(14, min(w,h) // 40)`
- Fall back to `ImageFont.load_default()` if `arial.ttf` not found (Windows should have it)
- 8-color palette for distinct object coloring

### 4. `app.py` — Streamlit UI

**Layout:**
- `st.set_page_config(layout="wide")` for two-column room
- Title: "OpenClaw Vision Agent" + tagline "Desk Safety Assistant"
- API key check on load — `st.error` + `st.stop()` if missing

**Input section:**
- Radio toggle: "Upload Image" / "Webcam Capture"
- Upload: `st.file_uploader(type=["jpg","jpeg","png","webp"])`
- Webcam: `st.camera_input()`
- Validation: try `Image.open()`, warn on images < 50px

**Analysis:**
- `st.button("Analyze Workspace", type="primary")`
- `st.spinner()` during API call
- try/except → `st.error()` on failure

**Output — two columns:**
- Left: annotated image via `st.image()`
- Right: Scene Summary (`st.info`), Detected Objects (markdown list), Risks (`st.warning` for each), Actions (`st.success` for each), Confidence Notes (`st.caption`), Raw JSON (`st.expander` + `st.json`)

### 5. Error Handling Matrix

| Error | Location | User Experience |
|-------|----------|-----------------|
| Missing GEMINI_API_KEY | app.py load | Red banner, app stops |
| Wrong file type | st.file_uploader filter | File rejected at widget |
| Corrupt image | Image.open() in app.py | "Could not open this file as an image" |
| Tiny image (<50px) | Size check in app.py | Yellow warning, analysis proceeds |
| API error (auth/rate/server) | try/except in app.py | "Analysis failed: {error}" |
| Content / safety block | vision.py block_reason check | "Image could not be analyzed due to content policy" |
| Malformed JSON | parser.py fallback | Partial results with defaults |
| Network timeout | Gemini client 30s timeout | "Analysis failed: Connection timed out" |

### 6. `README.md`

Must include (evaluator checks this):
- Project title + one-liner
- Quick Start: `git clone`, `pip install -r requirements.txt`, set GEMINI_API_KEY, `streamlit run app.py` — 4 commands
- Architecture overview with pipeline description
- What works / what's partial / what would improve with more time
- Assumptions & limitations (model hallucinations, bbox inaccuracy, confidence scores are estimates, not safety-critical)
- Sample input/output references
- Tech stack rationale (Streamlit: fast prototyping; Gemini 3.5 Flash: strong multimodal + native spatial grounding + structured outputs at low cost; Pillow: lightweight annotation; Pydantic: type safety)

### 7. `docs/architecture.md`

Short document: pipeline diagram (text), component responsibilities, why each tech choice.

## Known Limitations to Document Honestly

1. **Bounding boxes are model estimates, not object detection results.** They may be inaccurate or missing entirely. This is inherent to using a multimodal LLM vs. a dedicated detector like YOLO.
2. **Confidence scores are the model's self-assessment**, not calibrated probabilities.
3. **Not for safety-critical decisions.** This is a prototype demo.
4. **Single image analysis only** — no video, no multi-frame, no streaming.
5. **Webcam requires HTTPS** in production (localhost works for dev).

## What NOT to Build

- No Week 2 stretch features (mode selector, history, OCR, action envelope)
- No Docker, CI/CD, database
- No custom model training or fine-tuning
- No API keys in the repo

## Build Order

1. Create directory structure + boilerplate files (`.gitignore`, `.env.example`, `requirements.txt`)
2. `core/vision.py` — Pydantic models + API call (test standalone)
3. `core/parser.py` — fallback parsing
4. `core/annotator.py` — Pillow annotation (test with hardcoded data)
5. `core/__init__.py` — exports
6. `app.py` — wire everything, test end-to-end
7. Error handling polish
8. `README.md` + `docs/architecture.md`
9. Sample inputs/outputs + screenshots
10. Git init + GitHub push (`gh repo create xpw1337/openclaw-vision-agent --public --source=. --push`)

## Verification Checklist

- [ ] `pip install -r requirements.txt` works cleanly
- [ ] `streamlit run app.py` launches without errors (with GEMINI_API_KEY set)
- [ ] Upload a desk photo → specific structured JSON output
- [ ] Annotated image displays with labels/boxes
- [ ] Upload a .txt file → rejected by uploader
- [ ] Tiny image → yellow warning shown
- [ ] Missing API key → red error on load
- [ ] Raw JSON expander works
- [ ] README has clear 4-step run instructions
- [ ] `.gitignore` excludes `.env`, `__pycache__`, `.venv`
- [ ] Code is modular (vision.py, parser.py, annotator.py are separate)
- [ ] GitHub repo created and pushed

## User Action Required

The user needs to provide 2-3 desk photos for `sample_inputs/` and demo screenshots. These can be taken during testing.

## Estimated Effort

~400 lines of Python, ~140 lines of documentation. 3-4 hours of focused implementation.
