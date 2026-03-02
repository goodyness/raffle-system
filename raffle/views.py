import hashlib
import uuid
import logging
import random
import requests
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from accounts.views import sync_user_winnings
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings

from .models import Raffle, RaffleTicket, RaffleWallet, RaffleWithdrawalRequest, RaffleCategory, RaffleAnalytics, WalletTransaction
from .forms import RaffleForm, RaffleWithdrawalForm
from .tasks import (
    send_raffle_entry_email, 
    send_raffle_winner_email, 
    send_raffle_readiness_notification,
    send_raffle_creation_notification_email,
    send_raffle_withdrawal_notification_email,
    settle_unclaimed_winnings
)

logger = logging.getLogger(__name__)

# --- Public Views ---

def raffle_list(request):
    """List all approved raffles."""
    raffle_qs = Raffle.objects.filter(is_approved=True, is_revoked=False).order_by('-created_at')
    categories = RaffleCategory.objects.all()
    
    # Status filter
    status_filter = request.GET.get('status')
    if status_filter:
        raffle_qs = raffle_qs.filter(status=status_filter)
    
    # Category filter
    cat_slug = request.GET.get('category')
    if cat_slug:
        raffle_qs = raffle_qs.filter(category__slug=cat_slug)
    
    # Simple search
    query = request.GET.get('q')
    if query:
        raffle_qs = raffle_qs.filter(title__icontains=query)
        
    paginator = Paginator(raffle_qs, 6)
    page_number = request.GET.get('page')
    raffles = paginator.get_page(page_number)
    return render(request, 'raffle/raffle_list.html', {
        'raffles': raffles,
        'status_filter': status_filter,
        'categories': categories,
        'active_category': cat_slug
    })

def home(request):
    """Modern home page showing only 3 most recent active raffles."""
    recent_raffles = Raffle.objects.filter(
        is_approved=True, 
        is_revoked=False, 
        status='active'
    ).order_by('-created_at')[:3]
    
    categories = RaffleCategory.objects.all()
    
    return render(request, 'home.html', {
        'raffles': recent_raffles,
        'categories': categories,
    })

def terms_and_conditions(request):
    """Render the Terms and Conditions legal page."""
    return render(request, 'legal/terms.html')

def privacy_policy(request):
    """Render the Privacy Policy legal page."""
    return render(request, 'legal/privacy.html')

def about_us(request):
    """Render the About Us corporate page."""
    return render(request, 'corporate/about.html')

def contact_us(request):
    """Render the Contact corporate page."""
    return render(request, 'corporate/contact.html')

def custom_404(request, exception):
    """Render a custom 404 error page."""
    return render(request, '404.html', status=404)

def custom_500(request):
    """Render a custom 500 error page."""
    return render(request, '500.html', status=500)

def verify_ticket(request):
    """Check the status of a ticket ID."""
    ticket_id = request.GET.get('ticket_id') or request.POST.get('ticket_id')
    if not ticket_id:
        return JsonResponse({'error': 'No ticket ID provided'}, status=400)
    
    try:
        ticket = RaffleTicket.objects.select_related('raffle').get(ticket_number=ticket_id)
        raffle = ticket.raffle
        
        status = "unknown"
        message = ""
        
        if raffle.is_revoked:
            status = "revoked"
            message = "This raffle has been suspended for review."
        elif raffle.status in ['active', 'locked']:
            status = "ongoing"
            message = "This campaign is still ongoing. Winners haven't been picked yet!"
        elif raffle.status == 'ended':
            if ticket.is_winner:
                status = "won"
                message = f"CONGRATULATIONS! You won ₦{ticket.amount_won:,.0f}!"
            else:
                status = "lost"
                message = "Unfortunately, this ticket didn't win this time."

        return JsonResponse({
            'status': status,
            'message': message,
            'raffle_title': raffle.title,
            'ticket_number': ticket.ticket_number,
            'amount_played': float(ticket.amount_paid),
            'amount_won': float(ticket.amount_won) if ticket.is_winner else 0,
            'raffle_id': raffle.custom_id
        })
        
    except RaffleTicket.DoesNotExist:
        return JsonResponse({'error': 'Invalid Ticket ID. Please check and try again.'}, status=404)

def raffle_detail(request, custom_id):
    """Detailed view of a single raffle."""
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    
    # Referral logic
    ref_code = request.GET.get('ref')
    if ref_code:
        request.session[f'raffle_ref_{raffle.id}'] = ref_code
    
    paid_entries_count = raffle.tickets.filter(is_paid=True).count()
    current_revenue = Decimal(str(paid_entries_count)) * raffle.price
    estimated_total_payout = (current_revenue * raffle.payout_percentage) / 100
    
    payout_per_winner = 0
    if raffle.num_winners > 0:
        payout_per_winner = estimated_total_payout / raffle.num_winners

    participant_qs = raffle.tickets.filter(is_paid=True).order_by('-purchased_at')
    # Original participant_qs and pagination (to be replaced/modified)
    # participant_qs = raffle.tickets.filter(is_paid=True).order_by('-purchased_at')
    # paginator = Paginator(participant_qs, 10) # 10 per page as requested
    # page_number = request.GET.get('page')
    # participants = paginator.get_page(page_number)
    
    winners = []
    if raffle.status == 'ended':
        all_participants = raffle.tickets.filter(is_paid=True).order_by('-purchased_at')
    else:
        all_participants = raffle.tickets.filter(is_paid=True).order_by('-purchased_at') # Ensure all_participants is defined
    paginator = Paginator(all_participants, 10)
    page_number = request.GET.get('page')
    participants_page = paginator.get_page(page_number)

    winners = raffle.tickets.filter(is_winner=True).order_by('-amount_won') # Re-fetch winners if status is ended, or keep empty if not
    
    user_ticket = None
    if request.user.is_authenticated:
        user_ticket = raffle.tickets.filter(user=request.user, is_paid=True).first()

    return render(request, 'raffle/raffle_detail.html', {
        'raffle': raffle,
        'paid_entries_count': paid_entries_count,
        'estimated_total_payout': estimated_total_payout,
        'payout_per_winner': payout_per_winner,
        'participants': participants_page,
        'winners': winners,
        'user_ticket': user_ticket
    })

def recent_entries_api(request):
    """API for the live ticker."""
    from raffle.models import RaffleTicket
    recent_tickets = RaffleTicket.objects.filter(
        is_paid=True, 
        is_bonus=False,
        raffle__status='active'
    ).order_by('-purchased_at')[:5]
    data = []
    for t in recent_tickets:
        data.append({
            'name': t.name,
            'raffle_title': t.raffle.title,
            'raffle_id': t.raffle.custom_id,
        })
    return JsonResponse({'entries': data})

def raffle_live_draw(request, custom_id):
    """Animation page for the live draw."""
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    if raffle.status != 'ended':
        messages.warning(request, "The draw has not occurred yet.")
        return redirect('raffle:raffle_detail', custom_id=custom_id)
    
    winners = raffle.tickets.filter(is_winner=True)
    all_participants = raffle.tickets.filter(is_paid=True)
    
    return render(request, 'raffle/raffle_live_draw.html', {
        'raffle': raffle,
        'winners': winners,
        'all_participants': all_participants,
        'all_participants_names': [p.name for p in all_participants],
        'winners_data': [{'name': w.name, 'ticket': w.ticket_number} for w in winners]
    })

# --- Participation & Payment ---

@require_POST
@transaction.atomic
def join_raffle(request, custom_id):
    """Initiate entry into a raffle."""
    raffle = get_object_or_404(Raffle, custom_id=custom_id, status='active', is_approved=True, is_revoked=False)
    
    name = request.POST.get('name')
    email = request.POST.get('email')
    phone_number = request.POST.get('phone_number', '')
    payment_method = request.POST.get('payment_method', 'paystack')
    
    # Check if already joined
    if RaffleTicket.objects.filter(raffle=raffle, email=email, is_paid=True).exists():
        messages.error(request, 'You have already joined this raffle!')
        return redirect('raffle:raffle_detail', custom_id=custom_id)

    # Simplified Fee Logic (Matching bursapay)
    fixed_processing_fee = Decimal('100.00') if raffle.price >= 1000 else Decimal('50.00')
    commission_rate = Decimal('0.05')
    system_commission = raffle.price * commission_rate
    platform_fee_amount = system_commission + fixed_processing_fee
    total_price = raffle.price + fixed_processing_fee

    ticket = RaffleTicket.objects.create(
        raffle=raffle,
        user=request.user if request.user.is_authenticated else None,
        name=name,
        email=email,
        phone_number=phone_number,
        is_paid=(raffle.price == 0),
        amount_paid=total_price if raffle.price > 0 else 0,
        platform_fee=platform_fee_amount if raffle.price > 0 else 0
    )

    if raffle.price == 0:
        transaction.on_commit(lambda: send_raffle_entry_email.delay(ticket.id))
        check_auto_lock(raffle)
        messages.success(request, 'Successfully joined the raffle!')
        return redirect('raffle:raffle_detail', custom_id=custom_id)

    # Referral Linking
    ref_code = request.session.get(f'raffle_ref_{raffle.id}')
    if ref_code:
        try:
            referrer = RaffleTicket.objects.get(ticket_number=ref_code, raffle=raffle)
            ticket.referred_by = referrer
        except RaffleTicket.DoesNotExist:
            pass

    reference = f"RAF-{ticket.id}-{uuid.uuid4().hex[:8]}"
    ticket.payment_reference = reference
    ticket.save()

    # Payment Gateway Integration
    if payment_method == 'paystack':
        return initiate_paystack(request, ticket, email, total_price, reference)
    elif payment_method == 'flutterwave':
        return initiate_flutterwave(request, ticket, email, name, total_price, reference)

    return redirect('raffle:raffle_detail', custom_id=custom_id)

def initiate_paystack(request, ticket, email, amount, reference):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    callback_url = request.build_absolute_uri(reverse('raffle:verify_paystack'))
    data = {
        "email": email,
        "amount": int(amount * 100),
        "reference": reference,
        "callback_url": callback_url
    }
    try:
        response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers, timeout=10)
        if response.ok:
            return redirect(response.json()['data']['authorization_url'])
    except Exception as e:
        logger.error(f"Paystack Init Error: {e}")
    messages.error(request, "Payment initialization failed.")
    return redirect('raffle:raffle_detail', custom_id=ticket.raffle.custom_id)

def initiate_flutterwave(request, ticket, email, name, amount, reference):
    headers = {
        "Authorization": f"Bearer {settings.FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    callback_url = os.getenv('FLW_REDIRECT_URL') or request.build_absolute_uri(reverse('raffle:verify_flutterwave'))
    data = {
        "tx_ref": reference,
        "amount": float(amount),
        "currency": "NGN",
        "redirect_url": callback_url,
        "customer": {"email": email, "name": name},
        "customizations": {"title": "Raffle System", "description": f"Entry for {ticket.raffle.title}"}
    }
    try:
        response = requests.post("https://api.flutterwave.com/v3/payments", json=data, headers=headers, timeout=10)
        if response.ok:
            return redirect(response.json()['data']['link'])
    except Exception as e:
        logger.error(f"Flutterwave Init Error: {e}")
    messages.error(request, "Payment initialization failed.")
    return redirect('raffle:raffle_detail', custom_id=ticket.raffle.custom_id)

def verify_paystack(request):
    reference = request.GET.get('reference')
    if not reference: return redirect('raffle:raffle_list')
    
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    try:
        response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers, timeout=10)
        data = response.json()
        if response.ok and data.get('data', {}).get('status') == 'success':
            return finalize_success_payment(request, reference)
    except Exception as e:
        logger.error(f"Paystack Verify Error: {e}")
    messages.error(request, "Verification failed.")
    return redirect('home')

def verify_flutterwave(request):
    tx_ref = request.GET.get('tx_ref')
    status = request.GET.get('status')
    if status == 'cancelled': return redirect('raffle:raffle_list')
    
    # Verification logic normally goes here, calling FLW API
    return finalize_success_payment(request, tx_ref)

@transaction.atomic
def finalize_success_payment(request, reference):
    ticket = get_object_or_404(RaffleTicket, payment_reference=reference)
    if not ticket.is_paid:
        ticket.is_paid = True
        ticket.save()
        
        # Credit Wallet -> REMOVED: Balance is only credited after the draw (60% of loss)

        # Referral Bonus
        if ticket.referred_by and ticket.raffle.is_referral_enabled:
            handle_referral(ticket)

        transaction.on_commit(lambda: send_raffle_entry_email.delay(ticket.id))
        check_auto_lock(ticket.raffle)

    messages.success(request, f"Joined {ticket.raffle.title} successfully!")
    return redirect('raffle:raffle_payment_success', ticket_id=ticket.id)

def handle_referral(ticket):
    referrer = ticket.referred_by.user
    if referrer and not RaffleTicket.objects.filter(raffle=ticket.raffle, user=referrer, is_bonus=True).exists():
        RaffleTicket.objects.create(
            raffle=ticket.raffle,
            user=referrer,
            name=ticket.referred_by.name,
            email=ticket.referred_by.email,
            is_paid=True,
            is_bonus=True
        )

def check_auto_lock(raffle):
    paid_count = raffle.tickets.filter(is_paid=True).count()
    if paid_count >= raffle.target_participants and raffle.status == 'active':
        raffle.status = 'locked'
        raffle.locked_at = timezone.now()
        
        # Simple participant hash
        p_ids = sorted([str(t.id) for t in raffle.tickets.filter(is_paid=True)])
        raffle.participants_hash = hashlib.sha256(",".join(p_ids).encode()).hexdigest()
        raffle.save()
        
        if not raffle.notification_sent:
            transaction.on_commit(lambda: send_raffle_readiness_notification.delay(raffle.id, "Goal reached"))
            raffle.notification_sent = True
            raffle.save()

def raffle_payment_success(request, ticket_id):
    ticket = get_object_or_404(RaffleTicket, id=ticket_id)
    return render(request, 'raffle/raffle_success.html', {'ticket': ticket})

# --- Organizer Dashboard ---

@login_required
def registrar_raffle_dashboard(request):
    if request.user.role != 'organizer':
        if request.user.role == 'admin':
            return redirect('accounts:admin_dashboard')
        return redirect('home')

    if request.method == 'POST':
        form = RaffleForm(request.POST, request.FILES)
        if form.is_valid():
            raffle = form.save(commit=False)
            raffle.organizer = request.user
            
            # Resolve Partner Referral
            ref_code = form.cleaned_data.get('partner_referral_code')
            if ref_code:
                from accounts.models import RaffleOrganizerProfile
                partner_profile = RaffleOrganizerProfile.objects.filter(referral_code=ref_code).first()
                if partner_profile:
                    raffle.referred_by = partner_profile
            
            raffle.save()
            transaction.on_commit(lambda: send_raffle_creation_notification_email.delay(raffle.id))
            messages.success(request, f"Raffle '{raffle.title}' created!")
            return redirect('raffle:registrar_raffle_dashboard')
    else:
        form = RaffleForm()

    raffles = Raffle.objects.filter(organizer=request.user).order_by('-created_at')
    wallet, _ = RaffleWallet.objects.get_or_create(user=request.user)
    withdrawals = RaffleWithdrawalRequest.objects.filter(user=request.user).order_by('-requested_at')
    
    # Sales Data for Chart (Last 7 Days)
    from django.db.models import Count, Sum
    from datetime import timedelta
    seven_days_ago = timezone.now().date() - timedelta(days=6)
    
    sales_data = (
        RaffleTicket.objects.filter(
            raffle__organizer=request.user,
            is_paid=True,
            purchased_at__date__gte=seven_days_ago
        )
        .values('purchased_at__date')
        .annotate(total_sales=Count('id'), total_revenue=Sum('amount_paid'))
        .order_by('purchased_at__date')
    )
    
    chart_data = {
        'labels': [(seven_days_ago + timedelta(days=i)).strftime('%d %b') for i in range(7)],
        'values': [0] * 7
    }
    
    date_map = {item['purchased_at__date'].strftime('%d %b'): item['total_sales'] for item in sales_data}
    chart_data['values'] = [date_map.get(label, 0) for label in chart_data['labels']]

    initial_data = {}
    if request.user.bank_name:
        initial_data = {
            'bank_name': request.user.bank_name,
            'account_number': request.user.account_number,
            'account_name': request.user.account_name,
        }

    return render(request, 'raffle/organizer_dashboard.html', {
        'raffle_form': form,
        'raffles': raffles,
        'wallet': wallet,
        'withdrawals': withdrawals[:5],
        'withdrawal_form': RaffleWithdrawalForm(initial=initial_data),
        'chart_data': chart_data,
        'organizer_profile': getattr(request.user, 'organizer_profile', None)
    })

@login_required
def raffle_analytics_api(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id, organizer=request.user)
    analytics = getattr(raffle, 'analytics', None)
    
    if not analytics:
        return JsonResponse({'error': 'No analytics recorded for this campaign yet.'}, status=404)
        
    return JsonResponse({
        'total_revenue': float(analytics.total_revenue),
        'payout_pool': float(analytics.payout_pool),
        'total_loss': float(analytics.total_loss),
        'host_share': float(analytics.host_share),
        'system_share': float(analytics.system_share),
        'partner_share': float(analytics.partner_share),
        'is_referred': raffle.referred_by is not None,
        'partner_name': raffle.referred_by.user.get_full_name() if raffle.referred_by else ""
    })

@login_required
def participant_dashboard(request):
    """Dashboard for raffle participants."""
    if request.user.role == 'organizer':
        return redirect('raffle:registrar_raffle_dashboard')
    elif request.user.role == 'admin':
        return redirect('accounts:admin_dashboard')

    # Fail-safe sync winnings
    sync_user_winnings(request.user)

    # Get all tickets for this user that are paid
    tickets = RaffleTicket.objects.filter(user=request.user, is_paid=True).select_related('raffle').order_by('-purchased_at')
    
    # Wallet and Withdrawals
    wallet, _ = RaffleWallet.objects.get_or_create(user=request.user)
    withdrawals = RaffleWithdrawalRequest.objects.filter(user=request.user).order_by('-requested_at')

    # Group tickets by raffle state
    active_tickets = tickets.filter(raffle__status__in=['active', 'locked'])
    ended_tickets = tickets.filter(raffle__status='ended')
    
    # Stats
    total_spent = sum(t.amount_paid for t in tickets)
    total_won = sum(t.amount_won for t in tickets)
    won_tickets_count = tickets.filter(is_winner=True).count()

    # Participant Dashboard context
    initial_data = {}
    if request.user.bank_name:
        initial_data = {
            'bank_name': request.user.bank_name,
            'account_number': request.user.account_number,
            'account_name': request.user.account_name,
        }

    return render(request, 'raffle/participant_dashboard.html', {
        'active_tickets': active_tickets,
        'ended_tickets': ended_tickets,
        'total_spent': total_spent,
        'total_won': total_won,
        'won_tickets_count': won_tickets_count,
        'wallet': wallet,
        'withdrawals': withdrawals[:5],
        'withdrawal_form': RaffleWithdrawalForm(initial=initial_data)
    })

@login_required
def partner_referral_dashboard(request):
    if request.user.role != 'organizer':
        return redirect('home')
        
    profile = getattr(request.user, 'organizer_profile', None)
    if not profile:
        return redirect('raffle:registrar_raffle_dashboard')
        
    referred_raffles = Raffle.objects.filter(referred_by=profile).select_related('organizer').order_by('-created_at')
    
    # Calculate total referral earnings from analytics
    from django.db.models import Sum
    total_earned = RaffleAnalytics.objects.filter(raffle__referred_by=profile).aggregate(Sum('partner_share'))['partner_share__sum'] or 0
    
    return render(request, 'raffle/partner_referral_dashboard.html', {
        'referred_raffles': referred_raffles,
        'total_earned': total_earned,
        'profile': profile
    })

@login_required
@require_POST
def request_raffle_withdrawal(request):
    # Enforce "one withdrawal at a time"
    if RaffleWithdrawalRequest.objects.filter(user=request.user, status='pending').exists():
        messages.error(request, "You already have a pending withdrawal request. Please wait for it to be processed.")
        if request.user.role == 'organizer':
            return redirect('raffle:registrar_raffle_dashboard')
        return redirect('raffle:participant_dashboard')

    form = RaffleWithdrawalForm(request.POST)
    if form.is_valid():
        amt = form.cleaned_data['amount']
        if amt < 5000:
            messages.error(request, "Minimum withdrawal amount is ₦5,000.")
            if request.user.role == 'organizer':
                return redirect('raffle:registrar_raffle_dashboard')
            return redirect('raffle:participant_dashboard')

        with transaction.atomic():
            # select_for_update() locks the wallet row to prevent race conditions
            wallet = RaffleWallet.objects.select_for_update().get(user=request.user)
            
            if amt <= wallet.balance:
                # Debit wallet immediately
                wallet.balance -= amt
                wallet.save()
                
                withdrawal = form.save(commit=False)
                withdrawal.user = request.user
                withdrawal.save()
                
                # Automatically save bank details for future use
                if request.user.bank_name != withdrawal.bank_name or \
                   request.user.account_number != withdrawal.account_number or \
                   request.user.account_name != withdrawal.account_name:
                    request.user.bank_name = withdrawal.bank_name
                    request.user.account_number = withdrawal.account_number
                    request.user.account_name = withdrawal.account_name
                    request.user.save(update_fields=['bank_name', 'account_number', 'account_name'])
                
                # Record transaction
                processing_fee = Decimal('100.00')
                payable_amt = amt - processing_fee
                
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=amt,
                    transaction_type='debit',
                    description=f"Withdrawal request for ₦{amt:,.2f} (Net: ₦{payable_amt:,.2f}, Fee: ₦{processing_fee}) at {withdrawal.bank_name}"
                )

                
                transaction.on_commit(lambda: send_raffle_withdrawal_notification_email.delay(withdrawal.id))
                messages.success(request, "Withdrawal request submitted. Funds have been deducted and are pending approval.")
            else:
                messages.error(request, "Insufficient balance for this withdrawal.")
    else:
        messages.error(request, "Invalid form data.")
    
    if request.user.role == 'organizer':
        return redirect('raffle:registrar_raffle_dashboard')
    return redirect('raffle:participant_dashboard')

@login_required
@require_POST
def lock_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id, organizer=request.user, status='active')
    check_auto_lock(raffle) # Re-use auto-lock logic to manually lock
    raffle.status = 'locked'
    raffle.save()
    return JsonResponse({'status': 'success', 'message': 'Raffle locked!'})

@login_required
@require_POST
def generate_raffle_winners(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id, organizer=request.user, status='locked')
    seed = request.POST.get('external_seed')
    if not seed: return JsonResponse({'error': 'Seed required'}, status=400)

    raffle.external_seed = seed
    participants = list(raffle.tickets.filter(is_paid=True, is_winner=False))
    if not participants: return JsonResponse({'error': 'No entries'}, status=400)

    winners_to_pick = min(raffle.num_winners, len(participants))
    rng = random.Random(f"{raffle.participants_hash}:{seed}")
    selected = rng.sample(participants, winners_to_pick)

    # Calculate Revenue Splits
    total_paid_tickets = raffle.tickets.filter(is_paid=True)
    total_revenue = total_paid_tickets.count() * raffle.price
    payout_pool = (total_revenue * raffle.payout_percentage) / 100
    individual_prize = payout_pool / winners_to_pick if winners_to_pick > 0 else 0
    
    total_loss = total_revenue - payout_pool
    
    # 60% Host, 40% System
    host_share = total_loss * Decimal('0.60')
    system_initial_share = total_loss * Decimal('0.40')
    
    partner_share = Decimal('0.00')
    system_final_share = system_initial_share
    
    if raffle.referred_by:
        # Referral reward is 10% of the System's share (which is 4% of total loss)
        partner_share = system_initial_share * Decimal('0.10')
        system_final_share = system_initial_share - partner_share

    with transaction.atomic():
        # Get or create wallets
        host_wallet, _ = RaffleWallet.objects.get_or_create(user=raffle.organizer)
        
        # Credit Host's withdrawable share (60% of the loss)
        host_wallet.balance += host_share
        WalletTransaction.objects.create(
            wallet=host_wallet,
            amount=host_share,
            transaction_type='credit',
            description=f"Host share (60% of loss) from Raffle: {raffle.title}"
        )
        
        # Credit Host's payout pool (Reserved for winners)
        host_wallet.payout_pool_balance += payout_pool
        # (Payout pool is not a 'withdrawable' transaction yet, so we don't log it as a standard credit/debit until distributed)
        host_wallet.save()
        
        if raffle.referred_by:
            partner_wallet, _ = RaffleWallet.objects.get_or_create(user=raffle.referred_by.user)
            partner_wallet.balance += partner_share
            partner_wallet.save()
            WalletTransaction.objects.create(
                wallet=partner_wallet,
                amount=partner_share,
                transaction_type='credit',
                description=f"Referral commission (4% of loss) from Raffle: {raffle.title}"
            )

        for t in selected:
            t.is_winner = True
            t.amount_won = individual_prize
            t.save()
            
            # If winner is already a registered user, transfer from Payout Pool to their Balance immediately
            if t.user:
                winner_wallet, _ = RaffleWallet.objects.get_or_create(user=t.user)
                
                # Check if Host has enough in payout pool (sanity check)
                if host_wallet.payout_pool_balance >= individual_prize:
                    host_wallet.payout_pool_balance -= individual_prize
                    host_wallet.save()
                    winner_wallet.balance += individual_prize
                    winner_wallet.save()
                    
                    WalletTransaction.objects.create(
                        wallet=winner_wallet,
                        amount=individual_prize,
                        transaction_type='credit',
                        description=f"Winning payout from Raffle: {raffle.title}"
                    )
            
            transaction.on_commit(lambda ticket_id=t.id: send_raffle_winner_email.delay(ticket_id))
            
        # Record Analytics
        RaffleAnalytics.objects.create(
            raffle=raffle,
            total_revenue=total_revenue,
            payout_pool=payout_pool,
            total_loss=total_loss,
            host_share=host_share,
            system_share=system_final_share,
            partner_share=partner_share
        )
        
        raffle.status = 'ended'
        raffle.save()
        
        # Schedule automatic settlement of unclaimed money in 30 minutes
        transaction.on_commit(lambda: settle_unclaimed_winnings.apply_async(args=[raffle.id], countdown=1800))

    return JsonResponse({'status': 'success', 'message': 'Winners generated and revenue calculated!'})
@login_required
def wallet_history(request):
    wallet, _ = RaffleWallet.objects.get_or_create(user=request.user)
    transactions = wallet.transactions.all().order_by('-created_at')
    
    data = []
    for tx in transactions:
        data.append({
            'amount': float(tx.amount),
            'type': tx.transaction_type,
            'description': tx.description,
            'date': tx.created_at.strftime("%b %d, %H:%M"),
        })
    
    return JsonResponse({'status': 'success', 'transactions': data})

@login_required
@require_POST
def delete_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id, organizer=request.user)
    
    # Check deletion rules
    if raffle.status == 'active' and raffle.paid_count > 0:
        messages.error(request, "Cannot delete a raffle that has active participants.")
        return redirect('raffle:registrar_raffle_dashboard')

    if raffle.status == 'ended' and not raffle.is_settled:
        # If ending/settling manually, trigger settlement now before deletion
        from .tasks import settle_unclaimed_winnings
        settle_unclaimed_winnings(raffle.id)

    raffle.delete()
    messages.success(request, f"Raffle '{raffle.title}' deleted successfully.")
    return redirect('raffle:registrar_raffle_dashboard')

@login_required
def edit_raffle(request, custom_id):
    raffle = get_object_or_404(Raffle, custom_id=custom_id, organizer=request.user)
    
    if raffle.paid_count > 0:
        messages.error(request, "Cannot edit a raffle that already has ticket sales.")
        return redirect('raffle:registrar_raffle_dashboard')

    if request.method == 'POST':
        form = RaffleForm(request.POST, request.FILES, instance=raffle)
        if form.is_valid():
            form.save()
            messages.success(request, f"Raffle '{raffle.title}' updated successfully!")
            return redirect('raffle:registrar_raffle_dashboard')
    else:
        form = RaffleForm(instance=raffle)
    
    return render(request, 'raffle/edit_raffle.html', {
        'form': form,
        'raffle': raffle
    })
