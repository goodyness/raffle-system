from django.urls import path
from . import views, image_utils

app_name = 'raffle'

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('about/', views.about_us, name='about_us'),
    path('contact/', views.contact_us, name='contact_us'),
    path('terms/', views.terms_and_conditions, name='terms_and_conditions'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('explore/', views.raffle_list, name='raffle_list'),
    path('verify-ticket/', views.verify_ticket, name='verify_ticket'),
    path('d/<str:custom_id>/', views.raffle_detail, name='raffle_detail'),
    path('d/<str:custom_id>/live/', views.raffle_live_draw, name='raffle_live_draw'),
    path('d/<str:custom_id>/join/', views.join_raffle, name='join_raffle'),
    
    # Payments
    path('verify-paystack/', views.verify_paystack, name='verify_paystack'),
    path('verify-flutterwave/', views.verify_flutterwave, name='verify_flutterwave'),
    path('success/<int:ticket_id>/', views.raffle_payment_success, name='raffle_payment_success'),
    
    # Participant
    path('dashboard/participant/', views.participant_dashboard, name='participant_dashboard'),
    
    # Organizer
    path('dashboard/', views.registrar_raffle_dashboard, name='registrar_raffle_dashboard'),
    path('partner-referrals/', views.partner_referral_dashboard, name='partner_referral_dashboard'),
    path('withdrawal/request/', views.request_raffle_withdrawal, name='request_raffle_withdrawal'),
    path('d/<str:custom_id>/lock/', views.lock_raffle, name='lock_raffle'),
    path('d/<str:custom_id>/draw/', views.generate_raffle_winners, name='generate_raffle_winners'),
    path('d/<str:custom_id>/analytics/', views.raffle_analytics_api, name='raffle_analytics_api'),
    path('api/recent-entries/', views.recent_entries_api, name='recent_entries_api'),
    path('d/<str:custom_id>/share-card.png', image_utils.generate_sharing_card, name='raffle_share_card'),
    path('wallet/history/', views.wallet_history, name='wallet_history'),
    path('d/<str:custom_id>/edit/', views.edit_raffle, name='edit_raffle'),
    path('d/<str:custom_id>/delete/', views.delete_raffle, name='delete_raffle'),
]
