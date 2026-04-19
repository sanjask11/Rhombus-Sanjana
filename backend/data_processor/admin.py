from django.contrib import admin

from .models import ProcessingHistory


@admin.register(ProcessingHistory)
class ProcessingHistoryAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'bucket', 'total_rows', 'processed_at']
    list_filter = ['bucket', 'processed_at']
    search_fields = ['file_name', 'bucket', 'file_key']
    readonly_fields = ['processed_at']
