import streamlit as st
from PyPDF2 import PdfReader
from docx import Document

st.set_page_config(page_title="Document Text Extractor", layout="centered")

st.title("📄 Document Text Extractor")
st.write("Upload a **PDF**, **Word (.docx)**, or **Text (.txt)** file to extract its text.")

# File uploader
uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split('.')[-1].lower()

    extracted_text = ""

    if file_type == "pdf":
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            extracted_text += page.extract_text() or ""

    elif file_type == "docx":
        doc = Document(uploaded_file)
        for para in doc.paragraphs:
            extracted_text += para.text + "\n"

    elif file_type == "txt":
        extracted_text = uploaded_file.read().decode("utf-8")

    else:
        st.error("Unsupported file type!")

    if extracted_text.strip():
        st.subheader("📜 Extracted Text:")
        st.text_area("Text Content", extracted_text, height=300)
    else:
        st.warning("No text could be extracted from this file.")
