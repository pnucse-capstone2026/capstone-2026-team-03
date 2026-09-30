from django.urls import path

from .views import (
    AnalysisCreateView,
    AnalysisResultView,
    AnalysisStatusView,
    CustomSentenceCreateView,
    CustomSentenceDeleteView,
    LifestyleTranscriptionView,
    RecordListView,
    SentenceDetailView,
    SentenceListView,
    SentenceRecommendationView,
    StatisticsSummaryView,
)


urlpatterns = [
    path("sentences", SentenceListView.as_view(), name="sentence-list"),
    path("sentences/custom", CustomSentenceCreateView.as_view(), name="sentence-custom-create"),
    path(
        "sentences/custom/<int:sentence_id>",
        CustomSentenceDeleteView.as_view(),
        name="sentence-custom-delete",
    ),
    path(
        "sentences/recommendation",
        SentenceRecommendationView.as_view(),
        name="sentence-recommendation",
    ),
    path(
        "sentences/<int:sentence_id>",
        SentenceDetailView.as_view(),
        name="sentence-detail",
    ),
    path("analyses", AnalysisCreateView.as_view(), name="analysis-create"),
    path(
        "lifestyle/transcribe",
        LifestyleTranscriptionView.as_view(),
        name="lifestyle-transcribe",
    ),
    path(
        "analyses/<uuid:analysis_id>/status",
        AnalysisStatusView.as_view(),
        name="analysis-status",
    ),
    path(
        "analyses/<uuid:analysis_id>",
        AnalysisResultView.as_view(),
        name="analysis-result",
    ),
    path("records", RecordListView.as_view(), name="record-list"),
    path(
        "statistics/summary",
        StatisticsSummaryView.as_view(),
        name="statistics-summary",
    ),
]
