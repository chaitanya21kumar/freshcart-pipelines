from elt import freshcart as f

def test_lecture_sample_and_validation_extension_are_preserved():
    assert len(f.MOCK_WEB_ORDERS) == 6
    assert len(f.MOCK_MOBILE_ORDERS) == 2
    assert 'unsupported_currency' not in f.SQL_10_ORDERS_CLEAN_BASELINE
    assert "currency NOT IN ('INR', 'USD')" in f.SQL_10_ORDERS_CLEAN
    assert 'unsupported_currency' in f.SQL_10_ORDERS_CLEAN
    assert 'NOT EXISTS' in f.SQL_10_ORDERS_CLEAN
    assert 'q.row_data:UPDATED_AT' in f.SQL_10_ORDERS_CLEAN
