import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class StrongPasswordValidator:
    uppercase_pattern = re.compile(r"[A-Z]")
    number_pattern = re.compile(r"\d")
    special_pattern = re.compile(r"[^A-Za-z0-9]")

    def validate(self, password, user=None):
        errors = []
        if not self.uppercase_pattern.search(password):
            errors.append(_("Password must contain at least one uppercase letter."))
        if not self.number_pattern.search(password):
            errors.append(_("Password must contain at least one number."))
        if not self.special_pattern.search(password):
            errors.append(_("Password must contain at least one special character."))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _("Your password must include at least one uppercase letter, one number, and one special character.")
