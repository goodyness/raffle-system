from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid
import random
import string

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('organizer', 'Raffle Organizer'),
        ('participant', 'Participant'),
    ]

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True, default='participant')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    
    # Saved Bank Details for Organizers
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True)
    
    # We can add more fields as needed later
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
            if not self.username or self.username != self.email:
                self.username = self.email
        super().save(*args, **kwargs)

class AdminProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='admin_profile')
    permissions_level = models.IntegerField(default=1) # Example field
    
    def __str__(self):
        return f"Admin: {self.user.full_name}"

class RaffleOrganizerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='organizer_profile')
    organization_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    partner_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    def __str__(self):
        return f"Organizer: {self.user.full_name} ({self.organization_name or 'Independent'})"

    def save(self, *args, **kwargs):
        if not self.partner_id:
            while True:
                pid = f"PART-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
                if not RaffleOrganizerProfile.objects.filter(partner_id=pid).exists():
                    self.partner_id = pid
                    break
        if not self.referral_code:
            while True:
                ref = f"REF-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
                if not RaffleOrganizerProfile.objects.filter(referral_code=ref).exists():
                    self.referral_code = ref
                    break
        super().save(*args, **kwargs)

class OTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

    def __str__(self):
        return f"OTP for {self.user.email}: {self.code}"
