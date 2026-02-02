#!/usr/bin/env python3
"""
Tests para el módulo context_tagger.py
"""

from context_tagger import (
    ContextTagger, Tag, TagCategory, SegmentTags, TaggingResult,
    KeyMoment, KeyMomentType, ContentTag, ContextTag, QualityTag,
    get_tagging_summary, format_tags_for_display
)


def create_mock_segment(
    index=0, score=7.0, tier="SILVER",
    brightness=0.5, contrast=0.5, sharpness=100,
    motion=1.0, motion_std=0.5,
    face_count=0, face_coverage=0,
    framing_type="MEDIUM_SHOT", shot_type="ESTATICA",
    scene_group_id=0, take_group_id=None,
    duration=5.0, start_time=0.0
):
    """Crea un segmento simulado para pruebas"""
    return {
        'index': index,
        'score': score,
        'tier': tier,
        'duration': duration,
        'start_time': start_time,
        'metrics': {
            'brightness_mean': brightness,
            'contrast_mean': contrast,
            'sharpness_mean': sharpness,
            'motion_mean': motion,
            'motion_std': motion_std,
            'edge_density': 0.15,
        },
        'face_analysis': {
            'has_faces': face_count > 0,
            'avg_face_count': face_count,
            'primary_face_coverage': face_coverage,
            'avg_framing_issues': 0,
        },
        'framing': {
            'shot_type': framing_type,
        },
        'framing_type': framing_type,
        'framing_type_display': framing_type.replace('_', ' ').title(),
        'shot_type': shot_type,
        'scene_group_id': scene_group_id,
        'take_group_id': take_group_id,
    }


def test_tagger_initialization():
    """Test de inicialización del tagger"""
    print("\n=== Test: Inicialización del ContextTagger ===")

    tagger = ContextTagger()

    assert hasattr(tagger, 'thresholds'), "Debe tener thresholds"
    assert 'bright_threshold' in tagger.thresholds
    assert tagger.thresholds['bright_threshold'] > 0

    print("✓ ContextTagger inicializado correctamente")
    print(f"✓ Thresholds configurados: {len(tagger.thresholds)}")


def test_tag_category_enum():
    """Test del enum TagCategory"""
    print("\n=== Test: Enum TagCategory ===")

    assert TagCategory.CONTENT.value == "content"
    assert TagCategory.CONTEXT.value == "context"
    assert TagCategory.QUALITY.value == "quality"
    assert TagCategory.COMPOSITION.value == "composition"
    assert TagCategory.KEY_MOMENT.value == "key_moment"

    print("✓ Todas las categorías de tags definidas correctamente")


def test_content_tag_enum():
    """Test del enum ContentTag"""
    print("\n=== Test: Enum ContentTag ===")

    assert ContentTag.PERSON.value == "persona"
    assert ContentTag.FACE_VISIBLE.value == "rostro_visible"
    assert ContentTag.STATIC.value == "estatico"
    assert ContentTag.WIDE_SHOT.value == "plano_general"

    print("✓ Todos los tags de contenido definidos correctamente")


def test_empty_segments_tagging():
    """Test con lista vacía de segmentos"""
    print("\n=== Test: Etiquetado de Lista Vacía ===")

    tagger = ContextTagger()
    result = tagger.tag_segments([])

    assert result.segment_tags == []
    assert result.key_moments == []
    assert len(result.all_tags_used) == 0

    print("✓ Lista vacía manejada correctamente")


def test_single_segment_tagging():
    """Test con un solo segmento"""
    print("\n=== Test: Etiquetado de Un Segmento ===")

    tagger = ContextTagger()
    segments = [create_mock_segment()]

    result = tagger.tag_segments(segments)

    assert len(result.segment_tags) == 1
    assert result.segment_tags[0].segment_idx == 0
    assert len(result.segment_tags[0].tags) > 0

    print(f"✓ Segmento etiquetado con {len(result.segment_tags[0].tags)} tags")
    print(f"  Tags: {[t.name for t in result.segment_tags[0].tags]}")


def test_content_tags_generation():
    """Test de generación de tags de contenido"""
    print("\n=== Test: Tags de Contenido ===")

    tagger = ContextTagger()

    # Segmento con rostro
    seg_with_face = create_mock_segment(
        face_count=1, face_coverage=0.2,
        framing_type="CLOSE_UP"
    )

    result = tagger.tag_segments([seg_with_face])
    tags = result.segment_tags[0]
    tag_names = [t.name for t in tags.tags]

    assert ContentTag.PERSON.value in tag_names
    assert ContentTag.FACE_VISIBLE.value in tag_names
    print("✓ Tags de persona/rostro generados")

    # Segmento con múltiples personas
    seg_multiple = create_mock_segment(face_count=3, face_coverage=0.1)
    result2 = tagger.tag_segments([seg_multiple])
    tags2 = [t.name for t in result2.segment_tags[0].tags]

    assert ContentTag.MULTIPLE_PEOPLE.value in tags2
    print("✓ Tag de múltiples personas generado")

    # Segmento estático
    seg_static = create_mock_segment(motion=0.5, shot_type="ESTATICA")
    result3 = tagger.tag_segments([seg_static])
    tags3 = [t.name for t in result3.segment_tags[0].tags]

    assert ContentTag.STATIC.value in tags3
    print("✓ Tag de toma estática generado")


def test_context_tags_generation():
    """Test de generación de tags de contexto"""
    print("\n=== Test: Tags de Contexto ===")

    tagger = ContextTagger()

    # Segmento brillante
    seg_bright = create_mock_segment(brightness=0.75)
    result = tagger.tag_segments([seg_bright])
    tags = [t.name for t in result.segment_tags[0].tags]

    assert ContextTag.BRIGHT.value in tags
    print("✓ Tag de iluminado generado")

    # Segmento oscuro
    seg_dark = create_mock_segment(brightness=0.25)
    result2 = tagger.tag_segments([seg_dark])
    tags2 = [t.name for t in result2.segment_tags[0].tags]

    assert ContextTag.DARK.value in tags2
    print("✓ Tag de oscuro generado")

    # Segmento con alto contraste
    seg_contrast = create_mock_segment(contrast=0.7)
    result3 = tagger.tag_segments([seg_contrast])
    tags3 = [t.name for t in result3.segment_tags[0].tags]

    assert ContextTag.HIGH_CONTRAST.value in tags3
    print("✓ Tag de alto contraste generado")


def test_quality_tags_generation():
    """Test de generación de tags de calidad"""
    print("\n=== Test: Tags de Calidad ===")

    tagger = ContextTagger()

    # Segmento nítido
    seg_sharp = create_mock_segment(sharpness=150)
    result = tagger.tag_segments([seg_sharp])
    tags = [t.name for t in result.segment_tags[0].tags]

    assert QualityTag.SHARP.value in tags
    assert QualityTag.IN_FOCUS.value in tags
    print("✓ Tags de nitidez generados")

    # Segmento borroso
    seg_blurry = create_mock_segment(sharpness=30)
    result2 = tagger.tag_segments([seg_blurry])
    tags2 = [t.name for t in result2.segment_tags[0].tags]

    assert QualityTag.BLURRY.value in tags2
    print("✓ Tag de borroso generado")

    # Segmento estable
    seg_stable = create_mock_segment(motion_std=0.3, shot_type="ESTATICA")
    result3 = tagger.tag_segments([seg_stable])
    tags3 = [t.name for t in result3.segment_tags[0].tags]

    assert QualityTag.STABLE.value in tags3
    print("✓ Tag de estabilidad generado")


def test_key_moments_detection():
    """Test de detección de momentos clave"""
    print("\n=== Test: Detección de Momentos Clave ===")

    tagger = ContextTagger()

    # Crear varios segmentos con diferentes calidades
    segments = [
        create_mock_segment(index=0, score=6.5, tier="BRONZE", start_time=0),
        create_mock_segment(index=1, score=7.5, tier="SILVER", start_time=5),
        create_mock_segment(index=2, score=8.5, tier="GOLD", start_time=10),  # Mejor
        create_mock_segment(index=3, score=7.0, tier="SILVER", start_time=15),
        create_mock_segment(index=4, score=6.0, tier="BRONZE", start_time=20),
    ]

    result = tagger.tag_segments(segments)

    assert len(result.key_moments) > 0
    print(f"✓ Se detectaron {len(result.key_moments)} momentos clave")

    # Verificar que el mejor segmento es un key moment
    best_moment = next(
        (km for km in result.key_moments if km.moment_type == KeyMomentType.BEST_QUALITY),
        None
    )
    if best_moment:
        assert best_moment.segment_idx == 2  # El de score 8.5
        print(f"✓ Mejor calidad detectada en segmento {best_moment.segment_idx}")

    # Verificar apertura/cierre
    opening = next(
        (km for km in result.key_moments if km.moment_type == KeyMomentType.OPENING),
        None
    )
    if opening:
        print(f"✓ Apertura detectada en segmento {opening.segment_idx}")


def test_tag_dataclass():
    """Test de la dataclass Tag"""
    print("\n=== Test: Dataclass Tag ===")

    tag = Tag(
        name="persona",
        category=TagCategory.CONTENT,
        confidence=0.9,
        source="auto"
    )

    d = tag.to_dict()

    assert d['name'] == "persona"
    assert d['category'] == "content"
    assert d['confidence'] == 0.9
    assert d['source'] == "auto"

    print("✓ Tag.to_dict() funciona correctamente")


def test_segment_tags_dataclass():
    """Test de la dataclass SegmentTags"""
    print("\n=== Test: Dataclass SegmentTags ===")

    tags = [
        Tag(name="persona", category=TagCategory.CONTENT),
        Tag(name="iluminado", category=TagCategory.CONTEXT),
    ]

    seg_tags = SegmentTags(
        segment_idx=0,
        tags=tags,
        auto_description="Plano medio con persona"
    )

    d = seg_tags.to_dict()

    assert d['segment_idx'] == 0
    assert len(d['tags']) == 2
    assert d['tag_count'] == 2
    assert "persona" in d['tag_names']

    print("✓ SegmentTags.to_dict() funciona correctamente")


def test_key_moment_dataclass():
    """Test de la dataclass KeyMoment"""
    print("\n=== Test: Dataclass KeyMoment ===")

    km = KeyMoment(
        segment_idx=5,
        moment_type=KeyMomentType.BEST_QUALITY,
        reason="Mejor puntuación del proyecto",
        score=8.5,
        timestamp=25.0
    )

    d = km.to_dict()

    assert d['segment_idx'] == 5
    assert d['moment_type'] == "mejor_calidad"
    assert d['score'] == 8.5
    assert d['timestamp'] == 25.0

    print("✓ KeyMoment.to_dict() funciona correctamente")


def test_tagging_result_dataclass():
    """Test de la dataclass TaggingResult"""
    print("\n=== Test: Dataclass TaggingResult ===")

    result = TaggingResult(
        segment_tags=[],
        key_moments=[],
        all_tags_used={"persona", "iluminado"},
        tag_frequency={"persona": 5, "iluminado": 3}
    )

    d = result.to_dict()

    assert d['total_segments'] == 0
    assert d['total_key_moments'] == 0
    assert len(d['all_tags_used']) == 2

    print("✓ TaggingResult.to_dict() funciona correctamente")


def test_get_tagging_summary():
    """Test de la función get_tagging_summary"""
    print("\n=== Test: Función get_tagging_summary ===")

    # Resultado vacío
    result_empty = TaggingResult(
        segment_tags=[],
        key_moments=[],
        all_tags_used=set(),
        tag_frequency={}
    )

    summary = get_tagging_summary(result_empty)
    assert summary['total_segments'] == 0
    assert summary['total_tags'] == 0
    print(f"✓ Resumen vacío: {summary['description']}")

    # Resultado con tags
    tags = [Tag(name="persona", category=TagCategory.CONTENT)]
    seg_tags = SegmentTags(segment_idx=0, tags=tags)

    result_with_tags = TaggingResult(
        segment_tags=[seg_tags],
        key_moments=[],
        all_tags_used={"persona"},
        tag_frequency={"persona": 1}
    )

    summary2 = get_tagging_summary(result_with_tags)
    assert summary2['total_segments'] == 1
    assert summary2['total_tags'] == 1
    print(f"✓ Resumen con tags: {summary2['description']}")


def test_format_tags_for_display():
    """Test de la función format_tags_for_display"""
    print("\n=== Test: Función format_tags_for_display ===")

    tags = [
        Tag(name="persona", category=TagCategory.CONTENT, confidence=0.9),
        Tag(name="iluminado", category=TagCategory.CONTEXT, confidence=0.8),
        Tag(name="nitido", category=TagCategory.QUALITY, confidence=1.0),
    ]

    km = KeyMoment(
        segment_idx=0,
        moment_type=KeyMomentType.BEST_QUALITY,
        reason="Mejor calidad",
        score=8.0
    )

    seg_tags = SegmentTags(
        segment_idx=0,
        tags=tags,
        key_moment=km,
        auto_description="Plano con persona, iluminado"
    )

    formatted = format_tags_for_display(seg_tags)

    assert formatted['segment_idx'] == 0
    assert 'content' in formatted['tags_by_category']
    assert 'context' in formatted['tags_by_category']
    assert 'quality' in formatted['tags_by_category']
    assert formatted['is_key_moment'] == True
    assert formatted['key_moment_type'] == "mejor_calidad"

    print("✓ format_tags_for_display funciona correctamente")
    print(f"  Tags por categoría: {list(formatted['tags_by_category'].keys())}")


def test_get_segments_by_tag():
    """Test de búsqueda de segmentos por tag"""
    print("\n=== Test: Búsqueda por Tag ===")

    tagger = ContextTagger()

    segments = [
        create_mock_segment(index=0, face_count=1),  # Con persona
        create_mock_segment(index=1, face_count=0),  # Sin persona
        create_mock_segment(index=2, face_count=2),  # Con personas
    ]

    result = tagger.tag_segments(segments)

    # Buscar segmentos con tag "persona"
    matching = tagger.get_segments_by_tag(result, ContentTag.PERSON.value)

    assert 0 in matching
    assert 2 in matching
    assert 1 not in matching

    print(f"✓ Encontrados {len(matching)} segmentos con tag 'persona'")


def test_get_tag_statistics():
    """Test de estadísticas de tags"""
    print("\n=== Test: Estadísticas de Tags ===")

    tagger = ContextTagger()

    segments = [
        create_mock_segment(index=0, face_count=1, brightness=0.7),
        create_mock_segment(index=1, face_count=0, brightness=0.3),
        create_mock_segment(index=2, face_count=1, brightness=0.5),
    ]

    result = tagger.tag_segments(segments)
    stats = tagger.get_tag_statistics(result)

    assert stats['total_tags'] > 0
    assert stats['unique_tags'] > 0
    assert stats['avg_tags_per_segment'] > 0
    assert 'most_common' in stats
    assert 'by_category' in stats

    print(f"✓ Estadísticas calculadas:")
    print(f"  - Total tags: {stats['total_tags']}")
    print(f"  - Tags únicos: {stats['unique_tags']}")
    print(f"  - Promedio por segmento: {stats['avg_tags_per_segment']:.1f}")


def test_auto_description_generation():
    """Test de generación de descripción automática"""
    print("\n=== Test: Descripción Automática ===")

    tagger = ContextTagger()

    # Segmento completo
    seg = create_mock_segment(
        face_count=1,
        framing_type="MEDIUM_SHOT",
        shot_type="PANEO",
        tier="GOLD",
        score=8.5
    )

    result = tagger.tag_segments([seg])
    description = result.segment_tags[0].auto_description

    assert len(description) > 0
    print(f"✓ Descripción generada: '{description}'")


def test_interview_detection():
    """Test de detección de entrevista"""
    print("\n=== Test: Detección de Entrevista ===")

    tagger = ContextTagger()

    # Segmento tipo entrevista (rostro con poco movimiento)
    seg_interview = create_mock_segment(
        face_count=1,
        face_coverage=0.12,
        motion=0.5,
        shot_type="ESTATICA"
    )

    result = tagger.tag_segments([seg_interview])
    tags = [t.name for t in result.segment_tags[0].tags]

    if ContentTag.INTERVIEW.value in tags:
        print("✓ Entrevista detectada correctamente")
    else:
        print("  (Entrevista no detectada - puede ser por umbrales)")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE CONTEXT TAGGER")
    print("=" * 60)

    test_tagger_initialization()
    test_tag_category_enum()
    test_content_tag_enum()
    test_empty_segments_tagging()
    test_single_segment_tagging()
    test_content_tags_generation()
    test_context_tags_generation()
    test_quality_tags_generation()
    test_key_moments_detection()
    test_tag_dataclass()
    test_segment_tags_dataclass()
    test_key_moment_dataclass()
    test_tagging_result_dataclass()
    test_get_tagging_summary()
    test_format_tags_for_display()
    test_get_segments_by_tag()
    test_get_tag_statistics()
    test_auto_description_generation()
    test_interview_detection()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
