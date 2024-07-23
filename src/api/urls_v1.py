"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, path
from rest_framework import routers

from core.views import CoreVariableViewSet, DatasetViewset, ElasticDocumentDetailView
from document_search.views import DocumentSearchConversationViewset
from health.views import HealthView
from text_search.views import TextSearchConversationViewset
from user_profile.views import GetTokenView, LogOutView, UserProfileViewSet

router = routers.DefaultRouter()
router.register('core_settings', CoreVariableViewSet, basename='core_settings')
router.register('dataset', DatasetViewset, basename='dataset')
router.register('user_profile', UserProfileViewSet, basename='user_profile')
router.register('text_search', TextSearchConversationViewset, basename='text_search')
router.register('document_search', DocumentSearchConversationViewset, basename='document_search')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'elastic/<str:index>/<str:document_id>/',
        ElasticDocumentDetailView.as_view(),
        name='document_detail',
    ),
    path('get_token', GetTokenView.as_view(), name='get_token'),
    path('log_out', LogOutView.as_view(), name='log_out'),
    path('health', HealthView.as_view(), name='health'),
]
