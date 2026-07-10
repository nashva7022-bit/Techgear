import re
from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    

    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters long.",
                code='password_too_short',
            )
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                "Password must contain at least one uppercase letter.",
                code='password_no_upper',
            )
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                "Password must contain at least one lowercase letter.",
                code='password_no_lower',
            )
        if not re.search(r'\d', password):
            raise ValidationError(
                "Password must contain at least one number.",
                code='password_no_digit',
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-\[\]\/\\]', password):
            raise ValidationError(
                "Password must contain at least one special character (!@#$%^&* etc).",
                code='password_no_special',
            )

    def get_help_text(self):
        return (
            "Your password must be at least 8 characters and include "
            "an uppercase letter, lowercase letter, number and special character."
        )