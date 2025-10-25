from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, DatosFaciales, SesionFacial


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Administrador personalizado para el modelo Usuario"""
    
    list_display = ('email', 'dni', 'nombres', 'apellidos', 'rol', 'estado', 'face_registered', 'created_at')
    list_filter = ('rol', 'estado', 'face_registered', 'created_at')
    search_fields = ('email', 'dni', 'nombres', 'apellidos')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('dni', 'nombres', 'apellidos')}),
        ('Permisos', {'fields': ('rol', 'estado', 'face_registered', 'is_active', 'is_staff', 'is_superuser')}),
        ('Fechas Importantes', {'fields': ('last_login', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'dni', 'nombres', 'apellidos', 'rol', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('created_at',)


@admin.register(DatosFaciales)
class DatosFacialesAdmin(admin.ModelAdmin):
    """Administrador para el modelo DatosFaciales"""
    
    list_display = ('usuario', 'num_muestras', 'activo', 'fecha_registro', 'fecha_actualizacion')
    list_filter = ('activo', 'fecha_registro', 'fecha_actualizacion')
    search_fields = ('usuario__email', 'usuario__dni', 'usuario__nombres', 'usuario__apellidos')
    ordering = ('-fecha_registro',)
    
    fieldsets = (
        ('Usuario', {'fields': ('usuario',)}),
        ('Datos Faciales', {'fields': ('num_muestras', 'activo')}),
        ('Fechas', {'fields': ('fecha_registro', 'fecha_actualizacion')}),
    )
    
    readonly_fields = ('fecha_registro', 'fecha_actualizacion')


@admin.register(SesionFacial)
class SesionFacialAdmin(admin.ModelAdmin):
    """Administrador para el modelo SesionFacial"""
    
    list_display = ('usuario', 'resultado', 'confianza', 'ip_address', 'timestamp')
    list_filter = ('resultado', 'timestamp')
    search_fields = ('usuario__email', 'usuario__dni', 'ip_address')
    ordering = ('-timestamp',)
    
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        return False  # No permitir crear sesiones manualmente
