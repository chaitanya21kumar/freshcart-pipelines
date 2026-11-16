from sklearn.datasets import load_iris
from iris_project.transformers.prepare_data import transform

def test_split_is_80_20():
    df = load_iris(as_frame=True).frame
    out = transform(df)
    assert (out['split'] == 'train').sum() == 120
    assert (out['split'] == 'test').sum() == 30

def test_no_rows_lost_duplicated_or_leaked():
    df = load_iris(as_frame=True).frame
    out = transform(df)
    assert len(out) == len(df)
    assert out.index.is_unique
    train = out.loc[out['split'] == 'train']
    test = out.loc[out['split'] == 'test']
    assert set(train.index).isdisjoint(test.index)
    assert set(out.index) == set(df.index)
    assert 'split' not in df.columns

def test_split_is_reproducible():
    df = load_iris(as_frame=True).frame
    assert transform(df).equals(transform(df))
