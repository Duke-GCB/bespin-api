from django.conf.urls import url, include
from django.contrib import admin
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include('data.urls')),
    url(r'^api/v2/', include('bespin_api_v2.urls')),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^api-auth-token/', obtain_auth_token),
    url(r'^auth/', include('gcb_web_auth.urls')),
]
