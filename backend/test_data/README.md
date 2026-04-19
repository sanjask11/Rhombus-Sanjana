# Test Data

Seven curated CSV files exercising every inference path in
`data_processor.infer_data_types`. Upload with:

```bash
python scripts/upload_test_data.py <your-bucket>
```

## Files and what they test

| File | Columns | Inference target |
|---|---|---|
| `all_types.csv` | id, name, active, score, grade, price, joined, session_length | Integer, Text, Boolean, nullable Int64, Category, Decimal, Date/Time, Time Delta |
| `sales.csv` | order_id, customer, product, quantity, unit_price, total, order_date, shipped | Realistic mix — downcast integers, Category (product), Decimal, Date/Time, Boolean |
| `signals.csv` | sample_id, captured_at, frequency_hz, amplitude, channel | Complex numbers, ISO-with-timezone datetimes |
| `boolean_formats.csv` | true_false, yes_no, t_f, on_off, y_n, mixed_case | Every boolean token in `BOOL_MAP`, including case-insensitive mixed |
| `datetime_formats.csv` | iso_date, us_slash, with_time, with_tz, month_name | Every format in `DATETIME_FORMATS` |
| `edge_cases.csv` | id, notes, mostly_null, scientific, negative_float, big_int | All-unique text, sparse nulls, scientific notation, negatives, int16/int32 downcast |
| `messy_encoding.csv` | name, city, notes | latin-1 bytes (café, naïve, Zürich) — proves the encoding fallback |
