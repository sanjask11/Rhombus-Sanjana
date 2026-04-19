"""Integration tests for the S3 client (using moto to mock AWS)."""
import io

import pandas as pd
import pytest

from data_processor.s3_utils import S3Client, S3Error


class TestListFiles:
    def test_lists_only_csv_and_excel(self, s3_bucket):
        """readme.txt must be filtered out, csv/xlsx must be included."""
        files = S3Client().list_files(s3_bucket)
        names = {f['name'] for f in files}
        assert 'clean.csv' in names
        assert 'sample.csv' in names
        assert 'nested.csv' in names
        assert 'readme.txt' not in names

    def test_file_metadata_shape(self, s3_bucket):
        files = S3Client().list_files(s3_bucket)
        f = files[0]
        assert {'key', 'name', 'size', 'size_display', 'last_modified', 'file_type'} <= f.keys()

    def test_nonexistent_bucket_raises(self, s3_mock):
        # s3_mock exists but no bucket was created
        with pytest.raises(S3Error, match='does not exist'):
            S3Client().list_files('never-created')


class TestLoadFile:
    def test_load_csv_returns_dataframe(self, s3_bucket):
        df = S3Client().load_file(s3_bucket, 'clean.csv')
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df.columns) == ['Name', 'Score']

    def test_load_sample_data_pattern(self, s3_bucket):
        df = S3Client().load_file(s3_bucket, 'sample.csv')
        assert len(df) == 5
        assert 'Not Available' in df['Score'].values

    def test_missing_file_raises(self, s3_bucket):
        with pytest.raises(S3Error, match='not found'):
            S3Client().load_file(s3_bucket, 'ghost.csv')

    def test_unsupported_extension_raises(self, s3_mock):
        s3_mock.create_bucket(Bucket='extras')
        s3_mock.put_object(Bucket='extras', Key='file.json', Body=b'{}')
        with pytest.raises(ValueError, match='Unsupported file type'):
            S3Client().load_file('extras', 'file.json')

    def test_load_csv_with_latin1_encoding(self, s3_mock):
        """CSV exported with non-UTF8 encoding should still parse via fallback."""
        s3_mock.create_bucket(Bucket='enc-bucket')
        # 'caf\xe9' is 'café' in latin-1 — not valid utf-8
        body = b'Name,City\nAlice,caf\xe9\nBob,na\xefve\n'
        s3_mock.put_object(Bucket='enc-bucket', Key='latin.csv', Body=body)

        df = S3Client().load_file('enc-bucket', 'latin.csv')
        assert len(df) == 2
        assert 'café' in df['City'].values

    def test_load_xlsx(self, s3_mock):
        """Round-trip an xlsx through S3 and load it back."""
        s3_mock.create_bucket(Bucket='excel-bucket')

        df_orig = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
        buf = io.BytesIO()
        df_orig.to_excel(buf, engine='openpyxl', index=False)
        s3_mock.put_object(Bucket='excel-bucket', Key='data.xlsx', Body=buf.getvalue())

        df_loaded = S3Client().load_file('excel-bucket', 'data.xlsx')
        assert len(df_loaded) == 3
        assert list(df_loaded.columns) == ['a', 'b']
