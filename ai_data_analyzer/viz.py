import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def numeric_histogram(df: pd.DataFrame, column: str):
    fig = px.histogram(df, x=column, nbins=40, title=f"Distribution of {column}")
    return fig

def correlation_heatmap(df: pd.DataFrame):
    numeric = df.select_dtypes(include="number")
    if numeric.shape[1] == 0:
        return go.Figure()
    corr = numeric.corr()
    fig = px.imshow(corr, text_auto=True, title="Correlation matrix")
    return fig

def missing_values_bar(df: pd.DataFrame):
    miss = df.isnull().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    if miss.empty:
        fig = go.Figure()
        fig.update_layout(title="No missing values")
        return fig
    fig = px.bar(x=miss.index, y=miss.values, labels={"x":"column","y":"missing_count"}, title="Missing values by column")
    return fig
