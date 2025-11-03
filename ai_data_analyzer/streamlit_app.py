"""Streamlit app for interactive AI Data Analyzer.

Run with: streamlit run ai_data_analyzer/streamlit_app.py
"""
import os
import io
import streamlit as st
import pandas as pd

from .loader import load_file
from .analyzer import summarize_dataframe
from .summarizer import ai_summarize, extractive_summary
from .viz import numeric_histogram, correlation_heatmap, missing_values_bar

st.set_page_config(page_title="AI Data Analyzer", layout="wide")

def main():
    st.title("AI-Powered Data Analyzer")

    uploaded = st.file_uploader("Upload CSV/Excel/Text/PDF", type=["csv","xlsx","xls","txt","pdf","json"])

    if uploaded is None:
        st.info("Upload a data file to get started. Example: a CSV or Excel file.")
        return

    # Save uploaded to a temporary buffer path for loader convenience
    try:
        # streamlit provides UploadedFile which has .read()
        df, meta = load_file(uploaded)
    except Exception as e:
        st.error(f"Failed to load file: {e}")
        return

    st.subheader("Preview")
    st.dataframe(df.head(20))

    st.sidebar.header("Analysis")
    if st.sidebar.button("Run analysis"):
        with st.spinner("Running quick analysis..."):
            report = summarize_dataframe(df)
            st.sidebar.success("Analysis complete")

            st.subheader("Quick insights")
            st.write({
                "shape": report["shape"],
                "columns": report["columns"],
                "missing_counts": report.get("missing_counts", {}),
            })

            # show correlation heatmap
            st.plotly_chart(correlation_heatmap(df), use_container_width=True)
            st.plotly_chart(missing_values_bar(df), use_container_width=True)

            # numeric column selector for histogram
            numeric_cols = list(df.select_dtypes(include="number").columns)
            if numeric_cols:
                col = st.selectbox("Choose numeric column for distribution", numeric_cols)
                st.plotly_chart(numeric_histogram(df, col), use_container_width=True)

            st.subheader("Sample Rows")
            st.write(report.get("sample", []))

    # Text summarization
    st.sidebar.header("Summarize text")
    text_col = st.sidebar.selectbox("Choose a text column to summarize", [None] + list(df.select_dtypes(include="object").columns))
    n_sent = st.sidebar.slider("Sentences in summary", 1, 6, 3)
    use_ai = st.sidebar.checkbox("Use AI (Gemini) if available")

    if st.sidebar.button("Generate summary"):
        if text_col is None:
            # summarize the whole table as JSON string
            text = df.to_csv(index=False)
        else:
            text = "\n\n".join(df[text_col].dropna().astype(str).head(200).tolist())

        api_key = "AIzaSyDfn99Bg2PgO66dTN50B2eenTIEm9YXoWY" if use_ai else None
        try:
            summary = ai_summarize(text, api_key=api_key, n_sentences=n_sent)
        except NotImplementedError:
            st.warning("AI summarization isn't configured. Falling back to extractive summary.")
            summary = extractive_summary(text, n_sentences=n_sent)

        st.subheader("Summary")
        st.write(summary)

if __name__ == "__main__":
    main()
