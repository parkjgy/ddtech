from rest_framework import serializers

from .models import Staff


class StaffLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ('login_id', 'login_pw')
