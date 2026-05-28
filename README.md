# OpenClaw Vision Agent

**Give OpenClaw eyes.** A prototype vision agent that analyzes workspace images, identifies objects and safety risks, and suggests practical actions — built as a Desk Safety Assistant demo.

Built for [LVL3.ai](https://lvl3.ai) / Claw.dius Maximus — Level 3 automation that understands objectives and adapts intelligently.

## Quick Start

```bash
git clone https://github.com/xpw1337/openclaw-vision-agent.git
cd openclaw-vision-agent
pip install -r requirements.txt
```

Create a `.env` file with your Gemini API key:

```
GEMINI_API_KEY=your-api-key-here
```

Run the app:

```bash
streamlit run app.py
```

## What It Does

1. **Upload** a photo of your desk/workspace (or capture via webcam)
2. **Analyze** — the image is sent to Google's Gemini 3.5 Flash with a structured prompt
3. **Results** — structured JSON output with:
   - Scene summary
   - Detected objects with confidence scores
   - Safety risks and opportunities
   - Practical suggested actions
   - Honest confidence notes
4. **Annotated image** — original image overlaid with object labels, bounding boxes (when available), and a visual legend

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

### Component Responsibilities

| Module | File | Role |
|--------|------|------|
| Vision | `core/vision.py` | Pydantic models, image encoding, Gemini API call, system prompt |
| Parser | `core/parser.py` | Fallback JSON parsing, markdown fence stripping, dict conversion |
| Annotator | `core/annotator.py` | Pillow-based image annotation — bounding boxes + text legend |
| App | `app.py` | Streamlit UI — input handling, layout, display, error states |

## Project Structure

```
openclaw-vision-agent/
├── app.py
├── core/
│   ├── __init__.py
│   ├── vision.py
│   ├── parser.py
│   └── annotator.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── PRD.md
├── docs/
│   └── architecture.md
├── sample_inputs/
│   └── .gitkeep
├── sample_outputs/
│   └── .gitkeep
└── assets/
    └── .gitkeep
```

## Example Output

```json
{
  "scene_summary": "A desk with a laptop, notebook, coffee cup, cables, and paper receipts.",
  "objects": [
    {"label": "laptop", "confidence": 0.94},
    {"label": "coffee cup", "confidence": 0.87},
    {"label": "cables", "confidence": 0.72}
  ],
  "risks_or_opportunities": [
    "Liquid is close to electronics.",
    "Cables may create clutter or snag risk."
  ],
  "suggested_actions": [
    "Move the coffee cup away from the laptop.",
    "Bundle or reroute visible cables.",
    "Scan the receipts if they need reimbursement."
  ],
  "confidence_notes": "Object labels are estimates. Do not rely on this alone for safety-critical decisions."
}
```

## Tech Stack

| Technology | Why |
|------------|-----|
| **Streamlit** | Fast to prototype, built-in file upload and webcam capture, clean demo UI |
| **Google Gemini 3.5 Flash** | Strong multimodal reasoning at low cost, native spatial grounding for bounding boxes, structured outputs via Pydantic schema, generous free tier |
| **Pillow (PIL)** | Lightweight image annotation — no heavy OpenCV dependency for simple overlays |
| **Pydantic** | Type-safe schema definition, automatic JSON schema generation for structured outputs |
| **python-dotenv** | Clean environment variable management, keeps secrets out of code |

## Status

### Fully Working
- _To be updated after implementation_

### Partial
- **Bounding boxes**: Gemini returns approximate normalized coordinates, not pixel-accurate detection. Boxes are drawn when available but may be inaccurate.

### Would Improve With More Time
- Multiple analysis modes (whiteboard, receipt, inventory, site safety)
- Analysis history and comparison across frames
- OCR pipeline for text extraction
- Evaluation set with expected outputs
- OpenClaw action envelope format for downstream agent consumption
- Edge deployment documentation (Raspberry Pi / Jetson Nano)

## Assumptions & Limitations

- **Bounding boxes are model estimates**, not the output of a dedicated object detector (like YOLO). They may be inaccurate or missing entirely.
- **Confidence scores are the model's self-assessment**, not calibrated probabilities. They indicate relative certainty, not ground truth.
- **Not for safety-critical decisions.** This is a prototype demo — do not rely on it for actual workplace safety compliance.
- **Single image analysis only** — no video, multi-frame, or streaming support.
- **Webcam capture requires HTTPS** in production deployments (localhost works for local development).
- **API dependency** — requires an active Gemini API key and internet connection. Latency depends on image size and API load (typically 2-6 seconds on Flash).

## Demo Evidence

_Screenshots and sample outputs will be added after implementation._

## License

Built as a take-home assignment for LVL3.ai.
