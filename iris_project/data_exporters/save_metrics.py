"""C4 extension: publish the evaluated metrics only after their quality check."""
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

@data_exporter
def export_metrics(df, *args, **kwargs):
    df.to_csv('iris_metrics.csv', index=False)
    print('Saved', len(df), 'metrics to iris_metrics.csv')

@test
def test_metrics_written(*args):
    import pandas as pd
    from pathlib import Path
    assert Path('iris_metrics.csv').is_file()
    saved = pd.read_csv('iris_metrics.csv')
    assert saved['metric'].tolist() == ['accuracy', 'precision', 'recall', 'f1_score']
    assert saved['value'].between(0, 1).all()
