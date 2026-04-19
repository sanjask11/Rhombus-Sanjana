import io
import logging

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class S3Error(Exception):
    """Raised for any S3-related failure exposed to callers."""


# Encoding fallback order for CSV reads. utf-8 covers the common case; the
# BOM-prefixed variant handles files exported from Excel; latin-1/cp1252
# cover Windows-generated CSVs with non-ASCII characters.
_CSV_ENCODINGS = ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252')


def _fmt_size(n: int) -> str:
    """Format a byte count as a short human-readable string (e.g. '1.3 MB')."""
    for unit, thresh in (('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
        if n >= thresh:
            return f'{n / thresh:.1f} {unit}'
    return f'{n} B'


def _read_csv_with_fallback(content: bytes) -> pd.DataFrame:
    """Try each encoding in :data:`_CSV_ENCODINGS` until one parses cleanly."""
    last_error: Exception | None = None
    for enc in _CSV_ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(content), low_memory=False, encoding=enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue
    raise ValueError(f"Could not decode CSV with any of {_CSV_ENCODINGS}: {last_error}")


class S3Client:
    """Thin wrapper over boto3 for listing and loading tabular files from S3."""

    def __init__(self):
        kwargs = {'region_name': settings.AWS_DEFAULT_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        self.client = boto3.client('s3', **kwargs)

    def list_files(self, bucket: str) -> list:
        """Return metadata for every CSV/Excel object in *bucket*.

        Non-tabular keys (readme.txt, images, JSON, etc.) are filtered out.
        Results are sorted newest-first by ``last_modified``.
        """
        try:
            files = []
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.lower().endswith(('.csv', '.xlsx', '.xls')):
                        files.append({
                            'key': key,
                            'name': key.split('/')[-1],
                            'size': obj['Size'],
                            'size_display': _fmt_size(obj['Size']),
                            'last_modified': obj['LastModified'].isoformat(),
                            'file_type': 'csv' if key.lower().endswith('.csv') else 'excel',
                        })
            return sorted(files, key=lambda x: x['last_modified'], reverse=True)
        except ClientError as e:
            code = e.response['Error']['Code']
            msg = e.response['Error']['Message']
            if code == 'NoSuchBucket':
                raise S3Error(f"Bucket '{bucket}' does not exist.")
            if code in ('AccessDenied', 'AllAccessDisabled'):
                raise S3Error(f"Access denied to bucket '{bucket}'. Check your AWS credentials.")
            raise S3Error(f"S3 error: {msg}")
        except BotoCoreError as e:
            raise S3Error(f"AWS connection failed: {e}")

    def load_file(self, bucket: str, key: str) -> pd.DataFrame:
        """Download *key* from *bucket* and return it as a DataFrame.

        CSV reads try multiple encodings (utf-8, utf-8-sig, latin-1, cp1252)
        before giving up, so files exported from Excel or produced on Windows
        load cleanly without user intervention.
        """
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'NoSuchKey':
                raise S3Error(f"File '{key}' not found in bucket '{bucket}'.")
            raise S3Error(f"Failed to read file: {e.response['Error']['Message']}")
        except BotoCoreError as e:
            raise S3Error(f"Download failed: {e}")

        kl = key.lower()
        try:
            if kl.endswith('.csv'):
                return _read_csv_with_fallback(content)
            elif kl.endswith('.xlsx'):
                return pd.read_excel(io.BytesIO(content), engine='openpyxl')
            elif kl.endswith('.xls'):
                return pd.read_excel(io.BytesIO(content), engine='xlrd')
            else:
                raise ValueError("Unsupported file type. Must be .csv, .xlsx, or .xls")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse file: {e}")
