import logging
import re
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Boolean helpers ────────────────────────────────────────────────────────────

BOOL_MAP = {
    'true': True, 'false': False,
    'yes': True,  'no': False,
    '1': True,    '0': False,
    't': True,    'f': False,
    'on': True,   'off': False,
    'y': True,    'n': False,
}

# ── Datetime formats to try in order ──────────────────────────────────────────

DATETIME_FORMATS = [
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%m/%d/%Y',
    '%Y/%m/%d',
    '%d-%m-%Y',
    '%m-%d-%Y',
    '%Y-%m-%d %H:%M:%S',
    '%d/%m/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M:%SZ',
    '%Y-%m-%dT%H:%M:%S.%fZ',
    '%Y%m%d',
    '%d %b %Y',
    '%d %B %Y',
    '%b %d, %Y',
    '%B %d, %Y',
    '%d-%b-%Y',
    '%d-%B-%Y',
]

# Matches strings like "3+4j", "1-2.5j", "5j", "(1, 2)"
COMPLEX_RE = re.compile(
    r'^[+-]?\d*\.?\d+[eE][+-]?\d+[+-]\d*\.?\d+[eE]?[+-]?\d*[jJ]$'
    r'|^[+-]?\d*\.?\d+[+-]\d*\.?\d*[jJ]$'
    r'|^[+-]?\d*\.?\d*[jJ]$'
    r'|^\(\s*[+-]?\d*\.?\d+\s*,\s*[+-]?\d*\.?\d+\s*\)$'
)

# Strict timedelta hint: requires explicit duration keywords, short-forms
# (e.g. "3d", "5h"), or ISO-8601 "P..." syntax. Pure "HH:MM:SS" strings are
# intentionally excluded — they're more often meant as time-of-day.
TIMEDELTA_HINT_RE = re.compile(
    r'\bdays?\b'
    r'|\bhours?\b'
    r'|\bmin(?:ute)?s?\b'
    r'|\bsec(?:ond)?s?\b'
    r'|\d+\s*[dhms]\b'
    r'|^P\d',
    re.IGNORECASE,
)

# ── Private helpers ────────────────────────────────────────────────────────────

def _is_bool_series(non_null: pd.Series) -> bool:
    """True iff every value is a recognised boolean token.

    Purely-numeric columns of just "0"/"1" are excluded so they can be
    classified as integers instead (more useful default).
    """
    unique_lower = {str(v).lower().strip() for v in non_null.unique()}
    if not unique_lower or not unique_lower.issubset(BOOL_MAP):
        return False
    # Ambiguous: {"0","1"} alone — let the numeric branch handle it
    if unique_lower.issubset({'0', '1'}):
        return False
    return True


def _convert_to_bool(series: pd.Series) -> pd.Series:
    def _parse(val):
        if pd.isna(val):
            return pd.NA
        result = BOOL_MAP.get(str(val).lower().strip())
        return result if result is not None else pd.NA
    return series.map(_parse).astype('boolean')


def _is_complex_series(sample: pd.Series) -> bool:
    if len(sample) == 0:
        return False
    hit_rate = sample.apply(
        lambda x: bool(COMPLEX_RE.match(str(x).replace(' ', '')))
    ).mean()
    return hit_rate > 0.8


def _convert_to_complex(series: pd.Series) -> pd.Series:
    def _parse(val):
        if pd.isna(val):
            return None
        s = str(val).replace(' ', '')
        m = re.match(r'^\(([+-]?\d*\.?\d+),([+-]?\d*\.?\d+)\)$', s)
        if m:
            return complex(float(m.group(1)), float(m.group(2)))
        try:
            return complex(s)
        except (ValueError, TypeError):
            return None
    return series.apply(_parse)


def _try_datetime(series: pd.Series) -> Optional[pd.Series]:
    """Try to parse *series* as datetime.

    Walks the explicit :data:`DATETIME_FORMATS` list first (fast path), then
    falls back to pandas' flexible parser. Returns the converted series only
    if ≥ 80 % of the non-null values parsed successfully; otherwise ``None``.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return None

    for fmt in DATETIME_FORMATS:
        try:
            converted = pd.to_datetime(series, format=fmt, errors='coerce')
            if converted.notna().sum() / len(non_null) >= 0.8:
                return converted
        except Exception:
            continue

    # Flexible fallback — handles mixed / non-standard formats
    import warnings
    for kwargs in [
        {'format': 'mixed', 'dayfirst': False},
        {'dayfirst': False},
    ]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                converted = pd.to_datetime(series, errors='coerce', **kwargs)
            if converted.notna().sum() / len(non_null) >= 0.8:
                return converted
        except Exception:
            continue

    return None


def _try_timedelta(series: pd.Series, sample_size: int = 100) -> Optional[pd.Series]:
    """Try to parse *series* as timedelta.

    Only attempts conversion when ≥ 80 % of a sample contains explicit
    duration hints (``days``, ``hours``, short forms like ``3d``/``5h``, or
    ISO-8601 ``P…`` strings). This guard prevents misclassifying integer
    columns — ``pd.to_timedelta(1)`` would otherwise become ``1 nanosecond``.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return None

    sample = non_null if len(non_null) <= sample_size else non_null.sample(sample_size, random_state=42)
    hint_rate = sample.apply(lambda x: bool(TIMEDELTA_HINT_RE.search(str(x)))).mean()
    if hint_rate < 0.8:
        return None

    try:
        converted = pd.to_timedelta(series, errors='coerce')
        if converted.notna().sum() / len(non_null) >= 0.8:
            return converted
    except Exception:
        pass
    return None


def _downcast_int(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mn >= 0:
        for dtype in (np.uint8, np.uint16, np.uint32, np.uint64):
            if mx <= np.iinfo(dtype).max:
                return series.astype(dtype)
    else:
        for dtype in (np.int8, np.int16, np.int32, np.int64):
            info = np.iinfo(dtype)
            if mn >= info.min and mx <= info.max:
                return series.astype(dtype)
    return series


def _optimize_numeric(series: pd.Series) -> pd.Series:
    if series.isna().any():
        if pd.api.types.is_float_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0 and (non_null % 1 == 0).all():
                return series.astype('Int64')  # nullable integer
        return series

    if pd.api.types.is_float_dtype(series):
        non_null = series.dropna()
        if len(non_null) > 0 and (non_null % 1 == 0).all():
            return _downcast_int(series.astype(np.int64))
        return pd.to_numeric(series, downcast='float')

    if pd.api.types.is_integer_dtype(series):
        return _downcast_int(series)

    return series

# ── Public API ─────────────────────────────────────────────────────────────────

def infer_and_convert_data_types(
    df: pd.DataFrame,
    category_threshold: float = 0.5,
    sample_size: int = 10_000,
    type_overrides: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Infer and convert data types for every column in *df*.

    Priority order:
      Boolean → Numeric → Complex → Datetime → Timedelta → Categorical → Text (object)

    Args:
        df: Input DataFrame (all-object dtype is fine).
        category_threshold: Max (unique / total) ratio to treat as Categorical.
        sample_size: Rows sampled for inference on large datasets.
        type_overrides: {column_name: target_type_string} applied before inference.
    """
    if type_overrides is None:
        type_overrides = {}

    df = df.copy()

    for col in df.columns:
        if col in type_overrides:
            df[col] = apply_type_override(df[col], type_overrides[col])
            continue

        series = df[col]

        # Already a typed column — only optimize numerics
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                df[col] = _optimize_numeric(series)
            continue

        non_null = series.dropna()
        if len(non_null) == 0:
            continue

        sample = non_null if len(non_null) <= sample_size else non_null.sample(sample_size, random_state=42)

        # 1 ── Boolean
        if _is_bool_series(non_null):
            df[col] = _convert_to_bool(series)
            continue

        # 2 ── Numeric (tolerates up to 20 % non-parseable as NaN)
        numeric = pd.to_numeric(series, errors='coerce')
        if len(non_null) > 0 and numeric.notna().sum() / len(non_null) >= 0.8:
            df[col] = _optimize_numeric(numeric)
            continue

        # 3 ── Complex
        if _is_complex_series(sample):
            df[col] = _convert_to_complex(series)
            continue

        # 4 ── Datetime
        dt = _try_datetime(series)
        if dt is not None:
            df[col] = dt
            continue

        # 5 ── Timedelta
        td = _try_timedelta(series)
        if td is not None:
            df[col] = td
            continue

        # 6 ── Categorical
        if len(series) > 0 and series.nunique() / len(series) < category_threshold:
            df[col] = pd.Categorical(series)
            continue

        # 7 ── Keep as text / object

    return df


def apply_type_override(series: pd.Series, target_type: str) -> pd.Series:
    """Force a column to a specific type, ignoring inference."""
    key = target_type.lower().strip()
    converters = {
        'int64':     lambda s: pd.to_numeric(s, errors='coerce').astype('Int64'),
        'integer':   lambda s: pd.to_numeric(s, errors='coerce').astype('Int64'),
        'float64':   lambda s: pd.to_numeric(s, errors='coerce').astype('float64'),
        'decimal':   lambda s: pd.to_numeric(s, errors='coerce').astype('float64'),
        'bool':      _convert_to_bool,
        'boolean':   _convert_to_bool,
        'datetime64': lambda s: pd.to_datetime(s, errors='coerce'),
        'date':      lambda s: pd.to_datetime(s, errors='coerce'),
        'timedelta': lambda s: pd.to_timedelta(s, errors='coerce'),
        'duration':  lambda s: pd.to_timedelta(s, errors='coerce'),
        'category':  lambda s: pd.Categorical(s),
        'object':    lambda s: s.astype(str).where(s.notna(), other=None),
        'text':      lambda s: s.astype(str).where(s.notna(), other=None),
        'string':    lambda s: s.astype(str).where(s.notna(), other=None),
        'complex':   _convert_to_complex,
    }
    converter = converters.get(key)
    if converter:
        try:
            return converter(series)
        except Exception as e:
            logger.warning("Override to %s failed for series: %s", target_type, e)
    return series


# ── Display type mapping ───────────────────────────────────────────────────────

_DTYPE_DISPLAY = {
    'object': 'Text', 'string': 'Text',
    'int8': 'Integer',  'int16': 'Integer',  'int32': 'Integer',  'int64': 'Integer',
    'Int8': 'Integer',  'Int16': 'Integer',  'Int32': 'Integer',  'Int64': 'Integer',
    'uint8': 'Integer', 'uint16': 'Integer', 'uint32': 'Integer', 'uint64': 'Integer',
    'float32': 'Decimal', 'float64': 'Decimal',
    'bool': 'Boolean', 'boolean': 'Boolean',
    'category': 'Category',
    'complex64': 'Complex Number', 'complex128': 'Complex Number',
}


def get_type_info(df: pd.DataFrame) -> list:
    """Return per-column metadata including inferred display type."""
    result = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if 'datetime64' in dtype_str:
            display = 'Date/Time'
        elif 'timedelta' in dtype_str:
            display = 'Time Delta'
        else:
            display = _DTYPE_DISPLAY.get(dtype_str, 'Text')

        result.append({
            'name': col,
            'dtype': dtype_str,
            'display_type': display,
            'null_count': int(df[col].isna().sum()),
            'unique_count': int(df[col].nunique()),
            'sample_values': [str(v) for v in df[col].dropna().head(5).tolist()],
        })
    return result
