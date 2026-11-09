from django import forms
from .models import Enquiry


class EnquiryForm(forms.ModelForm):
    # Honeypot: real people leave this empty, bots fill it in.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'tabindex': '-1', 'autocomplete': 'off', 'class': 'hp'}))

    class Meta:
        model = Enquiry
        fields = ['name', 'email', 'phone', 'interest', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Full name', 'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
            'phone': forms.TextInput(attrs={'placeholder': '+254 7XX XXX XXX', 'autocomplete': 'tel'}),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Tell us about your property, your power needs, or the product you are interested in.'}),
        }

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Spam detected.')
        return ''

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError('Enter a valid phone number, e.g. 0712 345 678.')
        return phone
