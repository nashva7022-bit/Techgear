from django import forms


class AdminLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Admin Email",
                "class": "w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-black focus:border-black outline-none transition",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-black focus:border-black outline-none transition",
            }
        )
    )
