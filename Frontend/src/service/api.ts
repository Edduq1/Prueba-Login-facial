// Simple API client for backend facial auth

const BASE_URL = (import.meta.env?.VITE_API_BASE as string) || 'http://127.0.0.1:8000/api';

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.message || (Array.isArray(data?.errors) ? data.errors.join(', ') : data?.errors) || 'Error en la solicitud');
  }
  return data;
}

export async function loginTraditional(email: string, password: string) {
  return request('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function loginFacial(imageB64: string) {
  return request('/auth/facial-login/', {
    method: 'POST',
    body: JSON.stringify({ facial_data: imageB64 }),
  });
}

export async function getProfile(accessToken: string) {
  return request('/auth/me/', {
    method: 'GET',
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function registerFacial(samples: string[], accessToken: string) {
  return request('/auth/facial-register/', {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ facial_samples: samples }),
  });
}

export async function checkPermission(permission: string, accessToken: string) {
  return request('/auth/permissions/', {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ permission }),
  });
}