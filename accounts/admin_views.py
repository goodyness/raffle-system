from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from raffle.models import Raffle, RaffleWithdrawalRequest, RaffleTicket, AuditLog, RaffleAnalytics
from .models import CustomUser
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum
from raffle.tasks import send_raffle_revocation_status_email
from decimal import Decimal

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_raffles = Raffle.objects.count()
    pending_raffles = Raffle.objects.filter(is_approved=False).count()
    total_users = CustomUser.objects.count()
    
    # User Demographics
    total_participants = CustomUser.objects.filter(role='participant').count()
    total_organizers = CustomUser.objects.filter(role='organizer').count()
    
    # Financial Metrics
    analytics_agg = RaffleAnalytics.objects.aggregate(
        total_system_share=Sum('system_share'),
        total_host_share=Sum('host_share'),
        total_payouts=Sum('payout_pool'),
        total_unclaimed=Sum('unclaimed_prizes')
    )
    
    system_initial_revenue = analytics_agg['total_system_share'] or Decimal('0.00')
    total_unclaimed_prizes = analytics_agg['total_unclaimed'] or Decimal('0.00')
    total_organizer_earnings = analytics_agg['total_host_share'] or Decimal('0.00')
    total_winnings_paid = analytics_agg['total_payouts'] or Decimal('0.00')
    
    # Platform Fees (from paid tickets)
    total_platform_fees = RaffleTicket.objects.filter(is_paid=True).aggregate(Sum('platform_fee'))['platform_fee__sum'] or Decimal('0.00')
    
    # Withdrawal Processing Fees
    withdrawal_fee_count = RaffleWithdrawalRequest.objects.filter(status='approved').count()
    total_withdrawal_fees = Decimal(str(withdrawal_fee_count * 100))
    
    # Total System Revenue = Shares + Platform Fees + Withdrawal Fees + Unclaimed Prizes
    total_system_revenue = system_initial_revenue + total_platform_fees + total_withdrawal_fees + total_unclaimed_prizes
    
    # Pending Withdrawals
    pending_withdrawals_count = RaffleWithdrawalRequest.objects.filter(status='pending').count()
    pending_withdrawals_total = RaffleWithdrawalRequest.objects.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Today's Activity
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tickets_sold_today = RaffleTicket.objects.filter(purchased_at__gte=today_start, is_paid=True).count()
    revenue_today = RaffleTicket.objects.filter(purchased_at__gte=today_start, is_paid=True).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

    recent_raffles = Raffle.objects.order_by('-created_at')[:10]
    recent_withdrawals = RaffleWithdrawalRequest.objects.order_by('-requested_at')[:5]
    recent_audit_logs = AuditLog.objects.order_by('-created_at')[:5]
    
    # Audit log entry for dashboard access
    AuditLog.objects.create(
        user=request.user,
        action="ACCESS_DASHBOARD",
        description="Admin accessed the dashboard",
        ip_address=request.META.get('REMOTE_ADDR')
    )

    context = {
        'total_raffles': total_raffles,
        'pending_raffles': pending_raffles,
        'total_users': total_users,
        'total_participants': total_participants,
        'total_organizers': total_organizers,
        'total_system_revenue': total_system_revenue,
        'total_organizer_earnings': total_organizer_earnings,
        'total_winnings_paid': total_winnings_paid,
        'pending_withdrawals_count': pending_withdrawals_count,
        'pending_withdrawals_total': pending_withdrawals_total,
        'tickets_sold_today': tickets_sold_today,
        'revenue_today': revenue_today,
        'recent_raffles': recent_raffles,
        'recent_withdrawals': recent_withdrawals,
        'recent_audit_logs': recent_audit_logs,
    }
    return render(request, 'accounts/admin/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def admin_raffle_list(request):
    raffles = Raffle.objects.order_by('-created_at')
    return render(request, 'accounts/admin/raffle_list.html', {'raffles': raffles})

@login_required
@user_passes_test(is_admin)
def approve_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    raffle.is_approved = True
    raffle.save()
    messages.success(request, f"Raffle '{raffle.title}' has been approved.")
    return redirect('accounts:admin_raffle_list')

@login_required
@user_passes_test(is_admin)
def decline_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    raffle.delete() # Or set status to declined if we add a status field for rejection
    messages.warning(request, f"Raffle '{raffle.title}' has been declined and removed.")
    return redirect('accounts:admin_raffle_list')

@login_required
@user_passes_test(is_admin)
def toggle_raffle_referral(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    raffle.is_referral_enabled = not raffle.is_referral_enabled
    raffle.save()
    status = "enabled" if raffle.is_referral_enabled else "disabled"
    messages.success(request, f"Referrals for '{raffle.title}' have been {status}.")
    return redirect('accounts:admin_raffle_list')

@login_required
@user_passes_test(is_admin)
def admin_withdrawal_list(request):
    withdrawals = RaffleWithdrawalRequest.objects.order_by('-requested_at')
    return render(request, 'accounts/admin/withdrawal_list.html', {'withdrawals': withdrawals})

@login_required
@user_passes_test(is_admin)
def process_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(RaffleWithdrawalRequest, id=withdrawal_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            withdrawal.status = 'approved'
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
            from django.db import transaction
            from raffle.tasks import send_withdrawal_approved_email
            transaction.on_commit(lambda: send_withdrawal_approved_email.delay(withdrawal.id))
            messages.success(request, "Withdrawal approved.")
        elif action == 'reject':
            withdrawal.status = 'rejected'
            withdrawal.save()
            messages.warning(request, "Withdrawal rejected.")
    return redirect('accounts:admin_withdrawal_list')

@login_required
@user_passes_test(is_admin)
def admin_user_list(request):
    query = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')
    
    users_qs = CustomUser.objects.all().order_by('-date_joined')
    
    if query:
        users_qs = users_qs.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query)
        )
    
    if role_filter:
        users_qs = users_qs.filter(role=role_filter)
        
    paginator = Paginator(users_qs, 20)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    
    return render(request, 'accounts/admin/user_list.html', {
        'users': users,
        'query': query,
        'role_filter': role_filter
    })

@login_required
@user_passes_test(is_admin)
def admin_toggle_user_suspension(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if user == request.user:
        messages.error(request, "You cannot suspend yourself.")
        return redirect('accounts:admin_user_list')
        
    user.is_suspended = not user.is_suspended
    user.save()
    
    action = "SUSPENDED" if user.is_suspended else "RELEASED"
    AuditLog.objects.create(
        user=request.user,
        action=f"USER_{action}",
        description=f"Admin {action} user {user.email}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    messages.success(request, f"User {user.email} has been {action.lower()}.")
    return redirect('accounts:admin_user_list')

@login_required
@user_passes_test(is_admin)
def admin_delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if user == request.user:
        messages.error(request, "You cannot delete yourself.")
        return redirect('accounts:admin_user_list')
        
    email = user.email
    user.delete()
    
    AuditLog.objects.create(
        user=request.user,
        action="USER_DELETED",
        description=f"Admin deleted user {email}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    messages.warning(request, f"User {email} has been permanently removed.")
    return redirect('accounts:admin_user_list')

@login_required
@user_passes_test(is_admin)
def admin_raffle_detail(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    tickets_qs = raffle.tickets.all().order_by('-purchased_at')
    
    paginator = Paginator(tickets_qs, 20)
    page_number = request.GET.get('page')
    tickets = paginator.get_page(page_number)
    
    return render(request, 'accounts/admin/raffle_detail.html', {
        'raffle': raffle,
        'tickets': tickets
    })

@login_required
@user_passes_test(is_admin)
def admin_revoke_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    reason = request.POST.get('reason', 'Suspected violation of terms.')
    
    raffle.is_revoked = not raffle.is_revoked
    if raffle.is_revoked:
        raffle.revocation_reason = reason
        raffle.is_approved = False
    raffle.save()
    
    action = "REVOKED" if raffle.is_revoked else "RELEASED"
    
    # Trigger Celery Task for Notification
    from django.db import transaction
    transaction.on_commit(lambda: send_raffle_revocation_status_email.delay(
        raffle.id, 
        action.lower(), 
        reason if raffle.is_revoked else ''
    ))

    AuditLog.objects.create(
        user=request.user,
        action=f"RAFFLE_{action}",
        description=f"Admin {action} raffle {raffle.custom_id}. Reason: {reason}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    messages.success(request, f"Raffle '{raffle.title}' has been {action.lower()}.")
    return redirect('accounts:admin_raffle_detail', custom_id=custom_id)

@login_required
@user_passes_test(is_admin)
def admin_toggle_organizer_approval(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if user.role != 'organizer':
        messages.error(request, "This user is not an organizer.")
        return redirect('accounts:admin_user_list')
        
    user.is_verified = not user.is_verified
    user.save()
    
    action = "APPROVED" if user.is_verified else "REVOKED"
    AuditLog.objects.create(
        user=request.user,
        action=f"ORGANIZER_APPROVAL_{action}",
        description=f"Admin {action} organizer status for {user.email}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    messages.success(request, f"Organizer approval for {user.email} has been {action.lower()}.")
    return redirect('accounts:admin_user_list')

@login_required
@user_passes_test(is_admin)
def admin_audit_log(request):
    logs_qs = AuditLog.objects.all().order_by('-created_at')
    
    paginator = Paginator(logs_qs, 50)
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)
    
    return render(request, 'accounts/admin/audit_log.html', {'logs': logs})

@login_required
@user_passes_test(is_admin)
def admin_spam_radar(request):
    # Basic logic to find users with many tickets in a short time
    # This is a placeholder for more complex logic
    from django.db.models import Count
    from datetime import timedelta
    
    recent_time = timezone.now() - timedelta(hours=24)
    suspicious_users = CustomUser.objects.annotate(
        recent_ticket_count=Count('raffleticket', filter=Q(raffleticket__purchased_at__gte=recent_time))
    ).filter(recent_ticket_count__gt=20).order_by('-recent_ticket_count')
    
    return render(request, 'accounts/admin/spam_radar.html', {
        'suspicious_users': suspicious_users
    })
