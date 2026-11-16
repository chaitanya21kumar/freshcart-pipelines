import pandas as pd
import pytest
from iris_project.transformers.train_model import test_accuracy as gate
from iris_project.transformers.evaluate_model import evaluate, test_metrics as metrics_gate

def test_gate_rejects_bad_predictions():
    with pytest.raises(AssertionError, match='below 80%'):
        gate(pd.DataFrame({'target': [0, 1, 2, 1], 'predicted': [0, 0, 0, 0]}))

def test_metrics_are_valid_for_perfect_predictions():
    metrics = evaluate(pd.DataFrame({'target': [0, 1, 2], 'predicted': [0, 1, 2]}))
    metrics_gate(metrics)
    assert (metrics['value'] == 1).all()
