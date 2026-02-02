#!/usr/bin/env python3
"""
Tests para el módulo face_analyzer.py
"""

import numpy as np
import cv2
from face_analyzer import (
    FaceAnalyzer, FaceAnalysisResult, DetailedFaceInfo,
    EyeState, FaceFramingIssue,
    get_face_issue_severity, summarize_face_analysis
)


def create_frame_with_simulated_face(width=480, height=270, face_y_ratio=0.15,
                                     face_size_ratio=0.2, add_eyes=True):
    """
    Crea un frame con un 'rostro' simulado usando formas básicas.
    El detector Haar no lo detectará como rostro real, pero sirve para
    probar la lógica de análisis una vez detectado.
    """
    frame = np.random.randint(100, 150, (height, width, 3), dtype=np.uint8)

    # Calcular tamaño del rostro
    face_h = int(height * face_size_ratio * 1.3)
    face_w = int(width * face_size_ratio)

    # Posición (centrado horizontalmente, en tercio superior)
    x = (width - face_w) // 2
    y = int(height * face_y_ratio)

    # Dibujar área de rostro (tono piel)
    frame[y:y+face_h, x:x+face_w] = [180, 150, 140]  # BGR - tono piel

    if add_eyes:
        # Simular ojos (círculos oscuros en el tercio superior del rostro)
        eye_y = y + face_h // 4
        eye_radius = face_w // 8
        left_eye_x = x + face_w // 3
        right_eye_x = x + 2 * face_w // 3

        cv2.circle(frame, (left_eye_x, eye_y), eye_radius, (50, 50, 50), -1)
        cv2.circle(frame, (right_eye_x, eye_y), eye_radius, (50, 50, 50), -1)

    return frame, (x, y, face_w, face_h)


def create_uniform_frame(width=480, height=270, color=(128, 128, 128)):
    """Crea un frame de color uniforme (sin rostros)"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def test_analyzer_initialization():
    """Test de inicialización del analizador"""
    print("\n=== Test: Inicialización del FaceAnalyzer ===")

    analyzer = FaceAnalyzer()
    assert analyzer.cascades_loaded, "Haar cascades no cargados"
    print("✓ FaceAnalyzer inicializado correctamente")
    print(f"✓ Cascades loaded: {analyzer.cascades_loaded}")
    print(f"✓ Thresholds configurados: {len(analyzer.thresholds)} umbrales")


def test_empty_frame_analysis():
    """Test de análisis de frame sin rostros"""
    print("\n=== Test: Análisis de Frame Sin Rostros ===")

    analyzer = FaceAnalyzer()

    # Frame uniforme sin rostros
    frame = create_uniform_frame()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    result = analyzer.analyze_frame(frame, gray)

    assert result.face_count == 0, "Debería detectar 0 rostros"
    assert result.faces == [], "Lista de rostros debería estar vacía"
    assert not result.any_in_focus, "any_in_focus debería ser False"
    assert not result.any_eyes_closed, "any_eyes_closed debería ser False"
    assert result.primary_face is None, "primary_face debería ser None"

    print("✓ Frame vacío analizado correctamente")
    print(f"✓ Resultado: {result.face_count} rostros detectados")


def test_quick_face_metrics():
    """Test de métricas rápidas (versión optimizada)"""
    print("\n=== Test: Métricas Rápidas de Rostros ===")

    analyzer = FaceAnalyzer()

    # Frame sin rostros
    frame = create_uniform_frame()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    metrics = analyzer.get_quick_face_metrics(frame, gray)

    assert 'face_count' in metrics, "Debería tener face_count"
    assert 'primary_face_coverage' in metrics, "Debería tener primary_face_coverage"
    assert 'faces_in_focus' in metrics, "Debería tener faces_in_focus"
    assert 'any_eyes_closed' in metrics, "Debería tener any_eyes_closed"
    assert 'framing_issues_count' in metrics, "Debería tener framing_issues_count"

    assert metrics['face_count'] == 0, "Debería detectar 0 rostros"
    print("✓ get_quick_face_metrics funciona correctamente")
    print(f"✓ Claves en métricas: {list(metrics.keys())}")


def test_eye_state_enum():
    """Test del enum EyeState"""
    print("\n=== Test: Enum EyeState ===")

    assert EyeState.OPEN.value == "open"
    assert EyeState.CLOSED.value == "closed"
    assert EyeState.PARTIALLY_CLOSED.value == "partially_closed"
    assert EyeState.UNKNOWN.value == "unknown"

    print("✓ Todos los estados de ojos definidos correctamente")


def test_framing_issue_enum():
    """Test del enum FaceFramingIssue"""
    print("\n=== Test: Enum FaceFramingIssue ===")

    issues = [
        FaceFramingIssue.NONE,
        FaceFramingIssue.NO_HEADROOM,
        FaceFramingIssue.TOO_MUCH_HEADROOM,
        FaceFramingIssue.FACE_CUT_TOP,
        FaceFramingIssue.FACE_CUT_BOTTOM,
        FaceFramingIssue.FACE_CUT_LEFT,
        FaceFramingIssue.FACE_CUT_RIGHT,
        FaceFramingIssue.OFF_CENTER,
    ]

    for issue in issues:
        assert issue.value is not None
        print(f"  ✓ {issue.name} = '{issue.value}'")

    print("✓ Todos los problemas de encuadre definidos")


def test_get_face_issue_severity():
    """Test de función de severidad de problemas"""
    print("\n=== Test: Severidad de Problemas ===")

    # Sin problemas
    severity = get_face_issue_severity([])
    assert severity == "none"
    print("✓ Sin problemas → 'none'")

    # Problema severo
    severity = get_face_issue_severity([FaceFramingIssue.FACE_CUT_TOP])
    assert severity == "severe"
    print("✓ Rostro cortado arriba → 'severe'")

    severity = get_face_issue_severity([FaceFramingIssue.NO_HEADROOM])
    assert severity == "severe"
    print("✓ Sin headroom → 'severe'")

    # Problema moderado
    severity = get_face_issue_severity([FaceFramingIssue.FACE_CUT_LEFT])
    assert severity == "moderate"
    print("✓ Rostro cortado lado → 'moderate'")

    severity = get_face_issue_severity([FaceFramingIssue.TOO_MUCH_HEADROOM])
    assert severity == "moderate"
    print("✓ Demasiado headroom → 'moderate'")

    # Problema menor
    severity = get_face_issue_severity([FaceFramingIssue.OFF_CENTER])
    assert severity == "minor"
    print("✓ Descentrado → 'minor'")


def test_detailed_face_info_to_dict():
    """Test de serialización de DetailedFaceInfo"""
    print("\n=== Test: Serialización DetailedFaceInfo ===")

    face_info = DetailedFaceInfo(
        bbox=(100, 50, 80, 100),
        center=(140, 100),
        coverage=0.15,
        position_h="center",
        position_v="top",
        normalized_x=0.5,
        normalized_y=0.37,
        in_focus=True,
        sharpness=150.5,
        focus_quality="good",
        eyes_detected=2,
        left_eye=(110, 60, 20, 15),
        right_eye=(150, 60, 20, 15),
        eye_state=EyeState.OPEN,
        both_eyes_visible=True,
        headroom_ratio=0.12,
        headroom_ok=True,
        chin_room_ratio=0.45,
        is_partial=False,
        framing_issues=[],
        is_frontal=True,
        is_profile=False
    )

    d = face_info.to_dict()

    assert d['bbox'] == (100, 50, 80, 100)
    assert d['coverage'] == 0.15
    assert d['in_focus'] == True
    assert d['eye_state'] == 'open'
    assert d['framing_issues'] == []

    print("✓ to_dict() funciona correctamente")
    print(f"✓ Claves en dict: {list(d.keys())}")


def test_face_analysis_result_to_dict():
    """Test de serialización de FaceAnalysisResult"""
    print("\n=== Test: Serialización FaceAnalysisResult ===")

    # Crear resultado vacío
    result = FaceAnalysisResult(
        face_count=0,
        faces=[],
        any_in_focus=False,
        all_in_focus=False,
        any_eyes_closed=False,
        any_framing_issues=False,
        best_face_sharpness=0,
        worst_face_sharpness=0,
        primary_face=None,
        issues_summary=[]
    )

    d = result.to_dict()

    assert d['face_count'] == 0
    assert d['faces'] == []
    assert d['primary_face'] is None

    print("✓ to_dict() para resultado vacío funciona")


def test_summarize_face_analysis():
    """Test de función de resumen"""
    print("\n=== Test: Resumen de Análisis ===")

    # Resultado sin rostros
    result_empty = FaceAnalysisResult(
        face_count=0,
        faces=[],
        any_in_focus=False,
        all_in_focus=False,
        any_eyes_closed=False,
        any_framing_issues=False,
        best_face_sharpness=0,
        worst_face_sharpness=0,
        primary_face=None,
        issues_summary=[]
    )

    summary = summarize_face_analysis(result_empty)
    assert "Sin rostros" in summary
    print(f"✓ Sin rostros: '{summary}'")

    # Resultado con rostros (simulado)
    face = DetailedFaceInfo(
        bbox=(100, 50, 80, 100),
        center=(140, 100),
        coverage=0.15,
        position_h="center",
        position_v="top",
        normalized_x=0.5,
        normalized_y=0.37,
        in_focus=True,
        sharpness=150.5,
        focus_quality="good",
        eyes_detected=2,
        left_eye=None,
        right_eye=None,
        eye_state=EyeState.OPEN,
        both_eyes_visible=True,
        headroom_ratio=0.12,
        headroom_ok=True,
        chin_room_ratio=0.45,
        is_partial=False,
        framing_issues=[],
        is_frontal=True,
        is_profile=False
    )

    result_with_face = FaceAnalysisResult(
        face_count=1,
        faces=[face],
        any_in_focus=True,
        all_in_focus=True,
        any_eyes_closed=False,
        any_framing_issues=False,
        best_face_sharpness=150.5,
        worst_face_sharpness=150.5,
        primary_face=face,
        issues_summary=[]
    )

    summary = summarize_face_analysis(result_with_face)
    assert "1 rostro" in summary
    assert "foco" in summary.lower()
    print(f"✓ Con rostro: '{summary}'")


def test_position_categorization():
    """Test de categorización de posiciones"""
    print("\n=== Test: Categorización de Posiciones ===")

    analyzer = FaceAnalyzer()

    # Horizontal
    assert analyzer._categorize_horizontal_position(0.1) == "left"
    assert analyzer._categorize_horizontal_position(0.5) == "center"
    assert analyzer._categorize_horizontal_position(0.9) == "right"
    print("✓ Posiciones horizontales categorizadas correctamente")

    # Vertical
    assert analyzer._categorize_vertical_position(0.1) == "top"
    assert analyzer._categorize_vertical_position(0.5) == "middle"
    assert analyzer._categorize_vertical_position(0.9) == "bottom"
    print("✓ Posiciones verticales categorizadas correctamente")


def test_focus_evaluation():
    """Test de evaluación de foco"""
    print("\n=== Test: Evaluación de Foco ===")

    analyzer = FaceAnalyzer()

    # Excelente
    in_focus, quality = analyzer._evaluate_focus(200)
    assert in_focus == True
    assert quality == "excellent"
    print(f"✓ Sharpness 200 → in_focus={in_focus}, quality='{quality}'")

    # Bueno
    in_focus, quality = analyzer._evaluate_focus(120)
    assert in_focus == True
    assert quality == "good"
    print(f"✓ Sharpness 120 → in_focus={in_focus}, quality='{quality}'")

    # Aceptable
    in_focus, quality = analyzer._evaluate_focus(70)
    assert in_focus == True
    assert quality == "acceptable"
    print(f"✓ Sharpness 70 → in_focus={in_focus}, quality='{quality}'")

    # Suave (soft)
    in_focus, quality = analyzer._evaluate_focus(45)
    assert in_focus == False
    assert quality == "soft"
    print(f"✓ Sharpness 45 → in_focus={in_focus}, quality='{quality}'")

    # Borroso
    in_focus, quality = analyzer._evaluate_focus(20)
    assert in_focus == False
    assert quality == "blurry"
    print(f"✓ Sharpness 20 → in_focus={in_focus}, quality='{quality}'")


def test_framing_issues_detection():
    """Test de detección de problemas de encuadre"""
    print("\n=== Test: Detección de Problemas de Encuadre ===")

    analyzer = FaceAnalyzer()

    # Sin problemas (rostro bien centrado con buen headroom)
    issues = analyzer._detect_framing_issues(
        x=200, y=50, fw=80, fh=100,
        w=480, h=270,
        headroom_ratio=0.12,  # Buen headroom
        chin_room_ratio=0.45,
        normalized_x=0.5  # Centrado
    )
    assert len(issues) == 0, f"No debería haber problemas, pero hay: {issues}"
    print("✓ Rostro bien encuadrado → sin problemas")

    # Rostro cortado arriba
    issues = analyzer._detect_framing_issues(
        x=200, y=2, fw=80, fh=100,  # y muy pequeño
        w=480, h=270,
        headroom_ratio=0.01,
        chin_room_ratio=0.60,
        normalized_x=0.5
    )
    assert FaceFramingIssue.FACE_CUT_TOP in issues
    print("✓ Rostro cortado arriba detectado")

    # Sin headroom
    issues = analyzer._detect_framing_issues(
        x=200, y=5, fw=80, fh=100,
        w=480, h=270,
        headroom_ratio=0.02,  # Muy poco headroom
        chin_room_ratio=0.60,
        normalized_x=0.5
    )
    assert FaceFramingIssue.NO_HEADROOM in issues
    print("✓ Sin headroom detectado")

    # Demasiado headroom
    issues = analyzer._detect_framing_issues(
        x=200, y=100, fw=80, fh=100,
        w=480, h=270,
        headroom_ratio=0.35,  # Mucho headroom
        chin_room_ratio=0.25,
        normalized_x=0.5
    )
    assert FaceFramingIssue.TOO_MUCH_HEADROOM in issues
    print("✓ Demasiado headroom detectado")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE FACE ANALYZER")
    print("=" * 60)

    test_analyzer_initialization()
    test_empty_frame_analysis()
    test_quick_face_metrics()
    test_eye_state_enum()
    test_framing_issue_enum()
    test_get_face_issue_severity()
    test_detailed_face_info_to_dict()
    test_face_analysis_result_to_dict()
    test_summarize_face_analysis()
    test_position_categorization()
    test_focus_evaluation()
    test_framing_issues_detection()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
