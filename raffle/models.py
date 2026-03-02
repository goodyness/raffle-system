from django.db import models
from decimal import Decimal
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from core.supabase_storage import SupabaseStorage
import random
import string

class RaffleCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=50, default='💎', help_text="Emoji or icon class")
    
    class Meta:
        verbose_name_plural = "Raffle Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.icon} {self.name}"

class Raffle(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('locked', 'Locked'),
        ('ended', 'Ended'),
        ('rejected', 'Rejected'),
    ]

    custom_id = models.CharField(max_length=50, unique=True, blank=False, null=False, editable=False)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_raffles'
    )
    title = models.CharField(max_length=200)
    category = models.ForeignKey(RaffleCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='raffles')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    num_winners = models.PositiveIntegerField(default=1)
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    image = models.ImageField(upload_to='raffle_images/', storage=SupabaseStorage(), null=True, blank=True)
    target_participants = models.PositiveIntegerField(default=2000)
    payout_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'))
    is_approved = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)

    participants_hash = models.CharField(max_length=64, null=True, blank=True)
    external_seed = models.CharField(max_length=255, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_referral_enabled = models.BooleanField(default=False)
    is_settled = models.BooleanField(default=False)
    
    partner_referral_code = models.CharField(max_length=20, blank=True, null=True)
    referred_by = models.ForeignKey(
        'accounts.RaffleOrganizerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_raffles'
    )

    def generate_custom_id(self):
        title_part = slugify(self.title).replace('-', '')[:6].upper()
        rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"RAF-{title_part}-{rand_part}"

    def save(self, *args, **kwargs):
        if not self.custom_id:
            while True:
                new_id = self.generate_custom_id()
                if not Raffle.objects.filter(custom_id=new_id).exists():
                    self.custom_id = new_id
                    break
        super().save(*args, **kwargs)

    @property
    def paid_count(self):
        return self.tickets.filter(is_paid=True).count()

    @property
    def is_editable_or_deletable(self):
        if self.paid_count == 0:
            return True
        return self.status == 'ended'

    @property
    def participation_percentage(self):
        if not self.target_participants:
            return 0
        percentage = (self.paid_count / self.target_participants) * 100
        return min(percentage, 100)

    def __str__(self):
        return f"Raffle: {self.title} (Winners: {self.num_winners})"

class RaffleTicket(models.Model):
    raffle = models.ForeignKey(Raffle, on_delete=models.CASCADE, related_name='tickets')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    ticket_number = models.CharField(max_length=10, unique=True, editable=False)
    is_winner = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount_won = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))
    
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    is_bonus = models.BooleanField(default=False)
    
    purchased_at = models.DateTimeField(auto_now_add=True)

    def generate_ticket_number(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            while True:
                new_ticket = self.generate_ticket_number()
                if not RaffleTicket.objects.filter(ticket_number=new_ticket).exists():
                    self.ticket_number = new_ticket
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Raffle Ticket {self.ticket_number} - {self.name} for {self.raffle.title}"

class RaffleWallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='raffle_wallet'
    )
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    payout_pool_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Raffle Balance: ₦{self.balance}"

class RaffleWithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    declined_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - ₦{self.amount} ({self.status})"

class RaffleAnalytics(models.Model):
    raffle = models.OneToOneField(Raffle, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics')
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payout_pool = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_loss = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    host_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    system_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    partner_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00')) # 10% of system share
    unclaimed_prizes = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analytics for {self.raffle.title}"

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    wallet = models.ForeignKey(RaffleWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} of ₦{self.amount} - {self.description}"

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at} - {self.action} by {self.user}"
