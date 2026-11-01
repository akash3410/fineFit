from rest_framework import serializers
from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for public/authenticated user profile.
    """

    groups = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    is_superuser = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "email_verified",
            "phone_verified",
            "account_verified",
            "is_staff",
            "is_superuser",
            "is_active",
            "date_joined",
            "last_login",
            "groups",
            "permissions",
        ]
        read_only_fields = ["id", "email", "is_staff", "is_superuser", "date_joined"]

    def get_groups(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]

    def get_permissions(self, obj):
        if obj.is_superuser:
            return ["*"]
        perms = set()
        for perm in obj.user_permissions.all():
            perms.add(f"{perm.content_type.app_label}.{perm.codename}")
        for group in obj.groups.all():
            for perm in group.permissions.all():
                perms.add(f"{perm.content_type.app_label}.{perm.codename}")
        return sorted(list(perms))

    def get_is_superuser(self, obj):
        return obj.is_superuser
