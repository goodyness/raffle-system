from django import forms
from django.utils import timezone
from .models import Raffle, RaffleWithdrawalRequest

class RaffleForm(forms.ModelForm):
    class Meta:
        model = Raffle
        fields = [
            'title',
            'description',
            'price',
            'num_winners',
            'target_participants',
            'payout_percentage',
            'end_datetime',
            'image',
            'partner_referral_code',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': 'Campaign Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'rows': 3,
                'placeholder': 'Tell your participants what they can win...'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': '0.00'
            }),
            'num_winners': forms.NumberInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': '1'
            }),
            'target_participants': forms.NumberInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': '1000'
            }),
            'payout_percentage': forms.NumberInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': '80'
            }),
            'end_datetime': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'
            }),
            'partner_referral_code': forms.TextInput(attrs={
                'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium',
                'placeholder': 'REF-123456 (Optional)'
            }),
        }

    def clean_end_datetime(self):
        end = self.cleaned_data.get('end_datetime')
        if end:
            if timezone.is_naive(end):
                end = timezone.make_aware(end)
            if end <= timezone.now():
                raise forms.ValidationError("End time must be in the future.")
        return end

    def clean_payout_percentage(self):
        payout = self.cleaned_data.get('payout_percentage')
        if payout is not None:
            if payout > 95:
                raise forms.ValidationError("Payout percentage cannot exceed 95% (5% platform fee is required).")
            if payout < 75:
                raise forms.ValidationError("Minimum payout percentage is 75%.")
        return payout
    
    def clean_partner_referral_code(self):
        code = self.cleaned_data.get('partner_referral_code')
        if code:
            from accounts.models import RaffleOrganizerProfile
            if not RaffleOrganizerProfile.objects.filter(referral_code=code.strip().upper()).exists():
                raise forms.ValidationError("Invalid partnership referral code.")
        return code.strip().upper() if code else None

class RaffleWithdrawalForm(forms.ModelForm):
    class Meta:
        model = RaffleWithdrawalRequest
        fields = ['amount', 'bank_name', 'account_number', 'account_name']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'min': '5000', 'placeholder': 'Amount'}),
            'bank_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Bank Name'}),
            'account_number': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Account Number'}),
            'account_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Account Name'}),
        }
