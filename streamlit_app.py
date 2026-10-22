import time

import requests
import streamlit as st
from PIL import Image

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Image Moderation", layout="wide")
st.title("🛡️ Image Moderation Pipeline")
st.caption("Layer 1: fast NSFW+OCR gate → Layer 2: async VLM via OpenRouter")

uploaded = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Uploaded image", use_container_width=True)

    if st.button("Moderate", type="primary"):
        with st.spinner("Running Layer 1..."):
            try:
                resp = requests.post(
                    f"{API_URL}/moderate",
                    files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API error: {e}")
                st.stop()

        status = data.get("status")
        if status == "blocked":
            st.error(f"🚫 Blocked by Layer 1: {data['reason']}")
        elif status == "safe":
            st.success(f"✅ Passed by Layer 1: {data['reason']}")
        else:
            st.warning(f"⏳ Under review (post_id={data['post_id']}): {data['reason']}")
            st.info("Waiting for Layer 2 worker verdict...")

            post_id = data["post_id"]
            placeholder = st.empty()
            for _ in range(30):
                time.sleep(2)
                try:
                    r = requests.get(f"{API_URL}/posts/{post_id}", timeout=10)
                except Exception as e:
                    placeholder.error(f"Polling error: {e}")
                    break
                if r.status_code != 200:
                    placeholder.error(f"Post fetch failed ({r.status_code})")
                    break
                post = r.json()
                if post["status"] != "under_review":
                    placeholder.empty()
                    if post["status"] == "safe":
                        st.success("✅ Cleared by Layer 2")
                    elif post["status"] == "removed":
                        st.error("🚫 Removed by Layer 2")
                    if post.get("layer2"):
                        st.subheader("Layer 2 Report")
                        st.json(post["layer2"])
                    break
                placeholder.info("Still under review...")
            else:
                placeholder.warning("Timed out waiting for Layer 2")

        with st.expander("Layer 1 details"):
            st.json(data.get("layer1", {}))
