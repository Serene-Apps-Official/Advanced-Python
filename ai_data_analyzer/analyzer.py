import pandas as pd

def summarize_dataframe(df: pd.DataFrame, sample_rows: int = 5):
    """Return a dict of automatic analysis results for a DataFrame.

    Provides dtypes, missing values, numeric summary and correlations.
    """
    result = {}

    # basic info
    result["shape"] = df.shape
    result["columns"] = list(df.columns)
    result["dtypes"] = df.dtypes.apply(lambda x: str(x)).to_dict()

    # missing values
    missing = df.isnull().sum()
    result["missing_counts"] = missing[missing > 0].to_dict()

    # numeric summary
    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        result["numeric_summary"] = numeric.describe().to_dict()
        # correlations
        corr = numeric.corr()
        result["correlations"] = corr.fillna(0).to_dict()
    else:
        result["numeric_summary"] = {}
        result["correlations"] = {}

    # sample rows
    result["sample"] = df.head(sample_rows).to_dict(orient="records")

    # top cardinality for object columns
    cat_summary = {}
    for col in df.select_dtypes(include="object").columns:
        vc = df[col].value_counts(dropna=True).head(5)
        cat_summary[col] = vc.to_dict()
    result["categorical_top_values"] = cat_summary

    return result
