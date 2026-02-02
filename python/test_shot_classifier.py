#!/usr/bin/env python3
"""
Tests para el módulo shot_classifier.py
"""

import numpy as np
import cv2
from shot_classifier import (
    ShotClassifier, ShotType, ShotClassification,
    get_shot_type_display_name, get_shot_type_short_name
)


def create_frame_with_face(width=480, height=270, face_size_ratio=0.15):
    """Crea un frame con un 'rostro' simulado (rectángulo)"""
    frame = np.random.randint(100, 200, (height, width, 3), dtype=np.uint8)

    # Calcular tamaño del rostro
    face_h = int(height * face_size_ratio * 1.3)
    face_w = int(width * face_size_ratio)

    # Centrar el rostro
    x = (width - face_w) // 2
    y = (height - face_h) // 3  # Un poco arriba del centro

    # Dibujar área de rostro (tono piel)
    frame[y:y+face_h, x:x+face_w] = [180, 150, 140]  # BGR - tono piel

    return frame, (x, y, face_w, face_h)


def create_wide_shot_frame(width=480, height=270):
    """Crea un frame tipo plano general (paisaje, pocos detalles)"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Cielo (parte superior)
    frame[0:height//2, :] = [200, 180, 150]  # Azul claro

    # Tierra (parte inferior)
    frame[height//2:, :] = [80, 100, 60]  # Verde/marrón

    # Agregar algo de ruido para no ser completamente uniforme
    noise = np.random.randint(-10, 10, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return frame


def create_detail_shot_frame(width=480, height=270):
    """Crea un frame tipo plano detalle (muchos bordes, textura)"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Fondo con textura
    for i in range(0, height, 10):
        for j in range(0, width, 10):
            color = np.random.randint(50, 200, 3)
            frame[i:i+10, j:j+10] = color

    # Agregar bordes definidos
    cv2.rectangle(frame, (100, 50), (380, 220), (255, 255, 255), 2)
    cv2.circle(frame, (240, 135), 60, (0, 0, 255), 3)

    return frame


def test_classifier_initialization():
    """Test de inicialización del clasificador"""
    print("\n=== Test: Inicialización del Clasificador ===")

    classifier = ShotClassifier()
    assert classifier.cascades_loaded, "Haar cascades no cargados"
    print("✓ Classifier inicializado correctamente")
    print(f"✓ Haar cascades cargados: {classifier.cascades_loaded}")


def test_classify_from_metrics():
    """Test de clasificación basada en métricas"""
    print("\n=== Test: Clasificación por Métricas ===")

    classifier = ShotClassifier()

    # Test: Sin rostros, baja densidad = Plano general
    result = classifier._classify_from_metrics(0, 0, 0.03, [])
    assert result.shot_type == ShotType.EXTREME_WIDE
    print(f"✓ Sin rostros, baja densidad → {result.shot_type.value}")

    # Test: Un rostro grande = Close-up
    result = classifier._classify_from_metrics(1, 0.25, 0.1, [])
    assert result.shot_type == ShotType.CLOSEUP
    print(f"✓ Un rostro 25% coverage → {result.shot_type.value}")

    # Test: Un rostro muy grande = Extreme close-up
    result = classifier._classify_from_metrics(1, 0.40, 0.1, [])
    assert result.shot_type == ShotType.EXTREME_CLOSEUP
    print(f"✓ Un rostro 40% coverage → {result.shot_type.value}")

    # Test: Dos rostros = Two-shot
    result = classifier._classify_from_metrics(2, 0.1, 0.1, [])
    assert result.shot_type == ShotType.TWO_SHOT
    print(f"✓ Dos rostros → {result.shot_type.value}")

    # Test: Tres+ rostros = Group
    result = classifier._classify_from_metrics(3.5, 0.05, 0.1, [])
    assert result.shot_type == ShotType.GROUP
    print(f"✓ 3+ rostros → {result.shot_type.value}")

    # Test: Alta densidad de bordes, sin rostros = Detalle
    result = classifier._classify_from_metrics(0, 0, 0.2, [])
    assert result.shot_type == ShotType.DETAIL
    print(f"✓ Alta densidad, sin rostros → {result.shot_type.value}")


def test_display_names():
    """Test de funciones de nombre"""
    print("\n=== Test: Nombres de Display ===")

    assert get_shot_type_display_name(ShotType.CLOSEUP) == "Primer Plano"
    assert get_shot_type_short_name(ShotType.CLOSEUP) == "CU"
    print("✓ Nombres de display correctos")

    assert get_shot_type_display_name(ShotType.WIDE) == "Plano General"
    assert get_shot_type_short_name(ShotType.WIDE) == "WS"
    print("✓ Nombres cortos correctos")


def test_shot_classification_to_dict():
    """Test de serialización"""
    print("\n=== Test: Serialización ===")

    classification = ShotClassification(
        shot_type=ShotType.MEDIUM,
        confidence=0.85,
        face_count=1,
        primary_face_coverage=0.08,
        characteristics=['face_in_focus'],
        details={'test': True}
    )

    d = classification.to_dict()
    assert d['shot_type'] == 'PLANO_MEDIO'
    assert d['shot_type_key'] == 'medium'
    assert d['confidence'] == 0.85
    assert d['face_count'] == 1
    print("✓ to_dict() funciona correctamente")


def test_frame_classification():
    """Test de clasificación de frames reales"""
    print("\n=== Test: Clasificación de Frames ===")

    classifier = ShotClassifier()

    # Wide shot
    wide_frame = create_wide_shot_frame()
    gray = cv2.cvtColor(wide_frame, cv2.COLOR_BGR2GRAY)
    result = classifier.classify_frame(wide_frame, gray)
    print(f"✓ Wide shot frame → {result.shot_type.value} (conf: {result.confidence:.2f})")

    # Detail shot
    detail_frame = create_detail_shot_frame()
    gray = cv2.cvtColor(detail_frame, cv2.COLOR_BGR2GRAY)
    result = classifier.classify_frame(detail_frame, gray)
    print(f"✓ Detail shot frame → {result.shot_type.value} (conf: {result.confidence:.2f})")


def test_depth_of_field_analysis():
    """Test de análisis de profundidad de campo"""
    print("\n=== Test: Análisis de DOF ===")

    classifier = ShotClassifier()

    # Crear frame con centro nítido y bordes borrosos
    frame = np.zeros((270, 480, 3), dtype=np.uint8)

    # Centro con muchos detalles
    center = frame[67:202, 120:360]
    center[:] = np.random.randint(0, 255, center.shape, dtype=np.uint8)

    # Bordes borrosos (uniformes)
    frame[0:67, :] = 128
    frame[202:, :] = 128
    frame[:, 0:120] = 128
    frame[:, 360:] = 128

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dof_info = classifier._analyze_depth_of_field(gray)

    print(f"✓ Centro sharpness: {dof_info['center_sharpness']:.1f}")
    print(f"✓ Bordes sharpness: {dof_info['edge_sharpness']:.1f}")
    print(f"✓ Ratio: {dof_info['sharpness_ratio']:.2f}")
    print(f"✓ Shallow DOF: {dof_info['is_shallow_dof']}")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE SHOT CLASSIFIER")
    print("=" * 60)

    test_classifier_initialization()
    test_classify_from_metrics()
    test_display_names()
    test_shot_classification_to_dict()
    test_frame_classification()
    test_depth_of_field_analysis()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
