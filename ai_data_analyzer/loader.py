import os
import io
from io import StringIO, BytesIO
import pandas as pd
import pdfplumber

_FALLBACK_ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]

def load_file(path_or_buffer):
    """Load CSV, Excel, JSON or PDF into a pandas.DataFrame.

    Args:
        path_or_buffer: path to file (str) or file-like object

    Returns:
        tuple: (DataFrame, metadata dict)
    """
    metadata = {}

    # helper to try reading CSV/TSV with multiple encodings
    def _try_read_text(buf_bytes, sep=","):
        last_exc = None
        for enc in _FALLBACK_ENCODINGS:
            try:
                text = buf_bytes.decode(enc)
                return pd.read_csv(StringIO(text), sep=sep), enc
            except Exception as e:
                last_exc = e
                continue
        # as a last resort, try pandas default (may raise)
        raise last_exc or UnicodeDecodeError("utf-8", b"", 0, 1, "unable to decode")

    # if buffer-like, try to infer from name attribute
    if hasattr(path_or_buffer, "read"):
        raw = path_or_buffer.read()
        # If returned str, wrap and let pandas parse it
        if isinstance(raw, str):
            try:
                df = pd.read_csv(StringIO(raw))
                metadata["source"] = "file-like"
                return df, metadata
            except Exception:
                df = pd.read_table(StringIO(raw))
                metadata["source"] = "file-like"
                return df, metadata
        # bytes: try multiple encodings
        if isinstance(raw, (bytes, bytearray)):
            try:
                df, used_enc = _try_read_text(bytes(raw), sep=",")
                metadata["source"] = "file-like"
                metadata["encoding"] = used_enc
                return df, metadata
            except Exception:
                # fallback: let pandas try reading bytes directly
                try:
                    path_or_buffer.seek(0)
                except Exception:
                    pass
                try:
                    df = pd.read_csv(BytesIO(raw))
                    metadata["source"] = "file-like"
                    return df, metadata
                except Exception:
                    # last resort: raise original decode error
                    raise

    path = str(path_or_buffer)
    ext = os.path.splitext(path)[1].lower()

    if ext in (".csv", ".tsv"):
        sep = "," if ext == ".csv" else "\t"
        last_exc = None
        for enc in _FALLBACK_ENCODINGS:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc)
                metadata["source"] = path
                metadata["encoding"] = enc
                return df, metadata
            except Exception as e:
                last_exc = e
                continue
        # give up with the last exception
        raise last_exc

    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(path)
        metadata["source"] = path
        return df, metadata

    if ext in (".json",):
        df = pd.read_json(path)
        metadata["source"] = path
        return df, metadata

    if ext in (".txt",):
        # text file: try multiple encodings
        last_exc = None
        for enc in _FALLBACK_ENCODINGS:
            try:
                with open(path, "r", encoding=enc, errors="strict") as f:
                    lines = [l.strip() for l in f if l.strip()]
                df = pd.DataFrame({"text": lines})
                metadata["source"] = path
                metadata["encoding"] = enc
                return df, metadata
            except Exception as e:
                last_exc = e
                continue
        # as a last resort, open with latin-1 forgiving errors
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
        df = pd.DataFrame({"text": lines})
        metadata["source"] = path
        metadata["encoding"] = "latin-1-replace"
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
