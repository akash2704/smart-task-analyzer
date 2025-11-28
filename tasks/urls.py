from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Frontend Views
    path('', views.index, name='index'),
    
    # API Endpoints - Analysis & Suggestions
    path('api/tasks/analyze/', views.api_analyze, name='api_analyze'),
    path('api/tasks/suggest/', views.api_suggest, name='api_suggest'),
    path('api/tasks/stats/', views.api_stats, name='api_stats'),
    path('api/tasks/detect-cycles/', views.api_detect_cycles, name='api_detect_cycles'),
]