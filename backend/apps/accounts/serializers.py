from rest_framework import serializers
from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for public/authenticated user profile.
    """

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_staff",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "is_staff", "date_joined"]
