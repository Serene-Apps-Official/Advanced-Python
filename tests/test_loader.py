import os
import tempfile
import pandas as pd
from ai_data_analyzer.loader import load_file

def test_load_csv(tmp_path):
    p = tmp_path / "sample.csv"
    df = pd.DataFrame({"a": [1,2,3], "b": ["x","y","z"]})
    df.to_csv(p, index=False)

    loaded, meta = load_file(str(p))
    assert list(loaded.columns) == ["a", "b"]
    assert loaded.shape == (3,2)
