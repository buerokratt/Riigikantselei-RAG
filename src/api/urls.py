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
from django.contrib import admin
from django.urls import include, path
from rest_framework import routers

from core.views import (
    CoreVariableViewSet,
    ElasticDocumentDetailView,
    TextSearchConversationViewset,
)
from user_profile.views import GetTokenView, LogOutView, UserProfileViewSet

PREFIX = 'api'
GET_TOKEN_VIEW_URL = f'{PREFIX}/get_token'
LOG_OUT_VIEW_URL = f'{PREFIX}/log_out'

router = routers.DefaultRouter()
router.register(f'{PREFIX}/core_settings', CoreVariableViewSet, basename='core_settings')
router.register(f'{PREFIX}/user_profile', UserProfileViewSet, basename='user_profile')
router.register(f'{PREFIX}/text_search', TextSearchConversationViewset, basename='text_search')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path(
        f'{PREFIX}/elastic/<str:index>/<str:document_id>/',
        ElasticDocumentDetailView.as_view(),
        name='document_detail',
    ),
    path(GET_TOKEN_VIEW_URL, GetTokenView.as_view(), name='get_token'),
    path(LOG_OUT_VIEW_URL, LogOutView.as_view(), name='log_out'),
]
