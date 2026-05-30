"""OpenClaw Vision Agent — Streamlit shell (Iteration 3 robustness).

Handles the PRD §5 error matrix end-to-end (corrupt files, tiny images, API and
content-policy failures), keeps photo orientation consistent with what the model
sees, and persists results in session state so they survive Streamlit reruns.
"""

import io
import os

import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

from core import (
    ContentBlockedError,
    analyze_image,
    annotate_image,
    check_image_quality,
    safe_to_dict,
)

_QUALITY_MESSAGES = {
    "blank": (
        "This image looks blank or featureless (very dark, very bright, or a "
        "solid color), so the model has nothing to analyze."
    ),
    "blurry": "This image looks too blurry to analyze reliably.",
}

load_dotenv()

st.set_page_config(page_title="OpenClaw Vision Agent", layout="wide")
st.title("OpenClaw Vision Agent")
st.caption("Desk Safety Assistant")

if not os.getenv("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY is not set. Add it to a .env file in the project root.")
    st.stop()


def _file_signature(uploaded) -> tuple:
    """Identify the selected file so we can drop stale results on a new upload."""
    return (getattr(uploaded, "name", None), getattr(uploaded, "size", None))


def _render_results(analysis, annotated) -> None:
    left, right = st.columns([1, 1])
    with left:
        st.image(annotated, width="stretch")
    with right:
        st.info(analysis.scene_summary)

        st.subheader("Detected Objects")
        if analysis.objects:
            st.markdown(
                "\n".join(
                    f"- **{o.label}** ({int(o.confidence * 100)}%)"
                    for o in analysis.objects
                )
            )
        else:
            st.caption("No objects detected.")

        st.subheader("Risks & Opportunities")
        for risk in analysis.risks_or_opportunities:
            st.warning(risk)

        st.subheader("Suggested Actions")
        for action in analysis.suggested_actions:
            st.success(action)

        if analysis.confidence_notes:
            st.caption(analysis.confidence_notes)

    with st.expander("Raw JSON"):
        st.json(safe_to_dict(analysis))


source = st.radio("Input source", ["Upload Image", "Webcam Capture"], horizontal=True)
if source == "Upload Image":
    file = st.file_uploader("Upload a desk photo", type=["jpg", "jpeg", "png", "webp"])
else:
    file = st.camera_input("Capture a desk photo")

if file is None:
    # Empty state: results from a previous file are no longer relevant.
    st.session_state.pop("results", None)
    st.session_state.pop("file_sig", None)
    st.markdown(
        "Upload a desk photo (or capture one with your webcam) and click "
        "**Analyze Workspace** to get a structured safety read: detected objects, "
        "risks, and concrete actions.\n\n"
        "No photo handy? There are example desk images in the `sample_inputs/` "
        "folder of this repo you can drag in."
    )
    st.stop()

# Drop stale results (and any pending quality warning) on a new file selection.
signature = _file_signature(file)
if st.session_state.get("file_sig") != signature:
    st.session_state["file_sig"] = signature
    st.session_state.pop("results", None)
    st.session_state.pop("pending_reason", None)

image_bytes = file.getvalue()
try:
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
except (UnidentifiedImageError, OSError):
    st.error("Could not open this file as an image.")
    st.stop()

if min(image.size) < 50:
    st.warning("This image is very small (under 50px); results may be unreliable.")

# On Analyze: pre-check quality. A flagged image opens a warning dialog (which can
# be overridden) instead of running straight away; an override is remembered per file.
if st.button("Analyze Workspace", type="primary"):
    reason = check_image_quality(image)
    if reason and st.session_state.get("force_sig") != signature:
        st.session_state["pending_reason"] = reason
    else:
        st.session_state["run_now"] = True

if st.session_state.get("pending_reason"):

    @st.dialog("This image may be unusable")
    def _quality_warning() -> None:
        st.warning(_QUALITY_MESSAGES[st.session_state["pending_reason"]])
        st.write("Pick a different image, or analyze this one anyway.")
        left_btn, right_btn = st.columns(2)
        if left_btn.button("Analyze anyway", type="primary"):
            st.session_state["force_sig"] = signature
            st.session_state["run_now"] = True
            st.session_state.pop("pending_reason", None)
            st.rerun()
        if right_btn.button("Choose another image"):
            st.session_state.pop("pending_reason", None)
            st.rerun()

    _quality_warning()

# Decoupled from the button value so "Analyze anyway" can trigger it on its own rerun.
if st.session_state.pop("run_now", False):
    with st.spinner("Analyzing your workspace..."):
        try:
            analysis = analyze_image(image_bytes)
            annotated = annotate_image(image, analysis)
            st.session_state["results"] = {"analysis": analysis, "annotated": annotated}
        except ContentBlockedError:
            st.session_state.pop("results", None)
            st.error("This image could not be analyzed due to content policy.")
        except Exception as exc:  # noqa: BLE001 — surface any API/network failure cleanly
            st.session_state.pop("results", None)
            st.error(f"Analysis failed: {exc}")

# Render outside the button block so results persist across reruns (e.g. expander).
results = st.session_state.get("results")
if results:
    _render_results(results["analysis"], results["annotated"])
