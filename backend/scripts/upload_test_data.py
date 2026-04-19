#!/usr/bin/env python
"""Upload every file in ../test_data/ to an S3 bucket.

Usage:
    python scripts/upload_test_data.py <bucket-name>

Credentials are picked up from the standard boto3 chain (env vars,
~/.aws/credentials, etc.) — the same chain the Django app uses.
"""
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    bucket = sys.argv[1]
    data_dir = Path(__file__).resolve().parent.parent / 'test_data'
    if not data_dir.is_dir():
        print(f"error: {data_dir} does not exist", file=sys.stderr)
        return 1

    files = sorted(p for p in data_dir.iterdir() if p.is_file() and p.suffix in {'.csv', '.xlsx', '.xls'})
    if not files:
        print(f"error: no CSV/Excel files found in {data_dir}", file=sys.stderr)
        return 1

    s3 = boto3.client('s3')
    for f in files:
        try:
            s3.upload_file(str(f), bucket, f.name)
            print(f"  uploaded {f.name}  ({f.stat().st_size:,} bytes)")
        except (ClientError, BotoCoreError) as e:
            print(f"  FAILED {f.name}: {e}", file=sys.stderr)
            return 1

    print(f"\nDone. {len(files)} file(s) uploaded to s3://{bucket}/")
    return 0


if __name__ == '__main__':
    sys.exit(main())
