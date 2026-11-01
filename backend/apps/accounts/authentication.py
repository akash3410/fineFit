from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = kwargs.get('identifier') or username or kwargs.get('email') or kwargs.get('phone')
        if identifier is None or password is None:
            return None
        identifier = str(identifier).strip()
        users = User.objects.filter(Q(email__iexact=identifier) | Q(phone_number=identifier))
        if users.count() != 1:
            return None
        user = users.first()
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
