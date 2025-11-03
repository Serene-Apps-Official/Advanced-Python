import streamlit as st
import pdfplumber
from docx import Document
import requests
import websearch
import time

# ------------------ CONFIGURATION ------------------
st.set_page_config(page_title="🧠 Serene AI Summarizer", page_icon="🌐", layout="wide")

# Hugging Face API Endpoint
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"


# ------------------ COMMON SUMMARIZER FUNCTION ------------------
def summarize_text(text, tone="neutral", length="medium"):
    """Summarize text using Hugging Face API."""
    if not text.strip():
        return "⚠️ No content found to summarize."
    
    text = text[:2500]  # limit for token safety
    payload = {"inputs": f"Summarize this in a {tone} tone with {length} length:\n{text}"}
    
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and "summary_text" in data[0]:
                return data[0]["summary_text"]
            return str(data)
        else:
            return f"⚠️ API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Error: {e}"

# ------------------ STYLING ------------------
st.markdown("""
    <style>
        .main-title {
            text-align:center;
            font-size:2.5rem;
            color:#004f6d;
            text-shadow:1px 1px 2px #00aee6;
        }
        .desc {
            text-align:center;
            font-size:1.1rem;
            color:#004f6d;
        }
        .summary-box {
            background:#e7f5ff;
            border-left:5px solid #0096c7;
            padding:1rem;
            border-radius:10px;
            margin-top:1rem;
            font-size:1.05rem;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧠 Serene AI Summarizer</div>', unsafe_allow_html=True)
st.markdown('<div class="desc">Summarize documents and websites using AI-powered understanding.</div>', unsafe_allow_html=True)

# ------------------ MODE SELECTION ------------------
mode = st.radio("Choose Mode:", ["🌐 Website Summarizer", "📄 Document Summarizer"], horizontal=True)

# Sidebar customization
st.sidebar.header("⚙️ Customization")
tone = st.sidebar.selectbox("Choose Summary Tone:", ["Neutral", "Friendly", "Formal", "Analytical"])
length = st.sidebar.radio("Summary Length:", ["Short (2–3 lines)", "Medium (1 paragraph)", "Detailed Summary"])

# ------------------ WEBSITE SUMMARIZER MODE ------------------
if mode == "🌐 Website Summarizer":
    st.subheader("🌍 Website Summarizer Mode")
    url = st.text_input("🔗 Enter Website URL (e.g. example.com)")

    if st.button("✨ Summarize Website"):
        if url:
            st.info("⏳ Fetching website content...")
            try:
                content = websearch.getWebDescript("https://" + url)
                if not content.strip():
                    st.warning("⚠️ Could not extract meaningful text from this URL.")
                else:
                    st.success("✅ Website content fetched successfully!")
                    with st.spinner("🤖 Summarizing content..."):
                        summary = summarize_text(content, tone, length)
                    st.subheader("🧠 AI Summary")
                    st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)

                    st.download_button(
                        label="💾 Download Website Summary",
                        data=summary,
                        file_name=f"{url.replace('.', '_')}_summary.txt",
                        mime="text/plain"
                    )
                    st.balloons()
            except Exception as e:
                st.error(f"❌ Error: {e}")
        else:
            st.warning("⚠️ Please enter a valid URL.")

# ------------------ DOCUMENT SUMMARIZER MODE ------------------
else:
    st.subheader("📄 Document Summarizer Mode")
    uploaded_file = st.file_uploader("Upload your document", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        file_type = uploaded_file.name.split('.')[-1].lower()
        extracted_text = ""

        with st.spinner("🔍 Extracting text..."):
            try:
                if file_type == "pdf":
                    # Using pdfplumber for accurate extraction
                    with pdfplumber.open(uploaded_file) as pdf:
                        for page in pdf.pages:
                            extracted_text += page.extract_text() or ""

                elif file_type == "docx":
                    doc = Document(uploaded_file)
                    for para in doc.paragraphs:
                        extracted_text += para.text + "\n"

                elif file_type == "txt":
                    extracted_text = uploaded_file.read().decode("utf-8")

            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
                st.stop()

        if extracted_text.strip():
            st.success("✅ Text successfully extracted!")
            with st.expander("📜 View Extracted Text"):
                st.text_area("Extracted Text", extracted_text, height=300)

            if st.button("✨ Generate Summary"):
                with st.spinner("🤖 Summarizing document..."):
                    summary = summarize_text(extracted_text, tone, length)
                st.subheader("🧠 AI Summary")
                st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)

                st.download_button(
                    label="💾 Download Document Summary",
                    data=summary,
                    file_name="document_summary.txt",
                    mime="text/plain"
                )
                st.balloons()
        else:
            st.warning("⚠️ No text could be extracted from this document.")
