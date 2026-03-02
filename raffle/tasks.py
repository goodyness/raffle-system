from celery import shared_task
from decimal import Decimal
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_entry_email(self, ticket_id):
    from raffle.models import RaffleTicket
    try:
        # Debugging: log the ID being searched
        logger.info(f"Attempting to send email for Ticket ID: {ticket_id}")
        
        ticket = RaffleTicket.objects.select_related('raffle').get(id=ticket_id)
        
        context = {
            'ticket': ticket,
            'raffle': ticket.raffle,
            'year': now().year,
        }

        subject = f"Raffle Entry Confirmation: {ticket.raffle.title}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [ticket.email]

        html_content = render_to_string('emails/raffle_entry_confirmation.html', context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Raffle entry email sent successfully to: {ticket.email}")

    except RaffleTicket.DoesNotExist as e:
        logger.error(f"RaffleTicket {ticket_id} not found. This might be a race condition. Retrying...")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Failed to send raffle entry email for ID {ticket_id}: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_withdrawal_notification_email(self, withdrawal_id):
    from raffle.models import RaffleWithdrawalRequest
    try:
        withdrawal = RaffleWithdrawalRequest.objects.select_related('user').get(id=withdrawal_id)
        user = withdrawal.user
        
        context = {
            'withdrawal': withdrawal,
            'year': now().year,
            'BASE_URL': settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000',
        }

        subject = "New Raffle Withdrawal Request"
        from_email = settings.DEFAULT_FROM_EMAIL

        # Email for Admin
        admin_html = render_to_string('emails/raffle_withdrawal_request_notification_admin.html', context)
        admin_text = f"Admin, a new withdrawal request of ₦{withdrawal.amount} has been submitted by {user.full_name}."
        admin_email = EmailMultiAlternatives(subject, admin_text, from_email, [settings.ADMIN_EMAIL])
        admin_email.attach_alternative(admin_html, "text/html")
        admin_email.send()

        # Email for User (Organizer)
        user_html = render_to_string('emails/raffle_withdrawal_request_notification_user.html', context)
        user_text = f"Hello {user.full_name}, your withdrawal request of ₦{withdrawal.amount} has been received."
        user_email = EmailMultiAlternatives(subject, user_text, from_email, [user.email])
        user_email.attach_alternative(user_html, "text/html")
        user_email.send()

        logger.info(f"Raffle withdrawal emails sent to admin and user: {user.email}")

    except Exception as e:
        logger.error(f"Failed to send raffle withdrawal notifications: {e}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_winner_email(self, ticket_id):
    from raffle.models import RaffleTicket
    try:
        ticket = RaffleTicket.objects.select_related('raffle').get(id=ticket_id)
        
        context = {
            'ticket': ticket,
            'raffle': ticket.raffle,
            'organizer': ticket.raffle.organizer,
            'admin_email': settings.ADMIN_EMAIL,
            'amount_won': ticket.amount_won,
            'year': now().year,
            'BASE_URL': settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000',
            'has_account': ticket.user is not None,
        }

        subject = f"CONGRATULATIONS! You won in the {ticket.raffle.title} Raffle!"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [ticket.email]

        html_content = render_to_string('emails/raffle_winner_notification.html', context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Raffle winner email sent to: {ticket.email} for ₦{ticket.amount_won}")

    except Exception as e:
        logger.error(f"Failed to send raffle winner email: {e}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_creation_notification_email(self, raffle_id):
    from raffle.models import Raffle
    try:
        raffle = Raffle.objects.select_related('organizer').get(id=raffle_id)
        
        context = {
            'raffle': raffle,
            'organizer': raffle.organizer,
            'year': now().year,
            'BASE_URL': settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000',
        }

        # 1. Email to Organizer
        subject_org = f"Raffle Created: {raffle.title} (Awaiting Approval)"
        html_org = render_to_string('emails/raffle_created_organizer.html', context)
        text_org = strip_tags(html_org)
        
        email_org = EmailMultiAlternatives(subject_org, text_org, settings.DEFAULT_FROM_EMAIL, [raffle.organizer.email])
        email_org.attach_alternative(html_org, "text/html")
        email_org.send()

        # 2. Email to Admin
        subject_admin = f"NEW Raffle AWAITING APPROVAL: {raffle.title}"
        html_admin = render_to_string('emails/raffle_created_admin_notification.html', context)
        text_admin = strip_tags(html_admin)
        
        email_admin = EmailMultiAlternatives(subject_admin, text_admin, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL])
        email_admin.attach_alternative(html_admin, "text/html")
        email_admin.send()

        logger.info(f"Raffle creation notifications sent for raffle ID: {raffle_id}")

    except Exception as e:
        logger.error(f"Failed to send raffle creation notifications: {e}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_status_notification_email(self, raffle_id, status):
    from raffle.models import Raffle
    try:
        raffle = Raffle.objects.select_related('organizer').get(id=raffle_id)
        
        context = {
            'raffle': raffle,
            'organizer': raffle.organizer,
            'year': now().year,
            'BASE_URL': settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000',
        }

        if status == 'approved':
            subject = f"Raffle APPROVED: {raffle.title}! 🚀"
            template = 'emails/raffle_approved.html'
        else:
            subject = f"Raffle Update: {raffle.title}"
            template = 'emails/raffle_declined.html'

        html_content = render_to_string(template, context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [raffle.organizer.email])
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Raffle status notification ({status}) sent for raffle ID: {raffle_id}")

    except Exception as e:
        logger.error(f"Failed to send raffle status notification: {e}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_readiness_notification(self, raffle_id, reason):
    from raffle.models import Raffle
    try:
        raffle = Raffle.objects.select_related('organizer').get(id=raffle_id)
        
        context = {
            'raffle_title': raffle.title,
            'organizer_name': raffle.organizer.full_name,
            'reason': reason,
            'entries_count': raffle.tickets.filter(is_paid=True).count(),
            'year': now().year,
        }

        subject = f"ACTION REQUIRED: Raffle '{raffle.title}' is Ready to Complete! 🏁"
        html_content = render_to_string('emails/raffle_readiness_notification.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [raffle.organizer.email])
        email.attach_alternative(html_content, "text/html")
        email.send()

        raffle.notification_sent = True
        raffle.save()

        logger.info(f"Readiness notification sent for raffle: {raffle.title}")

    except Exception as e:
        logger.error(f"Failed to send raffle readiness notification: {e}")
        self.retry(exc=e)

@shared_task
def check_expired_raffles():
    from raffle.models import Raffle
    expired_raffles = Raffle.objects.filter(
        status='active',
        is_approved=True,
        end_datetime__lte=now(),
        notification_sent=False
    )
    
    for raffle in expired_raffles:
        send_raffle_readiness_notification.delay(raffle.id, "Temporal expiry (end date reached)")

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_end_stats_email(self, raffle_id):
    from django.db.models import Sum
    from raffle.models import Raffle
    from accounts.models import CustomUser
    try:
        raffle = Raffle.objects.select_related('organizer').get(id=raffle_id)
        
        paid_count = raffle.tickets.filter(is_paid=True).count()
        total_revenue = paid_count * raffle.price
        total_prize_pool = (total_revenue * raffle.payout_percentage) / 100
        total_profit = raffle.tickets.filter(is_paid=True).aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0
        winners_count = raffle.tickets.filter(is_winner=True).count()

        context = {
            'raffle': raffle,
            'total_revenue': total_revenue,
            'total_profit': total_profit,
            'total_prize_pool': total_prize_pool,
            'winners_count': winners_count,
            'year': now().year,
        }

        subject = f"Raffle Finalized: {raffle.title} - System Profit Report"
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Recipient: All Admins
        recipients = list(CustomUser.objects.filter(role='admin').values_list('email', flat=True))
        if settings.ADMIN_EMAIL not in recipients:
            recipients.append(settings.ADMIN_EMAIL)

        html_content = render_to_string('emails/raffle_summary_admin.html', context)
        text_content = f"The Raffle '{raffle.title}' has ended. Total Revenue: ₦{total_revenue}, System Profit: ₦{total_profit}."
        
        email = EmailMultiAlternatives(subject, text_content, from_email, recipients)
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Raffle end stats email sent to {len(recipients)} recipients for raffle ID: {raffle_id}")

    except Exception as e:
        logger.error(f"Failed to send raffle end stats email: {e}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_raffle_revocation_status_email(self, raffle_id, status, reason=''):
    from raffle.models import Raffle
    try:
        raffle = Raffle.objects.select_related('organizer').get(id=raffle_id)
        
        context = {
            'raffle': raffle,
            'organizer': raffle.organizer,
            'status': status,
            'reason': reason,
            'year': now().year,
            'BASE_URL': settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000',
        }

        subject = f"Raffle Campaign Update: {raffle.title} is now {status.upper()}"
        html_content = render_to_string('emails/raffle_revocation_status.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [raffle.organizer.email])
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Revocation status ({status}) email sent for raffle: {raffle.title}")

    except Exception as e:
        logger.error(f"Failed to send raffle revocation status email: {e}")
        self.retry(exc=e)
        
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def settle_unclaimed_winnings(self, raffle_id):
    from django.db import transaction
    from django.db.models import Sum
    from raffle.models import Raffle, RaffleWallet, WalletTransaction
    
    try:
        with transaction.atomic():
            raffle = Raffle.objects.select_related('organizer').get(id=raffle_id, status='ended', is_settled=False)
            
            # Find tickets with no assigned user (unclaimed)
            unclaimed_tickets = raffle.tickets.filter(is_winner=True, user=None)
            unclaimed_total = unclaimed_tickets.aggregate(Sum('amount_won'))['amount_won__sum'] or Decimal('0.00')
            
            if unclaimed_total > 0:
                host_wallet = RaffleWallet.objects.get(user=raffle.organizer)
                
                # Verify pool has enough (it should)
                if host_wallet.payout_pool_balance >= unclaimed_total:
                    # Deduct from host's payout pool (reserved money)
                    host_wallet.payout_pool_balance -= unclaimed_total
                    host_wallet.save()
                    
                    # Credit System Analytics instead of organizer balance
                    analytics, _ = RaffleAnalytics.objects.get_or_create(raffle=raffle)
                    analytics.unclaimed_prizes = Decimal(str(analytics.unclaimed_prizes)) + unclaimed_total
                    analytics.save()
                    
                    # Log the transaction as a system gain
                    # We can still log it in the organizer's wallet history but as a "Platform Retrieval" 
                    # OR we just log it as a descriptive entry so they know where it went.
                    WalletTransaction.objects.create(
                        wallet=host_wallet,
                        amount=unclaimed_total,
                        transaction_type='debit',
                        description=f"Platform Retrieval: Unclaimed prizes from Raffle: {raffle.title} (System Revenue)"
                    )
                    
                    logger.info(f"Settled ₦{unclaimed_total} unclaimed winnings for Raffle {raffle_id} to System Revenue.")
            
            raffle.is_settled = True
            raffle.save()
            
    except Raffle.DoesNotExist:
        logger.warning(f"Raffle {raffle_id} already settled or does not exist for settlement.")
    except Exception as e:
        logger.error(f"Error settling raffle {raffle_id}: {e}")
        raise self.retry(exc=e)

@shared_task
def send_withdrawal_approved_email(withdrawal_id):
    """Notify user of approved withdrawal with a styled email."""
    from .models import RaffleWithdrawalRequest
    from decimal import Decimal
    try:
        withdrawal = RaffleWithdrawalRequest.objects.select_related('user').get(id=withdrawal_id)
        user = withdrawal.user
        
        # Calculate net payable for the template
        withdrawal.net_payable = withdrawal.amount - Decimal('100.00')

        subject = f"Withdrawal Approved: ₦{withdrawal.net_payable:,.2f}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        html_content = render_to_string('emails/withdrawal_approved.html', {
            'user': user,
            'withdrawal': withdrawal,
            'base_url': settings.BASE_URL
        })
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    except RaffleWithdrawalRequest.DoesNotExist:
        logger.error(f"Withdrawal {withdrawal_id} not found for email notification.")
    except Exception as e:
        logger.error(f"Error sending withdrawal approval email: {e}")
