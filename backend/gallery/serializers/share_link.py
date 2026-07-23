from rest_framework import serializers

from gallery.models import ShareLink


class ShareLinkSerializer(serializers.ModelSerializer):
    """
    password is write_only: it comes in as plaintext when creating the link,
    but is stored hashed (see set_password() on the model). It is never
    returned in responses.
    """

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = ShareLink
        fields = [
            "id",
            "album",
            "token",
            "password",
            "expires_at",
            "is_active",
            "created_at",
            "url",
        ]
        read_only_fields = ["token", "created_at"]

    def get_url(self, obj):
        return f"/gallery/{obj.token}"

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        instance = ShareLink(**validated_data)
        instance.set_password(password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password is not None:
            instance.set_password(password)
            instance.save()
        return instance
