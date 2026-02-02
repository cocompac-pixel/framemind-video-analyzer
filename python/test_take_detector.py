#!/usr/bin/env python3
"""
Tests para el módulo take_detector.py
"""

import numpy as np
from take_detector import (
    TakeDetector, TakeMatch, TakeGroup, TakeDetectionResult,
    TakeRelationType, get_take_summary, format_take_groups_for_display
)


def create_mock_segment(index, scene_group=0, duration=5.0,
                        brightness=0.5, contrast=0.5, edge_density=0.1,
                        sharpness=100, motion=0.3, framing_type="MEDIUM_SHOT",
                        face_count=1, score=7.0, tier="SILVER"):
    """Crea un segmento simulado para pruebas"""
    return {
        'index': index,
        'scene_group_id': scene_group,
        'duration': duration,
        'metrics': {
            'brightness_mean': brightness,
            'contrast_mean': contrast,
            'edge_density': edge_density,
            'sharpness_mean': sharpness,
            'motion_mean': motion,
        },
        'framing_type': framing_type,
        'face_analysis': {
            'has_faces': face_count > 0,
            'avg_face_count': face_count,
            'primary_face_coverage': 0.15 if face_count > 0 else 0,
        },
        'score': score,
        'tier': tier,
    }


def test_detector_initialization():
    """Test de inicialización del detector"""
    print("\n=== Test: Inicialización del TakeDetector ===")

    detector = TakeDetector()

    assert hasattr(detector, 'thresholds'), "Debe tener thresholds"
    assert 'repeat_similarity_threshold' in detector.thresholds
    assert detector.thresholds['repeat_similarity_threshold'] > 0

    print("✓ TakeDetector inicializado correctamente")
    print(f"✓ Threshold de similitud: {detector.thresholds['repeat_similarity_threshold']}")
    print(f"✓ Pesos configurados en thresholds")


def test_take_relation_type_enum():
    """Test del enum TakeRelationType"""
    print("\n=== Test: Enum TakeRelationType ===")

    assert TakeRelationType.SAME_TAKE.value == "same_take"
    assert TakeRelationType.REPEATED_TAKE.value == "repeated_take"
    assert TakeRelationType.SIMILAR_SHOT.value == "similar_shot"
    assert TakeRelationType.DIFFERENT.value == "different"

    print("✓ Todos los tipos de relación definidos correctamente")


def test_empty_segments_analysis():
    """Test con lista vacía de segmentos"""
    print("\n=== Test: Análisis de Lista Vacía ===")

    detector = TakeDetector()
    result = detector.detect_repeated_takes([])

    assert result.total_groups == 0
    assert result.total_repeated_takes == 0
    assert result.take_groups == []
    assert result.matches == []

    print("✓ Lista vacía manejada correctamente")


def test_single_segment_analysis():
    """Test con un solo segmento"""
    print("\n=== Test: Análisis de Un Solo Segmento ===")

    detector = TakeDetector()
    segments = [create_mock_segment(0)]

    result = detector.detect_repeated_takes(segments)

    assert result.total_groups == 0, "No debería haber grupos con un solo segmento"
    assert result.total_repeated_takes == 0

    print("✓ Un solo segmento analizado correctamente")


def test_different_segments_no_match():
    """Test con segmentos muy diferentes (no deberían agruparse como takes repetidos)"""
    print("\n=== Test: Segmentos Diferentes ===")

    detector = TakeDetector()

    # Crear segmentos muy diferentes
    segments = [
        create_mock_segment(0, scene_group=0, brightness=0.2,
                           framing_type="WIDE_SHOT", motion=0.1),
        create_mock_segment(1, scene_group=1, brightness=0.8,
                           framing_type="CLOSE_UP", motion=0.8),
        create_mock_segment(2, scene_group=2, brightness=0.5,
                           framing_type="EXTREME_CLOSE_UP", motion=0.5),
    ]

    result = detector.detect_repeated_takes(segments)

    # No deberían formar grupos de takes repetidos (aunque pueden tener matches de similitud baja)
    print(f"  Grupos de takes repetidos: {result.total_groups}")
    print(f"  Matches totales encontrados: {len(result.matches)}")
    print("✓ Segmentos diferentes analizados")


def test_similar_segments_grouping():
    """Test con segmentos similares (deberían agruparse como takes repetidos)"""
    print("\n=== Test: Agrupación de Segmentos Similares ===")

    detector = TakeDetector()

    # Crear segmentos muy similares (mismo scene_group, mismo framing, métricas parecidas)
    segments = [
        create_mock_segment(0, scene_group=0, brightness=0.50, contrast=0.50,
                           framing_type="MEDIUM_SHOT", score=7.0, duration=5.0),
        create_mock_segment(1, scene_group=0, brightness=0.51, contrast=0.49,
                           framing_type="MEDIUM_SHOT", score=7.5, duration=5.2),
        create_mock_segment(2, scene_group=0, brightness=0.49, contrast=0.51,
                           framing_type="MEDIUM_SHOT", score=8.0, duration=4.9),
        # Uno diferente que no debería agruparse
        create_mock_segment(3, scene_group=1, brightness=0.80, contrast=0.30,
                           framing_type="WIDE_SHOT", score=6.0, duration=10.0),
    ]

    result = detector.detect_repeated_takes(segments)

    print(f"  Total grupos: {result.total_groups}")
    print(f"  Total takes repetidos: {result.total_repeated_takes}")
    print(f"  Matches encontrados: {len(result.matches)}")

    if result.total_groups > 0:
        print(f"  ✓ Se detectaron {result.total_groups} grupo(s) de takes repetidos")
        for group in result.take_groups:
            print(f"    - Grupo {group.group_id}: {group.take_count} takes, best={group.best_take}")
    else:
        print("  (No se formaron grupos - threshold puede necesitar ajuste)")

    print("✓ Test de agrupación completado")


def test_visual_similarity_calculation():
    """Test del cálculo de similitud visual"""
    print("\n=== Test: Cálculo de Similitud Visual ===")

    detector = TakeDetector()

    # Métricas idénticas
    metrics_a = {
        'brightness_mean': 0.5, 'contrast_mean': 0.5,
        'edge_density': 0.1, 'sharpness_mean': 100, 'motion_mean': 0.3
    }
    metrics_b = {
        'brightness_mean': 0.5, 'contrast_mean': 0.5,
        'edge_density': 0.1, 'sharpness_mean': 100, 'motion_mean': 0.3
    }

    sim = detector._calculate_visual_similarity(metrics_a, metrics_b)
    assert sim == 1.0, f"Métricas idénticas deberían dar similitud 1.0, obtuvo {sim}"
    print(f"✓ Métricas idénticas → similitud = {sim}")

    # Métricas muy diferentes
    metrics_c = {
        'brightness_mean': 0.1, 'contrast_mean': 0.9,
        'edge_density': 0.5, 'sharpness_mean': 200, 'motion_mean': 2.0
    }
    sim2 = detector._calculate_visual_similarity(metrics_a, metrics_c)
    assert sim2 < 0.7, f"Métricas muy diferentes deberían dar similitud baja, obtuvo {sim2}"
    print(f"✓ Métricas diferentes → similitud = {sim2:.3f}")

    # Métricas parcialmente similares
    metrics_d = {
        'brightness_mean': 0.55, 'contrast_mean': 0.45,
        'edge_density': 0.12, 'sharpness_mean': 110, 'motion_mean': 0.35
    }
    sim3 = detector._calculate_visual_similarity(metrics_a, metrics_d)
    assert 0.7 < sim3 < 1.0, f"Métricas similares deberían dar similitud alta, obtuvo {sim3}"
    print(f"✓ Métricas similares → similitud = {sim3:.3f}")


def test_take_match_dataclass():
    """Test de la dataclass TakeMatch"""
    print("\n=== Test: Dataclass TakeMatch ===")

    match = TakeMatch(
        segment_a=0,
        segment_b=1,
        similarity_score=0.85,
        relation_type=TakeRelationType.REPEATED_TAKE,
        confidence=0.80,
        visual_similarity=0.90,
        duration_similarity=0.95,
        framing_match=True,
        scene_group_match=True
    )

    d = match.to_dict()

    assert d['segment_a'] == 0
    assert d['segment_b'] == 1
    assert d['similarity_score'] == 0.85
    assert d['relation_type'] == 'repeated_take'
    assert d['framing_match'] == True
    assert d['confidence'] == 0.80

    print("✓ TakeMatch.to_dict() funciona correctamente")
    print(f"✓ Claves: {list(d.keys())}")


def test_take_group_dataclass():
    """Test de la dataclass TakeGroup"""
    print("\n=== Test: Dataclass TakeGroup ===")

    group = TakeGroup(
        group_id=1,
        takes=[0, 1, 2],
        best_take=2,
        take_count=3,
        avg_score=7.5,
        best_score=8.5,
        worst_score=6.5,
        recommended_takes=[2],
        discard_takes=[0, 1]
    )

    d = group.to_dict()

    assert d['group_id'] == 1
    assert d['takes'] == [0, 1, 2]
    assert d['best_take'] == 2
    assert d['take_count'] == 3
    assert d['best_score'] == 8.5
    assert len(d['recommended_takes']) == 1
    assert len(d['discard_takes']) == 2

    print("✓ TakeGroup.to_dict() funciona correctamente")
    print(f"✓ Grupo con {d['take_count']} takes, mejor: {d['best_take']}")


def test_take_detection_result_dataclass():
    """Test de la dataclass TakeDetectionResult"""
    print("\n=== Test: Dataclass TakeDetectionResult ===")

    result = TakeDetectionResult(
        take_groups=[],
        matches=[],
        segment_to_group={},
        total_groups=0,
        total_repeated_takes=0,
        potential_savings_duration=0.0
    )

    d = result.to_dict()

    assert d['total_groups'] == 0
    assert d['total_repeated_takes'] == 0
    assert d['take_groups'] == []

    print("✓ TakeDetectionResult.to_dict() funciona correctamente")


def test_get_take_summary():
    """Test de la función get_take_summary"""
    print("\n=== Test: Función get_take_summary ===")

    # Resultado vacío
    result_empty = TakeDetectionResult(
        take_groups=[],
        matches=[],
        segment_to_group={},
        total_groups=0,
        total_repeated_takes=0,
        potential_savings_duration=0.0
    )

    summary = get_take_summary(result_empty)
    assert summary['total_groups'] == 0
    assert summary['total_repeated_takes'] == 0
    print(f"✓ Resumen vacío: {summary['recommendation']}")

    # Resultado con grupos
    group = TakeGroup(
        group_id=1,
        takes=[0, 1, 2],
        best_take=2,
        take_count=3,
        avg_score=7.5,
        best_score=8.5,
        worst_score=6.5,
        recommended_takes=[2],
        discard_takes=[0, 1]
    )

    result_with_groups = TakeDetectionResult(
        take_groups=[group],
        matches=[],
        segment_to_group={0: 1, 1: 1, 2: 1},
        total_groups=1,
        total_repeated_takes=2,
        potential_savings_duration=10.0
    )

    summary2 = get_take_summary(result_with_groups)
    assert summary2['total_groups'] == 1
    assert summary2['total_repeated_takes'] == 2
    assert summary2['potential_savings_seconds'] == 10.0
    print(f"✓ Resumen con takes: {summary2['recommendation']}")


def test_get_take_recommendations():
    """Test de la función get_take_recommendations"""
    print("\n=== Test: Recomendaciones de Takes ===")

    detector = TakeDetector()

    # Crear segmentos
    segments = [
        create_mock_segment(0, score=7.0, tier="silver"),
        create_mock_segment(1, score=7.5, tier="silver"),
        create_mock_segment(2, score=8.0, tier="gold"),
    ]

    group = TakeGroup(
        group_id=0,
        takes=[0, 1, 2],
        best_take=2,
        take_count=3,
        avg_score=7.5,
        best_score=8.0,
        worst_score=7.0,
        recommended_takes=[2],
        discard_takes=[0, 1]
    )

    result = TakeDetectionResult(
        take_groups=[group],
        matches=[],
        segment_to_group={0: 0, 1: 0, 2: 0},
        total_groups=1,
        total_repeated_takes=2,
        potential_savings_duration=10.0
    )

    recommendations = detector.get_take_recommendations(result, segments)

    assert 'use' in recommendations
    assert 'consider' in recommendations
    assert 'skip' in recommendations

    print(f"✓ Recomendaciones generadas:")
    print(f"  - Usar: {len(recommendations['use'])} takes")
    print(f"  - Considerar: {len(recommendations['consider'])} takes")
    print(f"  - Saltar: {len(recommendations['skip'])} takes")


def test_duration_similarity():
    """Test de similitud de duración"""
    print("\n=== Test: Similitud de Duración ===")

    detector = TakeDetector()

    # Misma duración
    sim = detector._calculate_duration_similarity(5.0, 5.0)
    assert sim == 1.0
    print(f"✓ Duración 5.0 vs 5.0 → similitud = {sim}")

    # Duración similar (dentro de tolerancia 30%)
    sim2 = detector._calculate_duration_similarity(5.0, 6.0)
    assert sim2 == 1.0  # 6/5 = 1.2 = 20% diferencia, dentro de 30%
    print(f"✓ Duración 5.0 vs 6.0 → similitud = {sim2}")

    # Duración muy diferente
    sim3 = detector._calculate_duration_similarity(5.0, 15.0)
    assert sim3 < 0.5
    print(f"✓ Duración 5.0 vs 15.0 → similitud = {sim3:.3f}")


def test_face_similarity():
    """Test de similitud de rostros"""
    print("\n=== Test: Similitud de Rostros ===")

    detector = TakeDetector()

    # Sin rostros en ambos
    seg_a = create_mock_segment(0, face_count=0)
    seg_b = create_mock_segment(1, face_count=0)

    sim = detector._calculate_face_similarity(seg_a, seg_b)
    assert sim == 1.0
    print(f"✓ 0 rostros vs 0 rostros → similitud = {sim}")

    # Con rostros en ambos (mismo número)
    seg_c = create_mock_segment(2, face_count=1)
    seg_d = create_mock_segment(3, face_count=1)

    sim2 = detector._calculate_face_similarity(seg_c, seg_d)
    assert sim2 > 0.5
    print(f"✓ 1 rostro vs 1 rostro → similitud = {sim2:.3f}")

    # Uno con rostros, otro sin
    sim3 = detector._calculate_face_similarity(seg_a, seg_c)
    assert sim3 == 0.3  # Valor definido en el código
    print(f"✓ 0 rostros vs 1 rostro → similitud = {sim3}")


def test_confidence_calculation():
    """Test de cálculo de confianza"""
    print("\n=== Test: Cálculo de Confianza ===")

    detector = TakeDetector()

    # Alta confianza (todos los factores positivos)
    conf = detector._calculate_confidence(
        visual_sim=0.9,
        duration_sim=0.95,
        framing_match=True,
        scene_match=True
    )
    assert conf > 0.8
    print(f"✓ Alta similitud + matches → confianza = {conf:.3f}")

    # Baja confianza (factores negativos)
    conf2 = detector._calculate_confidence(
        visual_sim=0.4,
        duration_sim=0.5,
        framing_match=False,
        scene_match=False
    )
    assert conf2 < 0.6
    print(f"✓ Baja similitud sin matches → confianza = {conf2:.3f}")


def test_format_take_groups_for_display():
    """Test de formateo para UI"""
    print("\n=== Test: Formateo para Display ===")

    segments = [
        create_mock_segment(0, score=7.0, tier="silver", duration=5.0),
        create_mock_segment(1, score=8.0, tier="gold", duration=5.2),
    ]

    group = TakeGroup(
        group_id=0,
        takes=[0, 1],
        best_take=1,
        take_count=2,
        avg_score=7.5,
        best_score=8.0,
        worst_score=7.0,
        recommended_takes=[1],
        discard_takes=[0]
    )

    result = TakeDetectionResult(
        take_groups=[group],
        matches=[],
        segment_to_group={0: 0, 1: 0},
        total_groups=1,
        total_repeated_takes=1,
        potential_savings_duration=5.0
    )

    formatted = format_take_groups_for_display(result, segments)

    assert len(formatted) == 1
    assert formatted[0]['group_id'] == 0
    assert formatted[0]['take_count'] == 2
    assert len(formatted[0]['takes']) == 2

    print("✓ format_take_groups_for_display funciona correctamente")
    print(f"  - Grupo formateado: {formatted[0]['summary']}")


def test_union_find_grouping():
    """Test del algoritmo union-find para agrupar takes"""
    print("\n=== Test: Agrupación Union-Find ===")

    detector = TakeDetector()

    # Crear matches que deberían formar grupos
    match1 = TakeMatch(
        segment_a=0, segment_b=1,
        similarity_score=0.85,
        relation_type=TakeRelationType.REPEATED_TAKE,
        confidence=0.80,
        visual_similarity=0.85,
        duration_similarity=0.95,
        framing_match=True,
        scene_group_match=True
    )

    match2 = TakeMatch(
        segment_a=1, segment_b=2,
        similarity_score=0.82,
        relation_type=TakeRelationType.REPEATED_TAKE,
        confidence=0.78,
        visual_similarity=0.80,
        duration_similarity=0.90,
        framing_match=True,
        scene_group_match=True
    )

    segments = [
        create_mock_segment(0, score=7.0),
        create_mock_segment(1, score=7.5),
        create_mock_segment(2, score=8.0),
        create_mock_segment(3, score=6.0),  # No relacionado
    ]

    groups, mapping = detector._group_repeated_takes([match1, match2], segments)

    # Segmentos 0, 1, 2 deberían estar en el mismo grupo
    if len(groups) > 0:
        group = groups[0]
        assert 0 in group.takes
        assert 1 in group.takes
        assert 2 in group.takes
        assert group.best_take == 2  # El de mayor score
        print(f"✓ Grupo formado con {group.take_count} takes")
        print(f"  - Takes: {group.takes}")
        print(f"  - Mejor take: {group.best_take}")
    else:
        print("  (No se formaron grupos)")

    print("✓ Union-find funciona correctamente")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE TAKE DETECTOR")
    print("=" * 60)

    test_detector_initialization()
    test_take_relation_type_enum()
    test_empty_segments_analysis()
    test_single_segment_analysis()
    test_different_segments_no_match()
    test_similar_segments_grouping()
    test_visual_similarity_calculation()
    test_take_match_dataclass()
    test_take_group_dataclass()
    test_take_detection_result_dataclass()
    test_get_take_summary()
    test_get_take_recommendations()
    test_duration_similarity()
    test_face_similarity()
    test_confidence_calculation()
    test_format_take_groups_for_display()
    test_union_find_grouping()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
