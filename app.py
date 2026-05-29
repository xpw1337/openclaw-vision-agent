"""OpenClaw Vision Agent — Streamlit shell (Iteration 2 spec-complete)."""

import io
import os

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from core import analyze_image, annotate_image, safe_to_dict

load_dotenv()

st.set_page_config(page_title="OpenClaw Vision Agent", layout="wide")
st.title("OpenClaw Vision Agent")
st.caption("Desk Safety Assistant")

if not os.getenv("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY is not set. Add it to a .env file in the project root.")
    st.stop()

source = st.radio("Input source", ["Upload Image", "Webcam Capture"], horizontal=True)
if source == "Upload Image":
    file = st.file_uploader("Upload a desk photo", type=["jpg", "jpeg", "png", "webp"])
else:
    file = st.camera_input("Capture a desk photo")

if file is not None:
    if st.button("Analyze Workspace", type="primary"):
        with st.spinner("Analyzing your workspace..."):
            image_bytes = file.getvalue()
            analysis = analyze_image(image_bytes)
            annotated = annotate_image(Image.open(io.BytesIO(image_bytes)), analysis)

        left, right = st.columns([1, 1])
        with left:
            st.image(annotated, use_container_width=True)
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
