"""Unit tests for the type-inference engine."""
import numpy as np
import pandas as pd
import pytest

from data_processor.infer_data_types import (
    apply_type_override,
    get_type_info,
    infer_and_convert_data_types,
)


# ── Booleans ───────────────────────────────────────────────────────────────────

class TestBooleanInference:
    def test_true_false_strings(self):
        df = pd.DataFrame({'x': ['true', 'false', 'true', 'false']})
        out = infer_and_convert_data_types(df)
        assert str(out['x'].dtype) == 'boolean'

    def test_yes_no(self):
        df = pd.DataFrame({'x': ['yes', 'no', 'yes', 'no']})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'boolean'

    def test_case_insensitive(self):
        df = pd.DataFrame({'x': ['TRUE', 'False', 'YES', 'no']})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'boolean'

    def test_t_f_short_form(self):
        df = pd.DataFrame({'x': ['T', 'F', 'T', 'F']})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'boolean'

    def test_bool_with_nulls(self):
        df = pd.DataFrame({'x': ['yes', None, 'no', 'yes']})
        out = infer_and_convert_data_types(df)
        assert str(out['x'].dtype) == 'boolean'
        assert out['x'].isna().sum() == 1

    def test_bool_values_correct(self):
        df = pd.DataFrame({'x': ['yes', 'no', 'Y', 'N']})
        out = infer_and_convert_data_types(df)
        assert out['x'].tolist() == [True, False, True, False]

    def test_more_than_two_unique_not_bool(self):
        df = pd.DataFrame({'x': ['yes', 'no', 'maybe', 'yes']})
        out = infer_and_convert_data_types(df)
        assert str(out['x'].dtype) != 'boolean'


# ── Numerics ───────────────────────────────────────────────────────────────────

class TestNumericInference:
    def test_integers(self):
        df = pd.DataFrame({'x': ['1', '2', '3', '4', '5']})
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_integer_dtype(out['x'])

    def test_floats(self):
        df = pd.DataFrame({'x': ['1.5', '2.7', '3.14', '4.0', '5.5']})
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_float_dtype(out['x'])

    def test_mixed_with_text_becomes_nullable_int(self):
        """The canonical case from sample_data.csv — 'Not Available' in numeric col."""
        df = pd.DataFrame({'Score': ['90', '75', '85', '70', 'Not Available']})
        out = infer_and_convert_data_types(df)
        assert str(out['Score'].dtype) == 'Int64'
        assert out['Score'].isna().sum() == 1
        assert out['Score'].dropna().tolist() == [90, 75, 85, 70]

    def test_uint8_downcast(self):
        df = pd.DataFrame({'x': list(range(256))})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'uint8'

    def test_int8_downcast_negative(self):
        df = pd.DataFrame({'x': [-100, -50, 0, 50, 100]})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'int8'

    def test_int16_when_too_big_for_int8(self):
        df = pd.DataFrame({'x': [-200, -100, 0, 100, 200]})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'int16'

    def test_negative_floats(self):
        df = pd.DataFrame({'x': ['-1.5', '-2.7', '-3.14']})
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_float_dtype(out['x'])

    def test_scientific_notation(self):
        df = pd.DataFrame({'x': ['1e5', '2e6', '3e7']})
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_numeric_dtype(out['x'])

    def test_mostly_non_numeric_stays_text(self):
        df = pd.DataFrame({'x': ['abc', 'def', 'ghi', '1']})
        out = infer_and_convert_data_types(df)
        assert not pd.api.types.is_numeric_dtype(out['x'])


# ── Datetimes ──────────────────────────────────────────────────────────────────

class TestDatetimeInference:
    def test_iso_date(self):
        df = pd.DataFrame({'x': ['2023-01-15', '2023-02-20', '2023-03-25']})
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])

    def test_us_slash_format(self):
        df = pd.DataFrame({'x': ['1/15/2023', '2/20/2023', '3/25/2023']})
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])

    def test_with_time(self):
        df = pd.DataFrame({'x': ['2023-01-15 10:30:00', '2023-02-20 14:45:00']})
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])

    def test_iso_with_tz(self):
        df = pd.DataFrame({'x': ['2023-01-15T10:30:00Z', '2023-02-20T14:45:00Z']})
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])

    def test_month_name(self):
        df = pd.DataFrame({'x': ['Jan 15, 2023', 'Feb 20, 2023', 'Mar 25, 2023']})
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])

    def test_compact_format(self):
        df = pd.DataFrame({'x': ['20230115', '20230220', '20230325']})
        # Compact format may be read as integer; if not datetime, at least numeric
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_datetime64_any_dtype(out['x']) or pd.api.types.is_numeric_dtype(out['x'])

    def test_date_with_some_garbage(self):
        df = pd.DataFrame({'x': ['2023-01-15', '2023-02-20', '2023-03-25', 'not a date', '2023-04-10']})
        # 4/5 = 80% parseable → still becomes datetime
        assert pd.api.types.is_datetime64_any_dtype(infer_and_convert_data_types(df)['x'])


# ── Complex numbers ────────────────────────────────────────────────────────────

class TestComplexInference:
    def test_complex_notation(self):
        df = pd.DataFrame({'x': ['3+4j', '1-2j', '5+6j', '7-8j']})
        out = infer_and_convert_data_types(df)
        assert 'complex' in str(out['x'].dtype).lower()

    def test_pure_imaginary(self):
        df = pd.DataFrame({'x': ['3j', '-4j', '5j', '-6j']})
        out = infer_and_convert_data_types(df)
        assert 'complex' in str(out['x'].dtype).lower()


# ── Timedeltas ─────────────────────────────────────────────────────────────────

class TestTimedeltaInference:
    def test_day_hour_keywords(self):
        df = pd.DataFrame({'x': ['3 days', '5 hours', '1 day', '10 hours']})
        out = infer_and_convert_data_types(df)
        assert 'timedelta' in str(out['x'].dtype).lower()

    def test_short_forms(self):
        df = pd.DataFrame({'x': ['3d', '5h', '30m', '90s']})
        out = infer_and_convert_data_types(df)
        assert 'timedelta' in str(out['x'].dtype).lower()

    def test_integer_column_not_misclassified(self):
        """Pure integers must NOT be coerced to timedelta (regression guard)."""
        df = pd.DataFrame({'x': ['1', '2', '3', '4', '5']})
        out = infer_and_convert_data_types(df)
        assert 'timedelta' not in str(out['x'].dtype).lower()

    def test_time_of_day_not_timedelta(self):
        """'HH:MM:SS' strings are intentionally not treated as durations."""
        df = pd.DataFrame({'x': ['10:30:00', '11:15:00', '14:00:00', '09:45:00']})
        out = infer_and_convert_data_types(df)
        assert 'timedelta' not in str(out['x'].dtype).lower()


# ── Categoricals ───────────────────────────────────────────────────────────────

class TestCategoricalInference:
    def test_low_cardinality(self):
        df = pd.DataFrame({'x': ['A', 'B', 'A', 'B', 'A', 'C', 'B', 'A', 'B', 'A']})
        assert str(infer_and_convert_data_types(df)['x'].dtype) == 'category'

    def test_all_unique_stays_text(self):
        df = pd.DataFrame({'x': ['Alice', 'Bob', 'Charlie', 'David', 'Eve']})
        # 100 % unique → must not be categorical
        assert str(infer_and_convert_data_types(df)['x'].dtype) != 'category'


# ── Manual overrides ───────────────────────────────────────────────────────────

class TestTypeOverride:
    def test_override_integer(self):
        df = pd.DataFrame({'x': ['1', '2', '3']})
        out = infer_and_convert_data_types(df, type_overrides={'x': 'integer'})
        assert pd.api.types.is_integer_dtype(out['x'])

    def test_override_decimal(self):
        df = pd.DataFrame({'x': ['1', '2', '3']})
        out = infer_and_convert_data_types(df, type_overrides={'x': 'decimal'})
        assert pd.api.types.is_float_dtype(out['x'])

    def test_override_datetime(self):
        df = pd.DataFrame({'x': ['2023-01-15', '2023-02-20']})
        out = infer_and_convert_data_types(df, type_overrides={'x': 'datetime64'})
        assert pd.api.types.is_datetime64_any_dtype(out['x'])

    def test_override_category(self):
        df = pd.DataFrame({'x': ['Alice', 'Bob', 'Charlie']})
        out = infer_and_convert_data_types(df, type_overrides={'x': 'category'})
        assert str(out['x'].dtype) == 'category'

    def test_override_boolean(self):
        df = pd.DataFrame({'x': ['yes', 'no', 'yes']})
        out = infer_and_convert_data_types(df, type_overrides={'x': 'boolean'})
        assert str(out['x'].dtype) == 'boolean'

    def test_override_text(self):
        df = pd.DataFrame({'x': ['1', '2', '3']})  # would normally be int
        out = infer_and_convert_data_types(df, type_overrides={'x': 'text'})
        # Forced to string-like
        assert not pd.api.types.is_numeric_dtype(out['x'])

    def test_unknown_override_leaves_column_untouched(self):
        df = pd.DataFrame({'x': ['1', '2', '3']})
        # An unrecognised type name should not raise
        out = infer_and_convert_data_types(df, type_overrides={'x': 'no_such_type'})
        assert 'x' in out.columns


# ── get_type_info ──────────────────────────────────────────────────────────────

class TestGetTypeInfo:
    def test_display_types(self):
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [30, 25],
            'active': [True, False],
            'date': pd.to_datetime(['2023-01-01', '2023-02-01']),
        })
        info = {c['name']: c for c in get_type_info(df)}
        assert info['active']['display_type'] == 'Boolean'
        assert info['date']['display_type'] == 'Date/Time'
        assert info['age']['display_type'] == 'Integer'

    def test_null_and_unique_counts(self):
        df = pd.DataFrame({'x': ['A', 'B', 'A', None]})
        info = get_type_info(df)[0]
        assert info['null_count'] == 1
        assert info['unique_count'] == 2

    def test_sample_values(self):
        df = pd.DataFrame({'x': ['a', 'b', 'c', 'd', 'e', 'f']})
        assert len(get_type_info(df)[0]['sample_values']) == 5  # head(5)


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_all_null_column(self):
        df = pd.DataFrame({'x': [None, None, None]})
        out = infer_and_convert_data_types(df)
        assert 'x' in out.columns  # doesn't crash

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=['a', 'b'])
        out = infer_and_convert_data_types(df)
        assert list(out.columns) == ['a', 'b']

    def test_single_row(self):
        df = pd.DataFrame({'x': ['42']})
        out = infer_and_convert_data_types(df)
        assert pd.api.types.is_numeric_dtype(out['x'])

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({'x': ['1', '2', '3']})
        before = df['x'].dtype
        _ = infer_and_convert_data_types(df)
        assert df['x'].dtype == before


# ── Integration test — the canonical sample_data.csv case ─────────────────────

class TestSampleDataFile:
    def test_full_sample_inference(self):
        df = pd.DataFrame({
            'Name':      ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
            'Birthdate': ['1/01/1990', '2/02/1991', '3/03/1992', '4/04/1993', '5/05/1994'],
            'Score':     ['90', '75', '85', '70', 'Not Available'],
            'Grade':     ['A', 'B', 'A', 'B', 'A'],
            'Active':    ['yes', 'no', 'yes', 'no', 'yes'],
        })
        out = infer_and_convert_data_types(df)

        assert pd.api.types.is_datetime64_any_dtype(out['Birthdate'])
        assert str(out['Score'].dtype) == 'Int64'
        assert out['Score'].isna().sum() == 1
        assert str(out['Grade'].dtype) == 'category'
        assert str(out['Active'].dtype) == 'boolean'
