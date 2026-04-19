from django.urls import path

from .views import ProcessFileView, ProcessingHistoryView, S3FilesView

urlpatterns = [
    path('s3/files/', S3FilesView.as_view(), name='s3-files'),
    path('process/', ProcessFileView.as_view(), name='process-file'),
    path('history/', ProcessingHistoryView.as_view(), name='processing-history'),
]
