"""Request/response serializers for the data_processor API.

Centralising input validation here keeps views focused on business logic
and gives clients consistent 400-level error payloads (one shape, one
source of truth) instead of ad-hoc `if not x:` checks scattered across
handlers.
"""
from rest_framework import serializers

# Accepted keys for per-column type overrides. Keep this in sync with the
# converter map in :func:`data_processor.infer_data_types.apply_type_override`.
SUPPORTED_OVERRIDE_TYPES = {
    'int64', 'integer',
    'float64', 'decimal',
    'bool', 'boolean',
    'datetime64', 'date',
    'timedelta', 'duration',
    'category',
    'object', 'text', 'string',
    'complex',
}


class ListFilesSerializer(serializers.Serializer):
    """Query params for ``GET /api/s3/files/``."""

    bucket = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=63,  # S3 bucket-name limit
        help_text='S3 bucket name to list CSV/Excel files from.',
    )


class ProcessFileSerializer(serializers.Serializer):
    """Body for ``POST /api/process/``."""

    bucket = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=63,
    )
    file_key = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=1024,  # S3 key-length limit
    )
    type_overrides = serializers.DictField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        default=dict,
    )

    def validate_type_overrides(self, value: dict) -> dict:
        """Lowercase override values and reject unknown type names early."""
        normalised: dict[str, str] = {}
        for col, target in value.items():
            key = str(target).lower().strip()
            if key not in SUPPORTED_OVERRIDE_TYPES:
                raise serializers.ValidationError(
                    f"Unsupported override type '{target}' for column '{col}'. "
                    f"Supported: {sorted(SUPPORTED_OVERRIDE_TYPES)}"
                )
            normalised[col] = key
        return normalised
