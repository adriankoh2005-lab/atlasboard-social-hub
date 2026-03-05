from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Card, SidebarItem


class CardCreateForm(forms.Form):
    title = forms.CharField(max_length=100)
    description = forms.CharField(widget=forms.Textarea, max_length=1000)
    category = forms.CharField(max_length=50)
    tags = forms.CharField(
        required=False,
        help_text='Comma-separated tags. Example: Python, Django',
    )


class CardImportForm(forms.Form):
    payload = forms.CharField(
        widget=forms.Textarea,
        help_text='Paste JSON array or {"cards": [...]} payload.',
    )
    replace_existing = forms.BooleanField(required=False)


class SidebarItemForm(forms.ModelForm):
    class Meta:
        model = SidebarItem
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        existing = SidebarItem.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('Sidebar item already exists.')
        return name


class CardUpdateForm(forms.ModelForm):
    tags = forms.CharField(required=False, help_text='Comma-separated tags.')

    class Meta:
        model = Card
        fields = ['title', 'description', 'category']


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
