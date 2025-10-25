"""Views y utilidades de reconocimiento facial para la app login_facial.

Este módulo centraliza la lógica facial (funciones puras) migrada desde
`login_facial/facial.py` aplicando PEP 8 y principios de responsabilidad única.

Las funciones internas (prefijo `_`) se diseñan para ser reutilizables desde
vistas y pruebas, manteniendo firmas y umbrales de la implementación previa.
"""
import base64
import logging
from typing import Optional
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Usuario, DatosFaciales, SesionFacial
from .serializers import (
    UsuarioSerializer, UsuarioCreateSerializer, LoginSerializer,
    FacialLoginSerializer, FacialRegisterSerializer, DatosFacialesSerializer,
    SesionFacialSerializer, PermissionCheckSerializer, UserProfileSerializer
)

try:
    import numpy as np
    import cv2
except Exception:  # pragma: no cover
    np = None
    cv2 = None

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except Exception:  # pragma: no cover
    face_recognition = None
    FACE_RECOGNITION_AVAILABLE = False


# -----------------------------
# Utilidades de embeddings
# -----------------------------

def _compute_embedding_from_b64(b64_str) -> Optional['np.ndarray']:
    """Genera un embedding facial (np.ndarray float32) desde un frame base64.

    - Si `face_recognition` está disponible: produce un vector de 128 dims.
    - Fallback sin `face_recognition`: vector normalizado del recorte central.
    - Retorna `None` si no se puede decodificar o no hay rostro.
    """
    log = logging.getLogger('facial')
    if not b64_str:
        log.debug('compute_embedding: b64_str vacío')
        return None
    if np is None:
        log.debug('compute_embedding: numpy no disponible')
        return None
    try:
        header, encoded = b64_str.split(',') if ',' in b64_str else ('', b64_str)
        img_bytes = base64.b64decode(encoded)
        image = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image, cv2.IMREAD_COLOR) if cv2 is not None else None
        if frame is None:
            log.debug('compute_embedding: cv2.imdecode devolvió None')
            return None
        if face_recognition is not None:
            rgb = frame[:, :, ::-1]
            boxes = face_recognition.face_locations(rgb, model='hog')
            log.debug(f'compute_embedding: boxes={len(boxes)}')
            if not boxes:
                return None
            encs = face_recognition.face_encodings(rgb, boxes)
            log.debug(f'compute_embedding: encs={len(encs)}')
            if not encs:
                return None
            return np.array(encs[0], dtype=np.float32)
        else:
            # Fallback: promedio de píxeles del recorte central como "huella" simple
            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2
            crop = frame[max(cy-100, 0):cy+100, max(cx-100, 0):cx+100]
            if crop.size == 0:
                log.debug('compute_embedding: crop vacío en fallback')
                return None
            emb = cv2.resize(crop, (16, 16)).astype('float32').reshape(-1)
            emb = emb / (np.linalg.norm(emb) + 1e-6)
            return emb
    except Exception as e:
        logging.getLogger('facial').exception(f'compute_embedding: excepción {e}')
        return None


def _compare_embeddings(stored_bytes: bytes, live_emb) -> bool:
    """Compara un embedding almacenado (bytes) con uno vivo (`np.ndarray`).

    - Con `face_recognition`: distancia euclidiana en primeras 128 dims (<0.6).
    - Fallback: similitud de coseno (>0.9).
    """
    if stored_bytes is None or live_emb is None or np is None:
        return False
    try:
        stored = np.frombuffer(stored_bytes, dtype=np.float32)
        if face_recognition is not None and stored.shape[0] in (128, 129):
            dist = np.linalg.norm(stored[:128] - live_emb[:128])
            return dist < 0.6
        else:
            num = float(np.dot(stored, live_emb))
            den = (np.linalg.norm(stored) * np.linalg.norm(live_emb) + 1e-6)
            sim = num / den
            return sim > 0.9
    except Exception:
        return False

def _compare_to_collection(user, live_emb) -> bool:
    """Compara el embedding vivo con la colección registrada del usuario.

    - Si no hay colección, usa `_compare_embeddings` sobre `user.facial_data`.
    - Umbral base 0.45 adaptado por intentos fallidos hasta 0.55.
    """
    try:
        if live_emb is None:
            return False
        if np is None:
            return _compare_embeddings(getattr(user, 'facial_data', None), live_emb)
        if not getattr(user, 'facial_embeddings', None):
            return _compare_embeddings(getattr(user, 'facial_data', None), live_emb)

        base_thr = 0.45
        attempts = getattr(user, 'failed_attempts', 0) or 0
        thr = min(base_thr + attempts * 0.03, 0.55)

        live = np.array(live_emb, dtype=np.float32)
        for emb_list in getattr(user, 'facial_embeddings'):
            stored = np.array(emb_list, dtype=np.float32)
            dist = float(np.linalg.norm(stored[:128] - live[:128]))
            if dist < thr:
                return True
        return False
    except Exception:
        return False


def _compare_faces(known_encoding, face_encoding, tolerance=0.6):
    """Compara dos encodings faciales y retorna la distancia y si coinciden."""
    try:
        if FACE_RECOGNITION_AVAILABLE and face_recognition is not None:
            distances = face_recognition.face_distance([known_encoding], face_encoding)
            distance = distances[0]
            matches = distance <= tolerance
        else:
            # Modo simulado: calcular distancia euclidiana
            distance = np.linalg.norm(known_encoding - face_encoding)
            matches = distance <= tolerance * 100  # Ajustar umbral para simulación
            
        return matches, float(distance)
    except Exception as e:
        logging.getLogger('facial').exception(f'Error al comparar rostros: {e}')
        return False, 1.0


def get_tokens_for_user(user):
    """Genera tokens JWT para un usuario"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class LoginView(APIView):
    """Vista para login tradicional con email y contraseña"""
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            
            return Response({
                'success': True,
                'message': 'Login exitoso',
                'tokens': tokens,
                'user': UserProfileSerializer(user).data
            })
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class FacialLoginView(APIView):
    """Vista para login facial"""
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    
    def post(self, request):
        serializer = FacialLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        facial_data = serializer.validated_data['facial_data']
        
        # Generar embedding de la imagen recibida
        face_encoding = _compute_embedding_from_b64(facial_data)
        if face_encoding is None:
            return Response({
                'success': False,
                'message': 'No se pudo procesar la imagen facial'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar coincidencias en la base de datos
        best_match = None
        best_distance = float('inf')
        
        try:
            for datos_faciales in DatosFaciales.objects.filter(activo=True):
                if datos_faciales.embedding is not None:
                    matches, distance = _compare_faces(datos_faciales.embedding, face_encoding)
                    
                    if matches and distance < best_distance:
                        best_match = datos_faciales.usuario
                        best_distance = distance
        except Exception:
            pass
        
        if best_match:
            confianza = max(0, 1 - best_distance)  # Convertir distancia a confianza
            tokens = get_tokens_for_user(best_match)
            
            return Response({
                'success': True,
                'message': 'Login facial exitoso',
                'tokens': tokens,
                'user': UserProfileSerializer(best_match).data,
                'confidence': confianza
            })
        else:
            return Response({
                'success': False,
                'message': 'No se encontró coincidencia facial'
            }, status=status.HTTP_401_UNAUTHORIZED)


class FacialRegisterView(APIView):
    """Vista para registro facial (solo usuarios autenticados)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = FacialRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        facial_samples = serializer.validated_data['facial_samples']
        user = request.user
        
        # Procesar muestras faciales
        embeddings = []
        for sample in facial_samples:
            embedding = _compute_embedding_from_b64(sample)
            if embedding is not None:
                embeddings.append(embedding)
        
        if not embeddings:
            return Response({
                'success': False,
                'message': 'No se pudieron procesar las muestras faciales'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calcular embedding promedio
        if np is not None:
            avg_embedding = np.mean(embeddings, axis=0)
        else:
            avg_embedding = embeddings[0]
        
        try:
            with transaction.atomic():
                # Eliminar datos faciales anteriores
                try:
                    DatosFaciales.objects.filter(usuario=user).delete()
                except Exception:
                    pass
                
                # Crear nuevos datos faciales
                datos_faciales = DatosFaciales.objects.create(
                    usuario=user,
                    embedding=avg_embedding,
                    num_muestras=len(embeddings),
                    activo=True
                )
                
                # Marcar usuario como registrado facialmente
                user.face_registered = True
                user.save()
                
                return Response({
                    'success': True,
                    'message': 'Registro facial completado exitosamente',
                    'samples_processed': len(embeddings)
                })
                
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """Obtener estado del registro facial del usuario actual"""
        user = request.user
        try:
            datos_faciales = DatosFaciales.objects.filter(usuario=user, activo=True).first()
        except Exception:
            datos_faciales = None
        
        return Response({
            'face_registered': getattr(user, 'face_registered', False),
            'registration_date': datos_faciales.fecha_registro if datos_faciales else None,
            'samples_count': datos_faciales.num_muestras if datos_faciales else 0
        })


class LogoutView(APIView):
    """Vista para logout"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'success': True,
                'message': 'Logout exitoso'
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Error al cerrar sesión'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """Vista para obtener perfil del usuario actual"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class PermissionCheckView(APIView):
    """Vista para verificar permisos del usuario"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PermissionCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        permission = serializer.validated_data['permission']
        has_permission = getattr(request.user, 'has_permission', lambda x: False)(permission)
        
        return Response({
            'has_permission': has_permission,
            'permission': permission,
            'user_role': getattr(request.user, 'rol', 'usuario')
        })


class UsuarioListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear usuarios"""
    queryset = Usuario.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UsuarioCreateSerializer
        return UsuarioSerializer
    
    def perform_create(self, serializer):
        # Solo administradores pueden crear usuarios
        if not getattr(self.request.user, 'has_permission', lambda x: False)('manage_users'):
            raise permissions.PermissionDenied("No tiene permisos para crear usuarios")
        serializer.save()


class UsuarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para detalle, actualización y eliminación de usuarios"""
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        # Solo administradores pueden actualizar usuarios
        if not getattr(self.request.user, 'has_permission', lambda x: False)('manage_users'):
            raise permissions.PermissionDenied("No tiene permisos para actualizar usuarios")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo administradores pueden eliminar usuarios
        if not getattr(self.request.user, 'has_permission', lambda x: False)('manage_users'):
            raise permissions.PermissionDenied("No tiene permisos para eliminar usuarios")
        instance.delete()


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def usuario_by_dni(request, dni):
    """Buscar usuario por DNI"""
    try:
        usuario = Usuario.objects.get(dni=dni)
        serializer = UsuarioSerializer(usuario)
        return Response(serializer.data)
    except Usuario.DoesNotExist:
        return Response({
            'error': 'Usuario no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)


def _validate_position_collection(user, live_pos) -> bool:
    """Valida `live_pos` frente a posiciones registradas del usuario.

    - Si no hay colección, usa `user.position_data` como compatibilidad.
    - Tolerancias adaptativas en función de `failed_attempts`.
    """
    try:
        if not live_pos:
            return False
        positions = getattr(user, 'positions', None) or (
            [] if getattr(user, 'position_data', None) is None else [getattr(user, 'position_data')]
        )
        if not positions:
            return False

        attempts = getattr(user, 'failed_attempts', 0) or 0
        tol_xy = max(0.05, 0.10 - attempts * 0.01)
        tol_scale = max(0.08, 0.15 - attempts * 0.01)

        for p in positions:
            if all(k in p for k in ('x', 'y', 'scale')) and all(k in live_pos for k in ('x', 'y', 'scale')):
                if (
                    abs(p['x'] - live_pos['x']) <= tol_xy and
                    abs(p['y'] - live_pos['y']) <= tol_xy and
                    abs(p['scale'] - live_pos['scale']) <= tol_scale
                ):
                    return True
            if all(k in p for k in ('roll', 'pitch', 'yaw', 'dist')) and all(k in live_pos for k in ('roll', 'pitch', 'yaw', 'dist')):
                tol_ang = max(8, 15 - attempts * 1)
                tol_dist = max(0.12, 0.22 - attempts * 0.02)
                if (
                    abs(p['roll'] - live_pos['roll']) <= tol_ang and
                    abs(p['pitch'] - live_pos['pitch']) <= tol_ang and
                    abs(p['yaw'] - live_pos['yaw']) <= tol_ang and
                    abs(p['dist'] - live_pos['dist']) <= tol_dist
                ):
                    return True
        return False
    except Exception:
        return False


def _validate_position(stored_pos, live_pos) -> bool:
    """Valida una posición única con tolerancias fijas.

    Compatible con formato `{x,y,scale}` o `{roll,pitch,yaw,dist}`.
    """
    try:
        keys = ('x', 'y', 'scale')
        if all(k in stored_pos for k in keys) and all(k in live_pos for k in keys):
            tol_xy = 0.12
            tol_scale = 0.20
            ok = (
                abs(stored_pos['x'] - live_pos['x']) <= tol_xy and
                abs(stored_pos['y'] - live_pos['y']) <= tol_xy and
                abs(stored_pos['scale'] - live_pos['scale']) <= tol_scale
            )
            return ok
        angles = ('roll', 'pitch', 'yaw', 'dist')
        if all(k in stored_pos for k in angles) and all(k in live_pos for k in angles):
            tol_ang = 15
            tol_dist = 0.25
            return (
                abs(stored_pos['roll'] - live_pos['roll']) <= tol_ang and
                abs(stored_pos['pitch'] - live_pos['pitch']) <= tol_ang and
                abs(stored_pos['yaw'] - live_pos['yaw']) <= tol_ang and
                abs(stored_pos['dist'] - live_pos['dist']) <= tol_dist
            )
        return False
    except Exception:
        return False
