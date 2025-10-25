from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import json


class UsuarioManager(BaseUserManager):
    """Manager personalizado para el modelo Usuario"""
    
    def create_user(self, email, dni, nombres, apellidos, password=None, **extra_fields):
        """Crea y guarda un usuario regular"""
        if not email:
            raise ValueError('El email es obligatorio')
        if not dni:
            raise ValueError('El DNI es obligatorio')
        if not nombres:
            raise ValueError('Los nombres son obligatorios')
        if not apellidos:
            raise ValueError('Los apellidos son obligatorios')
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            dni=dni,
            nombres=nombres,
            apellidos=apellidos,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, dni, nombres, apellidos, password=None, **extra_fields):
        """Crea y guarda un superusuario"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', 'Administrador')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, dni, nombres, apellidos, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado basado en la especificación técnica.
    Extiende AbstractUser para mantener compatibilidad con Django auth.
    """
    ROLES = [
        ('Administrador', 'Administrador'),
        ('Analista', 'Analista'),
    ]
    
    ESTADOS = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
    ]
    
    # Campos requeridos por la documentación
    dni = models.CharField(max_length=8, unique=True, help_text="Documento de identidad")
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=120)
    rol = models.CharField(max_length=20, choices=ROLES, default='Analista')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='Activo')
    face_registered = models.BooleanField(default=False, help_text="Indica si el usuario tiene registro facial")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Sobrescribir campos de AbstractUser para usar email como username
    username = models.CharField(max_length=150, unique=True, blank=True)
    email = models.EmailField(max_length=120, unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['dni', 'nombres', 'apellidos']
    
    # Manager personalizado
    objects = UsuarioManager()
    
    class Meta:
        db_table = 'registro_usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def save(self, *args, **kwargs):
        # Auto-generar username basado en email si no se proporciona
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.dni})"
    
    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"
    
    def has_permission(self, permission):
        """Verifica permisos basados en rol según documentación"""
        admin_permissions = [
            'view_dashboard', 'view_transactions', 'view_alerts', 
            'view_models', 'view_configuration', 'manage_users',
            'retrain_models'
        ]
        analyst_permissions = ['view_dashboard', 'view_transactions']
        
        if self.rol == 'Administrador':
            return permission in admin_permissions
        elif self.rol == 'Analista':
            return permission in analyst_permissions
        return False


class DatosFaciales(models.Model):
    """
    Almacena los datos de reconocimiento facial de los usuarios.
    Basado en las utilidades faciales migradas desde backend2.
    """
    usuario = models.OneToOneField(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name='datos_faciales'
    )
    
    # Embeddings faciales (almacenados como JSON para flexibilidad)
    embeddings = models.JSONField(
        help_text="Lista de embeddings faciales del usuario (múltiples muestras)"
    )
    
    # Posiciones faciales para validación
    posiciones = models.JSONField(
        help_text="Lista de posiciones faciales correspondientes a los embeddings"
    )
    
    # Metadatos
    num_muestras = models.IntegerField(default=0)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'datos_faciales'
        verbose_name = 'Datos Faciales'
        verbose_name_plural = 'Datos Faciales'
    
    def __str__(self):
        return f"Datos faciales de {self.usuario.nombre_completo}"
    
    def agregar_muestra(self, embedding, posicion):
        """Agrega una nueva muestra facial"""
        if not self.embeddings:
            self.embeddings = []
        if not self.posiciones:
            self.posiciones = []
            
        # Convertir numpy array a lista si es necesario
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
            
        self.embeddings.append(embedding)
        self.posiciones.append(posicion)
        self.num_muestras = len(self.embeddings)
        self.save()
    
    def obtener_embeddings(self):
        """Retorna los embeddings como lista de arrays numpy"""
        import numpy as np
        return [np.array(emb, dtype=np.float32) for emb in self.embeddings or []]


class SesionFacial(models.Model):
    """
    Registro de intentos de autenticación facial para auditoría.
    """
    RESULTADOS = [
        ('exitoso', 'Exitoso'),
        ('fallido', 'Fallido'),
        ('error', 'Error'),
    ]
    
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name='sesiones_faciales',
        null=True, blank=True  # Puede ser null si no se identifica el usuario
    )
    
    resultado = models.CharField(max_length=10, choices=RESULTADOS)
    confianza = models.FloatField(null=True, blank=True, help_text="Nivel de confianza del reconocimiento")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    detalles = models.JSONField(null=True, blank=True, help_text="Detalles adicionales del intento")
    
    class Meta:
        db_table = 'sesiones_faciales'
        verbose_name = 'Sesión Facial'
        verbose_name_plural = 'Sesiones Faciales'
        ordering = ['-timestamp']
    
    def __str__(self):
        usuario_str = self.usuario.nombre_completo if self.usuario else "Usuario desconocido"
        return f"{usuario_str} - {self.resultado} ({self.timestamp})"
