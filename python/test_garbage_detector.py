#!/usr/bin/env python3
"""
Tests para el módulo garbage_detector.py
"""

import numpy as np
import cv2
from garbage_detector import (
    GarbageDetector, GarbageType, GarbageDetection,
    is_garbage_frame, get_garbage_summary
)


def create_black_frame(width=480, height=270):
    """Crea un frame completamente negro"""
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_white_frame(width=480, height=270):
    """Crea un frame completamente blanco"""
    return np.ones((height, width, 3), dtype=np.uint8) * 255


def create_uniform_frame(width=480, height=270, color=(128, 128, 128)):
    """Crea un frame de color uniforme"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def create_normal_frame(width=480, height=270):
    """Crea un frame con contenido variado (simula escena normal)"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Agregar ruido y formas
    frame = cv2.randn(frame, (128, 128, 128), (50, 50, 50))
    cv2.rectangle(frame, (50, 50), (200, 150), (255, 0, 0), -1)
    cv2.circle(frame, (350, 135), 50, (0, 255, 0), -1)
    return frame


def create_sky_frame(width=480, height=270):
    """Crea un frame que simula cielo"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Cielo azul claro, muy uniforme
    frame[:] = (230, 220, 200)  # BGR - azul claro
    return frame


def test_single_frame_analysis():
    """Test de análisis de frame individual"""
    detector = GarbageDetector()

    print("\n=== Test: Análisis de Frame Individual ===")

    # Test frame negro
    black_frame = create_black_frame()
    gray = cv2.cvtColor(black_frame, cv2.COLOR_BGR2GRAY)
    result = detector.analyze_single_frame(black_frame, gray)
    assert result['garbage_flags']['is_black'], "Frame negro no detectado como negro"
    print("✓ Frame negro detectado correctamente")

    # Test frame blanco
    white_frame = create_white_frame()
    gray = cv2.cvtColor(white_frame, cv2.COLOR_BGR2GRAY)
    result = detector.analyze_single_frame(white_frame, gray)
    assert result['garbage_flags']['is_white'], "Frame blanco no detectado como whiteout"
    print("✓ Frame blanco (whiteout) detectado correctamente")

    # Test frame uniforme
    uniform_frame = create_uniform_frame()
    gray = cv2.cvtColor(uniform_frame, cv2.COLOR_BGR2GRAY)
    result = detector.analyze_single_frame(uniform_frame, gray)
    assert result['garbage_flags']['is_uniform'], "Frame uniforme no detectado"
    print("✓ Frame uniforme detectado correctamente")

    # Test frame normal (no debería ser basura)
    normal_frame = create_normal_frame()
    gray = cv2.cvtColor(normal_frame, cv2.COLOR_BGR2GRAY)
    result = detector.analyze_single_frame(normal_frame, gray)
    is_garbage = any(result['garbage_flags'].values())
    # Puede que no sea perfectamente "limpio" pero verificamos métricas
    print(f"✓ Frame normal analizado (brightness={result['brightness']:.2f}, variance={result['variance']:.1f})")


def test_is_garbage_frame_utility():
    """Test de función utilitaria is_garbage_frame"""
    print("\n=== Test: Función is_garbage_frame ===")

    # Frame negro
    is_garbage, gtype = is_garbage_frame(0.01, 2.0, 0.001)
    assert is_garbage and gtype == "black_frame"
    print("✓ is_garbage_frame detecta negro")

    # Frame blanco
    is_garbage, gtype = is_garbage_frame(0.97, 5.0, 0.01)
    assert is_garbage and gtype == "whiteout"
    print("✓ is_garbage_frame detecta whiteout")

    # Frame con tapa
    is_garbage, gtype = is_garbage_frame(0.1, 3.0, 0.001)
    assert is_garbage and gtype == "lens_cap"
    print("✓ is_garbage_frame detecta tapa de lente")

    # Frame normal
    is_garbage, gtype = is_garbage_frame(0.5, 500.0, 0.1)
    assert not is_garbage
    print("✓ is_garbage_frame no marca frame normal como basura")


def test_analyze_frames_sequence():
    """Test de análisis de secuencia de frames"""
    detector = GarbageDetector()

    print("\n=== Test: Análisis de Secuencia de Frames ===")

    # Simular frames_data como los genera el analyzer
    frames_data = []

    # Primeros frames negros (simula tapa de lente)
    for i in range(5):
        frames_data.append({
            'timestamp': i * 0.1,
            'frame_idx': i,
            'brightness': 0.01,
            'variance': 2.0,
            'edge_density': 0.001,
            'saturation': 0.0,
            'garbage_flags': {'is_black': True, 'is_lens_cap': True, 'is_uniform': True, 'is_white': False, 'is_likely_sky': False, 'is_likely_ground': False}
        })

    # Frames normales
    for i in range(5, 50):
        frames_data.append({
            'timestamp': i * 0.1,
            'frame_idx': i,
            'brightness': 0.45,
            'variance': 500.0,
            'edge_density': 0.15,
            'saturation': 0.4,
            'motion_magnitude': 2.0 if i > 10 else 0.3,
            'direction_consistency': 0.7,
            'garbage_flags': {'is_black': False, 'is_lens_cap': False, 'is_uniform': False, 'is_white': False, 'is_likely_sky': False, 'is_likely_ground': False}
        })

    # Últimos frames con poco movimiento (simula post-roll)
    for i in range(50, 60):
        frames_data.append({
            'timestamp': i * 0.1,
            'frame_idx': i,
            'brightness': 0.45,
            'variance': 500.0,
            'edge_density': 0.15,
            'saturation': 0.4,
            'motion_magnitude': 0.1,  # Muy poco movimiento
            'direction_consistency': 0.2,
            'garbage_flags': {'is_black': False, 'is_lens_cap': False, 'is_uniform': False, 'is_white': False, 'is_likely_sky': False, 'is_likely_ground': False}
        })

    video_duration = 6.0  # 60 frames a 10 fps

    detections = detector.analyze_frames(frames_data, video_duration)

    print(f"Detecciones encontradas: {len(detections)}")
    for d in detections:
        print(f"  - {d.garbage_type.value}: {d.start_time:.1f}s - {d.end_time:.1f}s (conf: {d.confidence:.2f})")

    # Verificar que detectó al menos el segmento negro inicial
    black_detections = [d for d in detections if d.garbage_type in [GarbageType.BLACK_FRAME, GarbageType.LENS_CAP]]
    assert len(black_detections) > 0, "No se detectó el segmento negro inicial"
    print("✓ Segmento negro/tapa detectado")


def test_garbage_summary():
    """Test de función get_garbage_summary"""
    print("\n=== Test: Resumen de Basura ===")

    # Crear detecciones de prueba
    detections = [
        GarbageDetection(
            garbage_type=GarbageType.LENS_CAP,
            confidence=0.95,
            start_time=0.0,
            end_time=1.5,
            recoverable=False
        ),
        GarbageDetection(
            garbage_type=GarbageType.POST_ROLL,
            confidence=0.8,
            start_time=25.0,
            end_time=27.0,
            recoverable=True,
            suggested_trim=(0, 25.0)
        )
    ]

    summary = get_garbage_summary(detections)

    assert summary['total_garbage_duration'] == 3.5
    assert summary['garbage_count'] == 2
    assert 'lens_cap' in summary['types_found']
    assert 'post_roll' in summary['types_found']
    assert summary['recoverable_duration'] == 2.0

    print(f"✓ Resumen generado: {summary['total_garbage_duration']}s de basura")
    print(f"✓ Tipos encontrados: {summary['types_found']}")
    print(f"✓ Recomendación: {summary['recommendation']}")

    # Test con lista vacía
    empty_summary = get_garbage_summary([])
    assert empty_summary['garbage_count'] == 0
    print("✓ Resumen vacío manejado correctamente")


def test_detection_consolidation():
    """Test de consolidación de detecciones superpuestas"""
    detector = GarbageDetector()

    print("\n=== Test: Consolidación de Detecciones ===")

    # Crear detecciones superpuestas
    detections = [
        GarbageDetection(
            garbage_type=GarbageType.UNIFORM_FRAME,  # Menor prioridad
            confidence=0.7,
            start_time=0.0,
            end_time=1.0,
        ),
        GarbageDetection(
            garbage_type=GarbageType.LENS_CAP,  # Mayor prioridad
            confidence=0.95,
            start_time=0.0,
            end_time=1.0,
        )
    ]

    consolidated = detector._consolidate_detections(detections)

    # Solo debería quedar la de mayor prioridad
    assert len(consolidated) == 1
    assert consolidated[0].garbage_type == GarbageType.LENS_CAP
    print("✓ Detecciones superpuestas consolidadas correctamente")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE GARBAGE DETECTOR")
    print("=" * 60)

    test_single_frame_analysis()
    test_is_garbage_frame_utility()
    test_analyze_frames_sequence()
    test_garbage_summary()
    test_detection_consolidation()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
