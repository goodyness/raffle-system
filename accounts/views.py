import random
import string
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import CustomUser, OTP, RaffleOrganizerProfile
from .forms import OrganizerRegistrationForm, ParticipantRegistrationForm
from .tasks import send_otp_email_task
from django.db import transaction

# Local mailer replaced by background task in .tasks

def sync_user_winnings(user):
    """
    Look for any unassigned winning tickets that match the user's email 
    and credit their wallet.
    """
    from raffle.models import RaffleTicket, RaffleWallet, WalletTransaction
    from decimal import Decimal
    
    winning_tickets = RaffleTicket.objects.filter(email=user.email, is_winner=True, user__isnull=True)
    if not winning_tickets.exists():
        return
        
    with transaction.atomic():
        user_wallet, _ = RaffleWallet.objects.get_or_create(user=user)
        # Ensure Decimal
        user_wallet.balance = Decimal(str(user_wallet.balance))
        
        for ticket in winning_tickets:
            ticket.user = user
            ticket.save()
            
            # Transfer from Host's Payout Pool (or Balance if settled) to Winner's Balance
            host_wallet, _ = RaffleWallet.objects.get_or_create(user=ticket.raffle.organizer)
            host_wallet.payout_pool_balance = Decimal(str(host_wallet.payout_pool_balance))
            host_wallet.balance = Decimal(str(host_wallet.balance))
            
            if host_wallet.payout_pool_balance >= ticket.amount_won:
                # Case 1: Still in Host's Payout Pool (unsettled)
                host_wallet.payout_pool_balance -= ticket.amount_won
                host_wallet.save()
            else:
                # Case 2: Settled. Deduct from System's Unclaimed Prizes instead of Host's balance
                from raffle.models import RaffleAnalytics
                analytics, _ = RaffleAnalytics.objects.get_or_create(raffle=ticket.raffle)
                analytics.unclaimed_prizes = Decimal(str(analytics.unclaimed_prizes)) - ticket.amount_won
                analytics.save()
                
                # We don't debit the host anymore because the platform already took the surplus
                # Just log for internal audit that the prize was fulfilled by platform
            
            user_wallet.balance += ticket.amount_won
            user_wallet.save()
            
            WalletTransaction.objects.create(
                wallet=user_wallet,
                amount=ticket.amount_won,
                transaction_type='credit',
                description=f"Winning payout sync from Raffle: {ticket.raffle.title}"
            )

def register_organizer(request):
    if request.method == 'POST':
        form = OrganizerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = 'organizer'
            user.save()
            
            RaffleOrganizerProfile.objects.create(user=user)
            
            # Generate OTP
            code = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(
                user=user,
                code=code,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            
            send_otp_email_task.delay(user.id, code)
            request.session['verification_email'] = user.email
            messages.success(request, "Registration successful. Please check your email for the verification code.")
            return redirect('accounts:verify_email')
    else:
        form = OrganizerRegistrationForm()
    return render(request, 'accounts/register_organizer.html', {'form': form})

def register_participant(request):
    if request.method == 'POST':
        form = ParticipantRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = 'participant'
            user.is_email_verified = False # Now requires verification
            user.save()
            
            # Retrospective Winning Credit
            sync_user_winnings(user)
            
            # Generate OTP
            code = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(
                user=user,
                code=code,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            
            send_otp_email_task.delay(user.id, code)
            request.session['verification_email'] = user.email
            messages.success(request, "Registration successful. Please check your email for the verification code.")
            return redirect('accounts:verify_email')
    else:
        form = ParticipantRegistrationForm()
    return render(request, 'accounts/register_participant.html', {'form': form})

def verify_email(request):
    email = request.session.get('verification_email')
    if not email:
        return redirect('accounts:login')
        
    if request.method == 'POST':
        code = request.POST.get('code')
        user = get_object_or_404(CustomUser, email=email)
        otp = OTP.objects.filter(user=user, is_used=False).last()
        
        if otp and otp.is_valid():
            if otp.attempts >= 5:
                messages.error(request, "Too many failed attempts. Please request a new code.")
                return render(request, 'accounts/verify_email.html', {'email': email})

            if otp.code == code:
                otp.is_used = True
                otp.save()
                user.is_email_verified = True
                user.save()
                
                # Sync any winnings that happened before verification
                sync_user_winnings(user)
                
                login(request, user)
                messages.success(request, "Email verified successfully. Welcome!")
                
                # Role-based redirection
                if user.role == 'organizer':
                    return redirect('raffle:registrar_raffle_dashboard')
                else:
                    return redirect('raffle:participant_dashboard')
            else:
                otp.attempts += 1
                otp.save()
                remaining = 5 - otp.attempts
                if remaining > 0:
                    messages.error(request, f"Invalid code. {remaining} attempts remaining.")
                else:
                    messages.error(request, "Too many failed attempts. This code is now blocked.")
        else:
            messages.error(request, "Invalid or expired verification code.")
            
    return render(request, 'accounts/verify_email.html', {'email': email})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if not user.is_email_verified and not user.is_superuser:
                    request.session['verification_email'] = user.email
                    messages.warning(request, "Please verify your email first.")
                    # Resend OTP if needed
                    otp = OTP.objects.filter(user=user, is_used=False).last()
                    if otp:
                        send_otp_email_task.delay(user.id, otp.code)
                    else:
                        # Generate new if none active
                        code = ''.join(random.choices(string.digits, k=6))
                        OTP.objects.create(user=user, code=code, expires_at=timezone.now() + timedelta(minutes=15))
                        send_otp_email_task.delay(user.id, code)
                    return redirect('accounts:verify_email')
                
                # Sync winnings on every login to ensure balance is up to date
                sync_user_winnings(user)
                
                login(request, user)
                messages.info(request, f"You are now logged in as {user.email}.")
                if user.role == 'admin':
                    return redirect('accounts:admin_dashboard')
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('home')

def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = CustomUser.objects.filter(email=email).first()
        if user:
            # Generate Reset OTP (reusing OTP model)
            code = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(
                user=user,
                code=code,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            # Reusing the OTP email task but with "Reset" context if possible, 
            # for now standard OTP task is fine as it just sends the code.
            send_otp_email_task.delay(user.id, code)
            request.session['reset_email'] = email
            messages.success(request, "Password reset code sent to your email.")
            return redirect('accounts:password_reset_verify')
        else:
            messages.error(request, "User with this email does not exist.")
    return render(request, 'accounts/password_reset_request.html')

def password_reset_verify(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('accounts:password_reset_request')
        
    if request.method == 'POST':
        code = request.POST.get('code')
        user = get_object_or_404(CustomUser, email=email)
        otp = OTP.objects.filter(user=user, is_used=False).last()
        
        if otp and otp.is_valid():
            if otp.attempts >= 5:
                messages.error(request, "Too many failed attempts. Please request a new reset code.")
                return render(request, 'accounts/password_reset_verify.html', {'email': email})

            if otp.code == code:
                otp.is_used = True
                otp.save()
                request.session['reset_verified'] = True
                return redirect('accounts:password_reset_confirm')
            else:
                otp.attempts += 1
                otp.save()
                remaining = 5 - otp.attempts
                if remaining > 0:
                    messages.error(request, f"Invalid code. {remaining} attempts remaining.")
                else:
                    messages.error(request, "Too many failed attempts. This code is now blocked.")
        else:
            messages.error(request, "Invalid or expired reset code.")
            
    return render(request, 'accounts/password_reset_verify.html', {'email': email})

def password_reset_confirm(request):
    email = request.session.get('reset_email')
    verified = request.session.get('reset_verified')
    
    if not email or not verified:
        return redirect('accounts:password_reset_request')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password == confirm_password:
            user = CustomUser.objects.get(email=email)
            user.set_password(password)
            user.save()
            
            # Clear session
            del request.session['reset_email']
            del request.session['reset_verified']
            
            messages.success(request, "Password reset successful. Please login with your new password.")
            return redirect('accounts:login')
        else:
            messages.error(request, "Passwords do not match.")
            
    return render(request, 'accounts/password_reset_confirm.html')

# import decorator
from django.contrib.auth.decorators import login_required

@login_required
def profile_settings(request):
    from .forms import ProfileUpdateForm
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            password_form = PasswordChangeForm(user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect('accounts:profile_settings')
                
        elif action == 'change_password':
            profile_form = ProfileUpdateForm(instance=user)
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, "Password changed successfully.")
                return redirect('accounts:profile_settings')
    else:
        profile_form = ProfileUpdateForm(instance=user)
        password_form = PasswordChangeForm(user)
        
    context = {
        'profile_form': profile_form,
        'password_form': password_form
    }
    return render(request, 'accounts/profile_settings.html', context)
