from django.db import models


class ProcessingHistory(models.Model):
    bucket = models.CharField(max_length=255)
    file_key = models.CharField(max_length=1000)
    file_name = models.CharField(max_length=500)
    processed_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.IntegerField(default=0)
    column_types = models.JSONField(default=dict)

    class Meta:
        ordering = ['-processed_at']
        verbose_name = 'Processing History'
        verbose_name_plural = 'Processing Histories'

    def __str__(self):
        return f"{self.file_name} ({self.processed_at.strftime('%Y-%m-%d %H:%M')})"
