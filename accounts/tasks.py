from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import CustomUser
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_email_task(self, user_id, otp_code):
    try:
        user = CustomUser.objects.get(id=user_id)
        
        subject = "Verify Your Account - Raffle System"
        context = {
            'user': user,
            'otp_code': otp_code
        }
        
        html_message = render_to_string('emails/otp_verification.html', context)
        plain_message = strip_tags(html_message)
        
        email = EmailMultiAlternatives(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        
        logger.info(f"OTP email sent successfully to {user.email}")
        
    except CustomUser.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist for OTP email.")
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        self.retry(exc=e)
