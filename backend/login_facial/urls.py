from django.urls import path
from . import views

app_name = 'login_facial'

urlpatterns = [
    # Autenticación
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/facial-login/', views.FacialLoginView.as_view(), name='facial_login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.UserProfileView.as_view(), name='user_profile'),
    
    # Registro facial (solo post-login)
    path('auth/facial-register/', views.FacialRegisterView.as_view(), name='facial_register'),
    
    # Gestión de usuarios (solo administradores)
    path('users/', views.UsuarioListCreateView.as_view(), name='user_list_create'),
    path('users/<int:pk>/', views.UsuarioDetailView.as_view(), name='user_detail'),
    path('users/dni/<str:dni>/', views.usuario_by_dni, name='user_by_dni'),
    
    # Verificación de permisos
    path('auth/permissions/', views.PermissionCheckView.as_view(), name='permission_check'),
]