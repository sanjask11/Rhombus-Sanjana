import json
import logging

import numpy as np
import pandas as pd
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .infer_data_types import get_type_info, infer_and_convert_data_types
from .models import ProcessingHistory
from .s3_utils import S3Client, S3Error
from .serializers import ListFilesSerializer, ProcessFileSerializer

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame slice to a JSON-safe list of records."""
    preview = df.head(100).copy()
    for col in preview.columns:
        ds = str(preview[col].dtype)
        if 'datetime64' in ds:
            preview[col] = preview[col].astype(str).replace({'NaT': None})
        elif pd.api.types.is_categorical_dtype(preview[col]):
            preview[col] = preview[col].astype(object)
        elif 'complex' in ds:
            preview[col] = preview[col].astype(str)
        elif 'boolean' in ds:
            preview[col] = preview[col].astype(object)
    return json.loads(
        preview
        .replace({np.nan: None, np.inf: None, -np.inf: None})
        .to_json(orient='records', default_handler=str)
    )


def _first_error(serializer) -> str:
    """Flatten DRF serializer errors to a single human-readable message."""
    for field, errs in serializer.errors.items():
        if isinstance(errs, list) and errs:
            return f"{field}: {errs[0]}"
        if isinstance(errs, dict) and errs:
            inner_field, inner_errs = next(iter(errs.items()))
            msg = inner_errs[0] if isinstance(inner_errs, list) else inner_errs
            return f"{field}.{inner_field}: {msg}"
        return f"{field}: {errs}"
    return 'Invalid request.'


# ── Views ──────────────────────────────────────────────────────────────────────

class S3FilesView(APIView):
    """GET /api/s3/files/?bucket=<name>  →  list CSV/Excel files in bucket."""

    def get(self, request):
        serializer = ListFilesSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response({'error': _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)
        bucket = serializer.validated_data['bucket']
        try:
            files = S3Client().list_files(bucket)
            return Response({'files': files, 'bucket': bucket})
        except S3Error as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error('S3 list error: %s', e, exc_info=True)
            return Response({'error': 'Unexpected error listing files.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessFileView(APIView):
    """
    POST /api/process/
    Body: { bucket, file_key, type_overrides? }
    Returns inferred column types + first-100-row preview.
    """

    def post(self, request):
        serializer = ProcessFileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)
        bucket = serializer.validated_data['bucket']
        file_key = serializer.validated_data['file_key']
        type_overrides = serializer.validated_data['type_overrides']

        try:
            df = S3Client().load_file(bucket, file_key)
            df = infer_and_convert_data_types(df, type_overrides=type_overrides)
            type_info = get_type_info(df)
            data = _df_to_records(df)

            try:
                ProcessingHistory.objects.create(
                    bucket=bucket,
                    file_key=file_key,
                    file_name=file_key.split('/')[-1],
                    total_rows=len(df),
                    column_types={c['name']: c['dtype'] for c in type_info},
                )
            except Exception as hist_err:
                logger.warning('History save failed: %s', hist_err)

            return Response({
                'columns': type_info,
                'data': data,
                'total_rows': len(df),
                'preview_rows': len(data),
                'file_name': file_key.split('/')[-1],
            })

        except S3Error as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error('Processing error: %s', e, exc_info=True)
            return Response({'error': f'Processing failed: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessingHistoryView(APIView):
    """GET /api/history/  →  last 20 processed files."""

    def get(self, request):
        history = ProcessingHistory.objects.all()[:20]
        return Response({
            'history': [
                {
                    'id': h.id,
                    'bucket': h.bucket,
                    'file_name': h.file_name,
                    'file_key': h.file_key,
                    'total_rows': h.total_rows,
                    'processed_at': h.processed_at.isoformat(),
                    'column_count': len(h.column_types),
                }
                for h in history
            ]
        })
