from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Usuario, DatosFaciales, SesionFacial


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Usuario"""
    nombre_completo = serializers.ReadOnlyField()
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'dni', 'nombres', 'apellidos', 'email', 'rol', 
            'estado', 'face_registered', 'created_at', 'nombre_completo'
        ]
        read_only_fields = ['id', 'created_at', 'nombre_completo']


class UsuarioCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear usuarios"""
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Usuario
        fields = [
            'dni', 'nombres', 'apellidos', 'email', 'rol', 'estado', 'password'
        ]
    
    def validate_dni(self, value):
        if not value.isdigit() or len(value) != 8:
            raise serializers.ValidationError("DNI debe tener exactamente 8 dígitos")
        return value
    
    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este email")
        return value
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        usuario = Usuario.objects.create_user(**validated_data)
        if password:
            usuario.set_password(password)
            usuario.save()
        return usuario


class LoginSerializer(serializers.Serializer):
    """Serializer para login tradicional"""
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError("Credenciales inválidas")
            if user.estado != 'Activo':
                raise serializers.ValidationError("Usuario inactivo")
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Email y contraseña son requeridos")
        
        return attrs


class FacialLoginSerializer(serializers.Serializer):
    """Serializer para login facial"""
    facial_data = serializers.CharField(help_text="Datos faciales en base64")
    
    def validate_facial_data(self, value):
        if not value or len(value) < 100:  # Validación básica
            raise serializers.ValidationError("Datos faciales inválidos")
        return value


class FacialRegisterSerializer(serializers.Serializer):
    """Serializer para registro facial"""
    facial_samples = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=10,
        help_text="Lista de muestras faciales en base64"
    )
    
    def validate_facial_samples(self, value):
        if not value:
            raise serializers.ValidationError("Se requiere al menos una muestra facial")
        
        for sample in value:
            if not sample or len(sample) < 100:
                raise serializers.ValidationError("Muestra facial inválida")
        
        return value


class DatosFacialesSerializer(serializers.ModelSerializer):
    """Serializer para datos faciales"""
    usuario_nombre = serializers.CharField(source='usuario.nombre_completo', read_only=True)
    
    class Meta:
        model = DatosFaciales
        fields = [
            'id', 'usuario', 'usuario_nombre', 'num_muestras', 
            'fecha_registro', 'fecha_actualizacion', 'activo'
        ]
        read_only_fields = ['id', 'fecha_registro', 'fecha_actualizacion']


class SesionFacialSerializer(serializers.ModelSerializer):
    """Serializer para sesiones faciales"""
    usuario_nombre = serializers.CharField(source='usuario.nombre_completo', read_only=True)
    
    class Meta:
        model = SesionFacial
        fields = [
            'id', 'usuario', 'usuario_nombre', 'resultado', 'confianza',
            'ip_address', 'timestamp', 'detalles'
        ]
        read_only_fields = ['id', 'timestamp']


class PermissionCheckSerializer(serializers.Serializer):
    """Serializer para verificación de permisos"""
    permission = serializers.CharField(help_text="Permiso a verificar")
    
    def validate_permission(self, value):
        valid_permissions = [
            'view_dashboard', 'view_transactions', 'view_alerts', 
            'view_models', 'view_configuration', 'manage_users', 'retrain_models'
        ]
        if value not in valid_permissions:
            raise serializers.ValidationError(f"Permiso inválido. Válidos: {valid_permissions}")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer para perfil de usuario"""
    nombre_completo = serializers.ReadOnlyField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'dni', 'nombres', 'apellidos', 'email', 'rol', 
            'estado', 'face_registered', 'created_at', 'nombre_completo', 'permissions'
        ]
        read_only_fields = ['id', 'created_at', 'nombre_completo', 'permissions']
    
    def get_permissions(self, obj):
        """Retorna los permisos del usuario basados en su rol"""
        all_permissions = [
            'view_dashboard', 'view_transactions', 'view_alerts', 
            'view_models', 'view_configuration', 'manage_users', 'retrain_models'
        ]
        return [perm for perm in all_permissions if obj.has_permission(perm)]