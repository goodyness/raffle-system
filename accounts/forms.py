from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, RaffleOrganizerProfile

class OrganizerRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}))
    
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'phone_number']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Phone Number'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class ParticipantRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}))

    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'phone_number']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Phone Number'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'phone_number', 'bank_name', 'account_number', 'account_name']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}),
            'phone_number': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium'}),
            'bank_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'e.g. Guarantee Trust Bank'}),
            'account_number': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': '10 Digit Account Number'}),
            'account_name': forms.TextInput(attrs={'class': 'w-full bg-black/40 border border-white/10 text-white px-6 py-4 rounded-2xl outline-none focus:border-[#A2F625] transition font-medium', 'placeholder': 'Account Holder Name'}),
        }
