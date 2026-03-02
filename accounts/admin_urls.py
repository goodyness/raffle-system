from django.urls import path
from . import admin_views

urlpatterns = [
    path('dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('raffles/', admin_views.admin_raffle_list, name='admin_raffle_list'),
    path('raffles/<str:custom_id>/approve/', admin_views.approve_raffle, name='approve_raffle'),
    path('raffles/<str:custom_id>/decline/', admin_views.decline_raffle, name='decline_raffle'),
    path('raffles/<str:custom_id>/toggle-referral/', admin_views.toggle_raffle_referral, name='toggle_raffle_referral'),
    path('users/', admin_views.admin_user_list, name='admin_user_list'),
    path('withdrawals/', admin_views.admin_withdrawal_list, name='admin_withdrawal_list'),
    path('withdrawals/<int:withdrawal_id>/process/', admin_views.process_withdrawal, name='process_withdrawal'),
    path('users/<int:user_id>/suspend/', admin_views.admin_toggle_user_suspension, name='toggle_user_suspension'),
    path('users/<int:user_id>/delete/', admin_views.admin_delete_user, name='delete_user'),
    path('users/<int:user_id>/toggle-organizer/', admin_views.admin_toggle_organizer_approval, name='toggle_organizer_approval'),
    
    path('raffles/<str:custom_id>/detail/', admin_views.admin_raffle_detail, name='admin_raffle_detail'),
    path('raffles/<str:custom_id>/revoke/', admin_views.admin_revoke_raffle, name='revoke_raffle'),
    
    path('audit-log/', admin_views.admin_audit_log, name='admin_audit_log'),
    path('spam-radar/', admin_views.admin_spam_radar, name='admin_spam_radar'),
]
