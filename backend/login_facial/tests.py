from django.test import TestCase

import numpy as np

from .views import (
    _compare_embeddings,
    _compare_to_collection,
    _validate_position_collection,
    _validate_position,
)


class DummyUser:
    def __init__(self):
        self.facial_data = None
        self.facial_embeddings = []
        self.failed_attempts = 0
        self.positions = []
        self.position_data = None


class FacialUtilsTests(TestCase):
    def test_compare_embeddings_cosine(self):
        a = np.random.rand(128).astype(np.float32)
        b = a + np.random.normal(0, 0.01, size=128).astype(np.float32)
        a_bytes = a.tobytes()
        self.assertTrue(_compare_embeddings(a_bytes, b))

    def test_compare_to_collection_threshold(self):
        user = DummyUser()
        base = np.zeros(128, dtype=np.float32)
        user.facial_embeddings = [base]
        live = base + 0.01
        self.assertTrue(_compare_to_collection(user, live))
        user.failed_attempts = 5
        live = base + 0.5
        self.assertFalse(_compare_to_collection(user, live))

    def test_validate_position_collection(self):
        user = DummyUser()
        user.positions = [
            {'x': 0.5, 'y': 0.5, 'scale': 1.0},
            {'roll': 0, 'pitch': 0, 'yaw': 0, 'dist': 0.2},
        ]
        self.assertTrue(_validate_position_collection(user, {'x': 0.52, 'y': 0.48, 'scale': 1.04}))
        self.assertTrue(_validate_position_collection(user, {'roll': 1, 'pitch': 1, 'yaw': 1, 'dist': 0.25}))
        self.assertFalse(_validate_position_collection(user, {'x': 0.9, 'y': 0.9, 'scale': 1.5}))

    def test_validate_position_single(self):
        stored = {'x': 0.5, 'y': 0.5, 'scale': 1.0}
        live = {'x': 0.55, 'y': 0.45, 'scale': 1.1}
        self.assertTrue(_validate_position(stored, live))
        live_bad = {'x': 0.8, 'y': 0.2, 'scale': 1.5}
        self.assertFalse(_validate_position(stored, live_bad))
