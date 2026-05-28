"""OpenClaw Vision Agent — Streamlit shell (Iteration 1 walking skeleton)."""

import os

import streamlit as st
from dotenv import load_dotenv

from core.vision import analyze_image

load_dotenv()

st.set_page_config(page_title="OpenClaw Vision Agent", layout="centered")
st.title("OpenClaw Vision Agent")
st.caption("Desk Safety Assistant — walking skeleton")

if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY is not set. Add it to a .env file in the project root.")
    st.stop()

uploaded = st.file_uploader(
    "Upload a desk photo",
    type=["jpg", "jpeg", "png", "webp"],
)

if uploaded is not None:
    st.image(uploaded, caption="Input", use_container_width=True)
    if st.button("Analyze", type="primary"):
        with st.spinner("Analyzing..."):
            result = analyze_image(uploaded.getvalue())
        st.code(result, language="json")
