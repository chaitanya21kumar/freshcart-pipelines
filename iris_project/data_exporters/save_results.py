# Import Mage's decorator only if it isn't already loaded
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


# data_exporter marks this as a step that sends data out of the pipeline
# 'df' is the 30 predicted rows returned by train_model, passed in automatically by Mage
# It saves them to a CSV file and returns nothing, because this is an end of the pipeline
@data_exporter
def export_data(df, *args, **kwargs):
    df.to_csv('iris_predictions.csv', index=False)
    print('Saved', len(df), 'predictions to iris_predictions.csv')
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

@test
def test_predictions_written(*args):
    from pathlib import Path
    import pandas as pd
    path = Path('iris_predictions.csv')
    assert path.exists(), 'Predictions were not written'
    saved = pd.read_csv(path)
    assert len(saved) == 30 and {'target', 'predicted'}.issubset(saved.columns)
