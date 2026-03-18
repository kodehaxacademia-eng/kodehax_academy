from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{timestamp}{user.is_active}{getattr(user, 'is_email_verified', False)}"


class TeacherInvitationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, invitation, timestamp):
        return f"{invitation.pk}{invitation.email}{invitation.token}{timestamp}{invitation.is_used}"


email_verification_token = EmailVerificationTokenGenerator()
teacher_invitation_token = TeacherInvitationTokenGenerator()
