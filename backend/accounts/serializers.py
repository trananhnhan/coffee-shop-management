from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import Branch, User, Role



#  ------BRANCH-----


class ListBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'phone', 'table_capacity', 'is_active']
        read_only_fields = fields


class RetrieveBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'phone', 'table_capacity', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class CreateBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'phone', 'table_capacity']


class PartialUpdateBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'phone', 'table_capacity']


# ---------USER--------


class ListUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'branch', 'is_active']
        read_only_fields = fields


class RetrieveUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'branch', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'branch']

    def validate(self, data):
        request_user = self.context['request'].user

        # logic if Store Manager is creating new user
        if request_user.role == Role.STORE_MANAGER:
            # force branch
            data['branch'] = request_user.branch

            # must be assigning right role
            role = data.get('role')
            if role not in [Role.CASHIER, Role.KITCHEN]:
                raise serializers.ValidationError({"detail": "Store manager can only assign cashier or kitchen roles."})

        # logic if Owner is creating new user
        elif request_user.role == Role.OWNER:
            # must assign branch
            if not data.get('branch') and data.get('role') != Role.OWNER:
                raise serializers.ValidationError({"detail": "Branch is required for staff accounts."})

        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class PartialUpdateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['password', 'role', 'branch']

    def validate(self, data):
        request_user = self.context['request'].user

        # Store Manager can't change employee branch or promote to manager
        if request_user.role == Role.STORE_MANAGER:
            if 'branch' in data and data['branch'] != request_user.branch:
                raise serializers.ValidationError({"detail": "Cannot move user to another branch."})
            if 'role' in data and data['role'] not in [Role.CASHIER, Role.KITCHEN]:
                raise serializers.ValidationError({"detail": "Cannot promote user to manager."})

        return data

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)


