## Context and Background
 
I have a take-home assignment from Spencer Brown, CEO of LVL3.ai (Level 3 AI). LVL3.ai builds **Claw.dius Maximus**, a managed hosting platform that runs **OpenClaw** (the popular open-source AI agent, formerly Clawdbot) inside dedicated browser-based VMs with zero configuration. The company's thesis is "Level 3 automation" -- AI that understands objectives and adapts intelligently, beyond rigid scripts (Level 1) or predefined workflows (Level 2).
 
The assignment is to build an **"OpenClaw Vision Agent"** prototype -- giving OpenClaw the ability to see. Spencer said: "We're not looking for perfection; we're looking for effort." I have a follow-up discussion in 5-6 days. I am focusing on a **strong Week 1 core submission only**, not stretch goals.
 
The full assignment spec is in this file in the current directory:
`Level_3_AI_OpenClaw_Vision_Agent_Arijit_Take_Home.docx`
 
Read that file carefully before doing anything. Everything below supplements it with my technical decisions.
 
## What to Build
 
A **Streamlit web app** where a user uploads an image (or captures a webcam frame), and the system:
 
1. Sends the image to a **multimodal vision LLM** (use OpenAI's `gpt-4o` via their API) with a structured prompt
2. Gets back a JSON response with: `scene_summary`, `objects` (with confidence), `risks_or_opportunities`, `suggested_actions`, and `confidence_notes`
3. Displays the structured output in a clean, readable UI
4. Overlays basic annotations (labels, bounding boxes if coordinates are available, or text callouts) on the original image using PIL/Pillow or OpenCV
5. Handles at least one failure case gracefully (blurry/tiny image, unsupported file type, API error, empty scene)
**Demo mode to focus on: "Desk Safety Assistant"** -- the user uploads a photo of a desk/workspace, and OpenClaw identifies objects, flags safety risks (liquid near electronics, cable clutter, ergonomic issues), and suggests practical actions. This is easy to demo because I can just photograph my own desk.
 
## Technical Decisions
 
- **Framework:** Streamlit (clean, fast to build, good for demos)
- **Vision model:** OpenAI `gpt-4o` via the `openai` Python SDK. The prompt should ask the model to return ONLY valid JSON matching the assignment's schema. Use a system prompt that establishes the "OpenClaw Vision Agent" persona.
- **Image annotation:** Use Pillow (`PIL`) to draw text labels and simple visual callouts on the image. If the model returns bounding box coordinates, draw those too. Keep it simple -- clean labels are fine for Week 1.
- **Error handling:** Validate image format and size on upload. Catch API errors. Handle cases where the model returns malformed JSON (try/except with a fallback). Show user-friendly error messages, not raw tracebacks.
- **No API keys in the repo.** Use environment variables (`OPENAI_API_KEY`) and document this in the README. Add a `.env.example` file.
- **Python 3.10+**, use a `requirements.txt` with pinned versions.
## Project Structure
 
Initialize the project with this structure:
 
```
openclaw-vision-agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py                    # Main Streamlit app
├── core/
│   ├── __init__.py
│   ├── vision.py             # Vision model API calls and prompt engineering
│   ├── parser.py             # JSON response parsing and validation
│   └── annotator.py          # Image annotation/overlay logic
├── sample_inputs/            # 2-3 sample images for demo purposes
│   └── .gitkeep
├── sample_outputs/           # Example JSON outputs corresponding to sample inputs
│   └── .gitkeep
├── assets/                   # Any static assets (logo, etc.)
│   └── .gitkeep
└── docs/
    └── architecture.md       # Short architecture summary
```
 
## Key Implementation Details
 
### Vision Prompt (core/vision.py)
 
The system prompt for the vision model should:
- Establish that this is "OpenClaw Vision Agent" analyzing a scene
- Instruct the model to return ONLY valid JSON, no markdown fences, no preamble
- Define the exact JSON schema with all required fields from the assignment spec
- Tell it to be specific to what it actually sees, not generic filler
- Include confidence values as floats between 0 and 1
- Make suggested_actions practical and directly tied to visual evidence
- Include a confidence_notes field that honestly states limitations
### Streamlit App (app.py)
 
The app should have:
- A clean header/title: "OpenClaw Vision Agent" with a short tagline
- Image upload widget (accept jpg, jpeg, png, webp)
- A webcam capture option using `st.camera_input` (Streamlit has this built in)
- An "Analyze" button
- A two-column layout after analysis: left side shows the annotated image, right side shows the structured output
- The JSON output displayed both as formatted/readable cards AND as a raw JSON expander
- A spinner/loading state while the API call runs
- Error states that look intentional, not broken
### Image Annotation (core/annotator.py)
 
- Take the original image and the parsed JSON output
- Draw text labels on the image for detected objects
- If bounding box data is available from the model, draw rectangles
- Use a semi-transparent overlay style so labels don't obscure the image
- Return the annotated image as a PIL Image object
### Response Parsing (core/parser.py)
 
- Parse the model's response, stripping any accidental markdown fences
- Validate that all required fields exist in the JSON
- Provide sensible defaults if fields are missing
- Return a typed dict or dataclass
## README Requirements
 
The README must include (Spencer will evaluate this):
- Project title and one-line description
- Quick start: clone, install, set API key, run -- no guessing
- Architecture overview (brief, with a simple diagram or description of the pipeline)
- What is fully working, what is partial, what I would improve with more time
- Assumptions and limitations (be honest -- the model hallucinates, confidence scores are estimates, this is not safety-critical, etc.)
- Sample input/output screenshots or descriptions
- Tech stack and why each choice was made
## GitHub Repo
 
After building everything:
1. Initialize a git repo in the project directory
2. Create a proper `.gitignore` for Python (include `.env`, `__pycache__`, `.venv`, etc.)
3. Make an initial commit with all the project files
4. Create the GitHub repo using `gh repo create xpw1337/openclaw-vision-agent --public --source=. --push`
   - My GitHub username is `xpw1337`
   - Make it public
   - Push the initial commit
## What NOT to Do
 
- Do NOT attempt Week 2 stretch features. Keep scope tight.
- Do NOT build a custom object detection model or fine-tune anything. Use the multimodal LLM as-is.
- Do NOT over-engineer. No Docker, no CI/CD, no database. This is a prototype demo.
- Do NOT include any API keys, tokens, or secrets anywhere in the code or repo.
- Do NOT use generic placeholder responses. Every output must be specific to the actual image provided.
## Final Check
 
Before you're done, verify:
- [ ] `pip install -r requirements.txt` works cleanly
- [ ] `streamlit run app.py` launches without errors (assuming OPENAI_API_KEY is set)
- [ ] Uploading a sample image produces specific, structured JSON output
- [ ] The annotated image displays with labels
- [ ] At least one error case is handled (try uploading a .txt file, or a tiny image)
- [ ] README has clear run instructions
- [ ] `.gitignore` excludes `.env` and other sensitive/generated files
- [ ] Code is modular (vision.py, parser.py, annotator.py are separate concerns)
- [ ] GitHub repo is created and pushed
Now read the docx file, then start building. Work through it methodically -- get the core pipeline (image -> API -> JSON) working first, then add the UI and annotations, then polish.
