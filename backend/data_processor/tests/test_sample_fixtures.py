"""Inference tests against the checked-in CSVs under backend/test_data/.

These act as fixtures for manual QA and ensure the files themselves stay
consistent with the inferred types documented in test_data/README.md.
"""
from pathlib import Path

import pandas as pd
import pytest

from data_processor.infer_data_types import get_type_info, infer_and_convert_data_types
from data_processor.s3_utils import _read_csv_with_fallback

DATA_DIR = Path(__file__).resolve().parents[2] / 'test_data'


def _load(name: str) -> pd.DataFrame:
    """Read a test CSV through the same encoding-fallback path S3 uses."""
    return _read_csv_with_fallback((DATA_DIR / name).read_bytes())


def _display(df: pd.DataFrame) -> dict:
    return {c['name']: c['display_type'] for c in get_type_info(df)}


class TestAllTypesFixture:
    def test_every_type_detected(self):
        df = infer_and_convert_data_types(_load('all_types.csv'))
        types = _display(df)
        assert types == {
            'id':             'Integer',
            'name':           'Text',
            'active':         'Boolean',
            'score':          'Integer',   # nullable Int64 after 'N/A' coercion
            'grade':          'Category',
            'price':          'Decimal',
            'joined':         'Date/Time',
            'session_length': 'Time Delta',
        }
        assert df['score'].isna().sum() == 1


class TestSalesFixture:
    def test_sales_inference(self):
        df = infer_and_convert_data_types(_load('sales.csv'))
        types = _display(df)
        assert types['order_id']   == 'Integer'
        assert types['product']    == 'Category'
        assert types['unit_price'] == 'Decimal'
        assert types['order_date'] == 'Date/Time'
        assert types['shipped']    == 'Boolean'


class TestSignalsFixture:
    def test_complex_and_tz_datetime(self):
        df = infer_and_convert_data_types(_load('signals.csv'))
        types = _display(df)
        assert types['captured_at'] == 'Date/Time'
        assert types['amplitude']   == 'Complex Number'
        assert types['channel']     == 'Category'


class TestBooleanFormatsFixture:
    def test_every_column_is_boolean(self):
        df = infer_and_convert_data_types(_load('boolean_formats.csv'))
        types = _display(df)
        assert set(types.values()) == {'Boolean'}


class TestDatetimeFormatsFixture:
    def test_every_column_is_datetime(self):
        df = infer_and_convert_data_types(_load('datetime_formats.csv'))
        types = _display(df)
        assert set(types.values()) == {'Date/Time'}


class TestEdgeCasesFixture:
    def test_edge_case_columns(self):
        df = infer_and_convert_data_types(_load('edge_cases.csv'))
        types = _display(df)
        assert types['id']             == 'Integer'
        # Scientific notation of whole numbers (1e5=100000) is correctly
        # downcast to Integer by _optimize_numeric — this is intended.
        assert types['scientific']     == 'Integer'
        assert types['negative_float'] == 'Decimal'
        assert types['big_int']        == 'Integer'


class TestMessyEncodingFixture:
    def test_latin1_loads_and_preserves_content(self):
        df = _load('messy_encoding.csv')
        assert len(df) == 5
        assert 'café' in df['city'].values
        assert 'Zürich' in df['city'].values


@pytest.mark.parametrize('name', [
    'all_types.csv',
    'sales.csv',
    'signals.csv',
    'boolean_formats.csv',
    'datetime_formats.csv',
    'edge_cases.csv',
    'messy_encoding.csv',
])
def test_fixture_loads_without_error(name):
    """Smoke test: every fixture loads and passes inference without raising."""
    df = infer_and_convert_data_types(_load(name))
    assert len(df) > 0
