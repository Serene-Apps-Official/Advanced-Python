import pandas as pd
import numpy as np

# Create sample data
df = pd.DataFrame({'A': np.random.rand(1000000), 'B': np.random.rand(1000000)})

df['C'] = df[ 'A' ] * df[ 'B' ] + np.sin(df[ 'A' ] )


df[ 'D' ] = df.apply( lambda row : row[ 'A' ] * row[ 'B' ] + np.sin(row[ 'A' ]) , axis=1 )