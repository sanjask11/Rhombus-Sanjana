"""End-to-end API tests for the Django views (with mocked S3)."""
import json

import pytest
from django.test import Client

from data_processor.models import ProcessingHistory


@pytest.fixture
def api():
    return Client()


# ── /api/s3/files/ ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestS3FilesEndpoint:
    URL = '/api/s3/files/'

    def test_missing_bucket_param(self, api):
        response = api.get(self.URL)
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_lists_files(self, api, s3_bucket):
        response = api.get(self.URL, {'bucket': s3_bucket})
        assert response.status_code == 200
        body = response.json()
        assert body['bucket'] == s3_bucket
        assert len(body['files']) == 3  # clean.csv, sample.csv, nested.csv

    def test_nonexistent_bucket_returns_400(self, api, s3_mock):
        response = api.get(self.URL, {'bucket': 'ghost-bucket'})
        assert response.status_code == 400
        assert 'does not exist' in response.json()['error']


# ── /api/process/ ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProcessEndpoint:
    URL = '/api/process/'

    def _post(self, api, body):
        return api.post(self.URL, data=json.dumps(body), content_type='application/json')

    def test_missing_params(self, api):
        response = self._post(api, {})
        assert response.status_code == 400

    def test_missing_file_key(self, api):
        response = self._post(api, {'bucket': 'b'})
        assert response.status_code == 400

    def test_type_overrides_must_be_dict(self, api):
        response = self._post(api, {'bucket': 'b', 'file_key': 'f.csv', 'type_overrides': 'not-a-dict'})
        assert response.status_code == 400

    def test_unknown_override_type_rejected(self, api):
        response = self._post(api, {
            'bucket': 'b', 'file_key': 'f.csv',
            'type_overrides': {'col': 'not_a_real_type'},
        })
        assert response.status_code == 400
        assert 'Unsupported override type' in response.json()['error']

    def test_blank_bucket_rejected(self, api):
        response = self._post(api, {'bucket': '   ', 'file_key': 'f.csv'})
        assert response.status_code == 400

    def test_processes_sample_file(self, api, s3_bucket):
        response = self._post(api, {'bucket': s3_bucket, 'file_key': 'sample.csv'})
        assert response.status_code == 200
        body = response.json()

        assert body['file_name'] == 'sample.csv'
        assert body['total_rows'] == 5
        assert len(body['columns']) == 5

        by_name = {c['name']: c for c in body['columns']}
        assert by_name['Birthdate']['display_type'] == 'Date/Time'
        assert by_name['Score']['display_type'] == 'Integer'
        assert by_name['Score']['null_count'] == 1
        assert by_name['Grade']['display_type'] == 'Category'
        assert by_name['Active']['display_type'] == 'Boolean'

    def test_returns_row_preview(self, api, s3_bucket):
        response = self._post(api, {'bucket': s3_bucket, 'file_key': 'clean.csv'})
        body = response.json()
        assert len(body['data']) == 3
        assert body['data'][0]['Name'] == 'Alice'

    def test_apply_type_override(self, api, s3_bucket):
        """Force Grade → Text instead of the auto-inferred Category."""
        response = self._post(api, {
            'bucket': s3_bucket,
            'file_key': 'sample.csv',
            'type_overrides': {'Grade': 'text'},
        })
        assert response.status_code == 200
        grade_col = next(c for c in response.json()['columns'] if c['name'] == 'Grade')
        assert grade_col['display_type'] == 'Text'

    def test_processing_saves_history(self, api, s3_bucket):
        assert ProcessingHistory.objects.count() == 0
        self._post(api, {'bucket': s3_bucket, 'file_key': 'clean.csv'})
        assert ProcessingHistory.objects.count() == 1

        record = ProcessingHistory.objects.first()
        assert record.file_name == 'clean.csv'
        assert record.total_rows == 3

    def test_missing_file_returns_400(self, api, s3_bucket):
        response = self._post(api, {'bucket': s3_bucket, 'file_key': 'missing.csv'})
        assert response.status_code == 400


# ── /api/history/ ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHistoryEndpoint:
    URL = '/api/history/'

    def test_empty_history(self, api):
        response = api.get(self.URL)
        assert response.status_code == 200
        assert response.json()['history'] == []

    def test_returns_recent(self, api):
        ProcessingHistory.objects.create(
            bucket='b', file_key='f.csv', file_name='f.csv',
            total_rows=10, column_types={'x': 'Int64'},
        )
        body = api.get(self.URL).json()
        assert len(body['history']) == 1
        assert body['history'][0]['file_name'] == 'f.csv'
        assert body['history'][0]['column_count'] == 1
