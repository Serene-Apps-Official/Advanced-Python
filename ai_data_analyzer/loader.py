import os
import io
import pandas as pd
import pdfplumber

def load_file(path_or_buffer):
    """Load CSV, Excel, JSON or PDF into a pandas.DataFrame.

    Args:
        path_or_buffer: path to file (str) or file-like object

    Returns:
        tuple: (DataFrame, metadata dict)
    """
    metadata = {}

    # if buffer-like, try to infer from name attribute
    if hasattr(path_or_buffer, "read"):
        # need to peek for CSV vs JSON; assume CSV
        try:
            df = pd.read_csv(path_or_buffer)
            metadata["source"] = "file-like"
            return df, metadata
        except Exception:
            path_or_buffer.seek(0)
            df = pd.read_table(path_or_buffer)
            metadata["source"] = "file-like"
            return df, metadata

    path = str(path_or_buffer)
    ext = os.path.splitext(path)[1].lower()

    if ext in (".csv", ".tsv"):
        sep = "," if ext == ".csv" else "\t"
        df = pd.read_csv(path, sep=sep)
        metadata["source"] = path
        return df, metadata

    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(path)
        metadata["source"] = path
        return df, metadata

    if ext in (".json",):
        df = pd.read_json(path)
        metadata["source"] = path
        return df, metadata

    if ext in (".txt",):
        # text file: put each line as a row
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip()]
        df = pd.DataFrame({"text": lines})
        metadata["source"] = path
        return df, metadata

    if ext in (".pdf",):
        # fallback: extract all text into single-column DataFrame
        texts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
        combined = "\n\n".join(texts)
        df = pd.DataFrame({"text": [combined]})
        metadata["source"] = path
        return df, metadata

    raise ValueError(f"Unsupported file type: {ext}")
