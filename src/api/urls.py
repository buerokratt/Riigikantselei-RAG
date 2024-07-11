from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='api/v1/', permanent=False), name='home'),
    # reroute root to version prefix
    path('api', RedirectView.as_view(url='api/v1/', permanent=False), name='index'),
    path('api/v1/', include(('api.urls_v1', 'rk_api_v1'), namespace='v1')),
]
