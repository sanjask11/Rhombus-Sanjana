"""Shared pytest fixtures."""
import os

import boto3
import pytest
from moto import mock_aws

# ── Ensure fake AWS creds exist before boto3 is touched ──────────────────────
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_SESSION_TOKEN', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')


@pytest.fixture(autouse=True)
def _override_aws_settings(settings):
    """Force Django settings to use fake creds during tests."""
    settings.AWS_ACCESS_KEY_ID = 'testing'
    settings.AWS_SECRET_ACCESS_KEY = 'testing'
    settings.AWS_DEFAULT_REGION = 'us-east-1'


@pytest.fixture
def s3_mock():
    """Yield a mocked boto3 S3 client."""
    with mock_aws():
        yield boto3.client('s3', region_name='us-east-1')


@pytest.fixture
def s3_bucket(s3_mock):
    """Create a test bucket pre-populated with sample files."""
    bucket = 'test-bucket'
    s3_mock.create_bucket(Bucket=bucket)

    # A clean CSV
    s3_mock.put_object(
        Bucket=bucket, Key='clean.csv',
        Body=b'Name,Score\nAlice,90\nBob,75\nCarol,85',
    )
    # A CSV with the sample-data pattern (mixed numeric + "Not Available")
    s3_mock.put_object(
        Bucket=bucket, Key='sample.csv',
        Body=(b'Name,Birthdate,Score,Grade,Active\n'
              b'Alice,1/01/1990,90,A,yes\n'
              b'Bob,2/02/1991,75,B,no\n'
              b'Charlie,3/03/1992,85,A,yes\n'
              b'David,4/04/1993,70,B,no\n'
              b'Eve,5/05/1994,Not Available,A,yes\n'),
    )
    # A file that isn't csv/xlsx — must be filtered out
    s3_mock.put_object(Bucket=bucket, Key='readme.txt', Body=b'ignore me')
    # A file inside a folder
    s3_mock.put_object(Bucket=bucket, Key='folder/nested.csv', Body=b'x,y\n1,2')

    yield bucket
