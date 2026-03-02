from django.urls import path
from . import views
from django.urls import include

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/organizer/', views.register_organizer, name='register_organizer'),
    path('register/participant/', views.register_participant, name='register_participant'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/verify/', views.password_reset_verify, name='password_reset_verify'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('settings/', views.profile_settings, name='profile_settings'),
    path('manage/', include('accounts.admin_urls')),
]
