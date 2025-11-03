# AI-Powered Data Analyzer

This small package provides utilities to load tabular files (CSV, Excel, JSON, text and basic PDF extraction), run quick automated analysis and produce extractive summaries. It also includes a Streamlit app for interactive use.

How to run

- Install dependencies (recommended in a virtualenv):

```powershell
python -m pip install -r requirements.txt
```

- Run the Streamlit app:

```powershell
streamlit run "ai_data_analyzer/streamlit_app.py"
```

AI summarization

The code contains a placeholder to integrate Gemini (or other LLMs). To enable it, set the environment variable `GEMINI_API_KEY` and implement the network call in `ai_data_analyzer.summarizer.ai_summarize`.

Files added

- `ai_data_analyzer/loader.py`: load CSV/Excel/JSON/TXT/PDF
- `ai_data_analyzer/analyzer.py`: quick statistics and correlations
- `ai_data_analyzer/summarizer.py`: simple extractive summarizer + AI stub
- `ai_data_analyzer/viz.py`: plotly viz helpers
- `ai_data_analyzer/streamlit_app.py`: interactive app
- `requirements.txt` and `README.md`
