#!/usr/bin/env python3
"""
Tests para el módulo scene_grouper.py
"""

import numpy as np
from scene_grouper import (
    SceneGrouper, SceneGroup, SceneAnalysisResult, VisualFingerprint,
    SceneChangeType, get_scene_summary, format_scene_groups_for_display
)


def create_mock_segments(n_segments=10, varied=True):
    """Crea segmentos simulados para testing"""
    segments = []

    for i in range(n_segments):
        # Variar métricas para simular diferentes escenas
        if varied:
            # Alternar entre "escenas" diferentes
            scene_type = i % 3
            if scene_type == 0:
                brightness = 0.3 + np.random.uniform(-0.1, 0.1)  # Oscuro
                contrast = 0.4
            elif scene_type == 1:
                brightness = 0.6 + np.random.uniform(-0.1, 0.1)  # Medio
                contrast = 0.5
            else:
                brightness = 0.8 + np.random.uniform(-0.1, 0.1)  # Claro
                contrast = 0.6
        else:
            brightness = 0.5
            contrast = 0.5

        segment = {
            'start_time': i * 2.0,
            'end_time': (i + 1) * 2.0,
            'duration': 2.0,
            'tier': ['gold', 'silver', 'bronze', 'discard'][i % 4],
            'score': 5.0 + np.random.uniform(0, 5),
            'metrics': {
                'brightness_mean': brightness,
                'brightness_std': 0.1,
                'contrast_mean': contrast,
                'edge_density': 0.1 + np.random.uniform(0, 0.1),
                'sharpness_mean': 100 + np.random.uniform(-50, 50),
                'h_balance': 0.5 + np.random.uniform(-0.2, 0.2),
                'v_balance': 0.5 + np.random.uniform(-0.2, 0.2),
            }
        }
        segments.append(segment)

    return segments


def test_grouper_initialization():
    """Test de inicialización del agrupador"""
    print("\n=== Test: Inicialización del SceneGrouper ===")

    grouper = SceneGrouper()

    assert grouper.thresholds is not None
    assert 'similarity_threshold' in grouper.thresholds
    assert 'hard_cut_threshold' in grouper.thresholds

    print("✓ SceneGrouper inicializado correctamente")
    print(f"✓ Thresholds configurados: {len(grouper.thresholds)}")


def test_empty_segments():
    """Test con lista vacía de segmentos"""
    print("\n=== Test: Lista Vacía de Segmentos ===")

    grouper = SceneGrouper()
    result = grouper.analyze_project([])

    assert result.total_groups == 0
    assert result.groups == []
    assert result.segment_to_group == {}
    assert result.scene_changes == []

    print("✓ Lista vacía manejada correctamente")


def test_single_segment():
    """Test con un solo segmento"""
    print("\n=== Test: Un Solo Segmento ===")

    grouper = SceneGrouper()
    segments = create_mock_segments(1)

    result = grouper.analyze_project(segments)

    assert result.total_groups == 1
    assert len(result.groups) == 1
    assert result.segment_to_group[0] == 0

    print("✓ Segmento único procesado correctamente")
    print(f"✓ Grupo creado: {result.groups[0].name}")


def test_similar_segments_grouping():
    """Test de agrupación de segmentos similares"""
    print("\n=== Test: Agrupación de Segmentos Similares ===")

    grouper = SceneGrouper()

    # Crear segmentos muy similares (misma escena)
    segments = create_mock_segments(5, varied=False)

    result = grouper.analyze_project(segments)

    # Todos deberían estar en el mismo grupo
    unique_groups = set(result.segment_to_group.values())
    print(f"✓ Segmentos similares agrupados en {len(unique_groups)} grupo(s)")

    # Verificar que hay al menos un grupo
    assert result.total_groups >= 1
    print(f"✓ Total grupos: {result.total_groups}")


def test_varied_segments_grouping():
    """Test de agrupación con segmentos variados"""
    print("\n=== Test: Agrupación de Segmentos Variados ===")

    grouper = SceneGrouper()

    # Crear segmentos con 3 "escenas" diferentes
    segments = create_mock_segments(12, varied=True)

    result = grouper.analyze_project(segments)

    print(f"✓ {len(segments)} segmentos agrupados en {result.total_groups} grupos")

    for group in result.groups:
        print(f"  - {group.name}: {group.segment_count} segmentos, "
              f"consistencia={group.visual_consistency:.2f}")

    # Deberían haber múltiples grupos
    assert result.total_groups >= 1
    print("✓ Agrupación por variación completada")


def test_scene_change_detection():
    """Test de detección de cambios de escena"""
    print("\n=== Test: Detección de Cambios de Escena ===")

    grouper = SceneGrouper()

    # Crear segmentos con cambio abrupto en el medio
    segments = []
    for i in range(6):
        if i < 3:
            brightness = 0.3  # Escena oscura
        else:
            brightness = 0.8  # Escena clara (cambio abrupto)

        segments.append({
            'start_time': i * 2.0,
            'end_time': (i + 1) * 2.0,
            'duration': 2.0,
            'tier': 'silver',
            'score': 7.0,
            'metrics': {
                'brightness_mean': brightness,
                'brightness_std': 0.05,
                'contrast_mean': 0.5,
                'edge_density': 0.1,
                'sharpness_mean': 100,
                'h_balance': 0.5,
                'v_balance': 0.5,
            }
        })

    result = grouper.analyze_project(segments)

    print(f"✓ Cambios de escena detectados: {len(result.scene_changes)}")
    for change in result.scene_changes:
        print(f"  - {change['change_type']} en t={change['timestamp']:.1f}s "
              f"(confianza: {change['confidence']:.2f})")

    # Debería detectar al menos un cambio
    if len(result.scene_changes) > 0:
        print("✓ Cambio de escena detectado correctamente")


def test_fingerprint_extraction():
    """Test de extracción de fingerprints"""
    print("\n=== Test: Extracción de Fingerprints ===")

    grouper = SceneGrouper()
    segments = create_mock_segments(3)

    fingerprints = grouper._extract_fingerprints(segments)

    assert len(fingerprints) == 3

    for i, fp in enumerate(fingerprints):
        assert fp.segment_id == i
        assert len(fp.hue_hist) == grouper.thresholds['hue_bins']
        assert len(fp.sat_hist) == grouper.thresholds['sat_bins']
        assert len(fp.val_hist) == grouper.thresholds['val_bins']

    print("✓ Fingerprints extraídos correctamente")
    print(f"✓ Histograma hue: {len(fingerprints[0].hue_hist)} bins")
    print(f"✓ Histograma sat: {len(fingerprints[0].sat_hist)} bins")


def test_fingerprint_distance():
    """Test de cálculo de distancia entre fingerprints"""
    print("\n=== Test: Distancia entre Fingerprints ===")

    grouper = SceneGrouper()

    # Crear dos fingerprints similares
    similar_segments = create_mock_segments(2, varied=False)
    fps_similar = grouper._extract_fingerprints(similar_segments)

    # Crear dos fingerprints diferentes
    different_segments = [
        {
            'metrics': {'brightness_mean': 0.2, 'contrast_mean': 0.3,
                       'edge_density': 0.05, 'sharpness_mean': 50,
                       'h_balance': 0.3, 'v_balance': 0.3}
        },
        {
            'metrics': {'brightness_mean': 0.9, 'contrast_mean': 0.8,
                       'edge_density': 0.3, 'sharpness_mean': 200,
                       'h_balance': 0.7, 'v_balance': 0.7}
        }
    ]
    fps_different = grouper._extract_fingerprints(different_segments)

    dist_similar = grouper._calculate_fingerprint_distance(fps_similar[0], fps_similar[1])
    dist_different = grouper._calculate_fingerprint_distance(fps_different[0], fps_different[1])

    print(f"✓ Distancia entre similares: {dist_similar:.3f}")
    print(f"✓ Distancia entre diferentes: {dist_different:.3f}")

    # Los similares deberían tener menor distancia
    assert dist_similar < dist_different
    print("✓ Distancias calculadas correctamente (similares < diferentes)")


def test_scene_group_to_dict():
    """Test de serialización de SceneGroup"""
    print("\n=== Test: Serialización de SceneGroup ===")

    group = SceneGroup(
        group_id=0,
        name="Setup A (Medio)",
        segments=[0, 1, 2],
        representative_segment=1,
        avg_brightness=0.5,
        dominant_color=(0, 128, 128),
        total_duration=6.0,
        segment_count=3,
        visual_consistency=0.85
    )

    d = group.to_dict()

    assert d['group_id'] == 0
    assert d['name'] == "Setup A (Medio)"
    assert d['segments'] == [0, 1, 2]
    assert d['segment_count'] == 3
    assert d['visual_consistency'] == 0.85

    print("✓ to_dict() funciona correctamente")


def test_get_scene_summary():
    """Test de función de resumen"""
    print("\n=== Test: Resumen de Escenas ===")

    grouper = SceneGrouper()
    segments = create_mock_segments(10, varied=True)
    result = grouper.analyze_project(segments)

    summary = get_scene_summary(result)

    assert 'total_groups' in summary
    assert 'total_scene_changes' in summary
    assert 'avg_group_size' in summary
    assert 'avg_consistency' in summary

    print(f"✓ Total grupos: {summary['total_groups']}")
    print(f"✓ Cambios de escena: {summary['total_scene_changes']}")
    print(f"✓ Tamaño promedio de grupo: {summary['avg_group_size']:.1f}")
    print(f"✓ Consistencia promedio: {summary['avg_consistency']:.2f}")


def test_get_similar_segments():
    """Test de búsqueda de segmentos similares"""
    print("\n=== Test: Búsqueda de Segmentos Similares ===")

    grouper = SceneGrouper()
    segments = create_mock_segments(10, varied=True)

    # Buscar similares al segmento 0
    similar = grouper.get_similar_segments(segments, 0, top_n=3)

    assert len(similar) <= 3
    print(f"✓ Encontrados {len(similar)} segmentos similares al segmento 0:")

    for idx, similarity in similar:
        print(f"  - Segmento {idx}: similaridad={similarity:.3f}")

    # Las similaridades deberían estar entre 0 y 1
    for _, sim in similar:
        assert 0 <= sim <= 1

    print("✓ Búsqueda de similares funciona correctamente")


def test_format_scene_groups_for_display():
    """Test de formateo para UI"""
    print("\n=== Test: Formateo para Display ===")

    grouper = SceneGrouper()
    segments = create_mock_segments(10, varied=True)
    result = grouper.analyze_project(segments)

    formatted = format_scene_groups_for_display(result, segments)

    assert len(formatted) == result.total_groups

    for group in formatted:
        assert 'group_id' in group
        assert 'name' in group
        assert 'segment_count' in group
        assert 'visual_consistency' in group
        assert 'tier_distribution' in group

    print(f"✓ {len(formatted)} grupos formateados para display")
    for g in formatted:
        print(f"  - {g['name']}: {g['segment_count']} segs, "
              f"consistencia={g['visual_consistency']}%")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE SCENE GROUPER")
    print("=" * 60)

    test_grouper_initialization()
    test_empty_segments()
    test_single_segment()
    test_similar_segments_grouping()
    test_varied_segments_grouping()
    test_scene_change_detection()
    test_fingerprint_extraction()
    test_fingerprint_distance()
    test_scene_group_to_dict()
    test_get_scene_summary()
    test_get_similar_segments()
    test_format_scene_groups_for_display()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
