#!/usr/bin/env python3
"""
Tests para el módulo search_engine.py
"""

from search_engine import (
    SearchEngine, SearchQuery, SearchResult, Filter, FilterGroup,
    FilterOperator, SortOrder, LogicalOperator,
    build_query_from_dict, get_search_summary, get_available_filters
)


def create_mock_segment(
    index=0, score=7.0, tier="SILVER",
    duration=5.0, start_time=0.0,
    shot_type="ESTATICA", framing_type="MEDIUM_SHOT",
    face_count=0, tags=None, scene_group_id=0,
    is_key_moment=False, is_best_take=None, is_repeated_take=False
):
    """Crea un segmento simulado para pruebas"""
    return {
        'index': index,
        'score': score,
        'tier': tier,
        'duration': duration,
        'start_time': start_time,
        'end_time': start_time + duration,
        'shot_type': shot_type,
        'framing_type': framing_type,
        'face_count': face_count,
        'face_analysis': {
            'has_faces': face_count > 0,
            'avg_face_count': face_count,
            'primary_face_coverage': 0.15 if face_count > 0 else 0,
        },
        'metrics': {
            'brightness_mean': 0.5,
            'contrast_mean': 0.5,
            'sharpness_mean': 100,
            'motion_mean': 1.0,
            'motion_std': 0.5,
        },
        'tags': tags or [],
        'scene_group_id': scene_group_id,
        'is_key_moment': is_key_moment,
        'is_best_take': is_best_take,
        'is_repeated_take': is_repeated_take,
    }


def create_test_segments():
    """Crea un conjunto de segmentos de prueba"""
    return [
        create_mock_segment(0, score=9.0, tier="GOLD", duration=5.0, start_time=0,
                           face_count=1, tags=["persona", "estatico", "nitido"],
                           is_key_moment=True, is_best_take=True),
        create_mock_segment(1, score=8.0, tier="GOLD", duration=4.0, start_time=5,
                           shot_type="PANEO", face_count=0, tags=["movimiento_camara"]),
        create_mock_segment(2, score=7.5, tier="SILVER", duration=6.0, start_time=9,
                           face_count=2, tags=["varias_personas", "entrevista"],
                           scene_group_id=1),
        create_mock_segment(3, score=6.0, tier="BRONZE", duration=3.0, start_time=15,
                           framing_type="CLOSE_UP", tags=["primer_plano"]),
        create_mock_segment(4, score=4.0, tier="DISCARD", duration=2.0, start_time=18,
                           tags=["borroso"], is_repeated_take=True),
        create_mock_segment(5, score=7.0, tier="SILVER", duration=5.0, start_time=20,
                           face_count=1, tags=["persona", "estatico"],
                           scene_group_id=1, is_best_take=False),
    ]


def test_engine_initialization():
    """Test de inicialización del motor de búsqueda"""
    print("\n=== Test: Inicialización del SearchEngine ===")

    engine = SearchEngine()

    assert hasattr(engine, 'searchable_fields')
    assert hasattr(engine, 'field_aliases')
    assert len(engine.searchable_fields) > 0

    print("✓ SearchEngine inicializado correctamente")
    print(f"✓ Campos buscables: {len(engine.searchable_fields)}")
    print(f"✓ Alias disponibles: {len(engine.field_aliases)}")


def test_filter_operator_enum():
    """Test del enum FilterOperator"""
    print("\n=== Test: Enum FilterOperator ===")

    assert FilterOperator.EQUALS.value == "eq"
    assert FilterOperator.GREATER_THAN.value == "gt"
    assert FilterOperator.CONTAINS.value == "contains"
    assert FilterOperator.BETWEEN.value == "between"

    print("✓ Todos los operadores de filtro definidos correctamente")


def test_empty_search():
    """Test de búsqueda en lista vacía"""
    print("\n=== Test: Búsqueda en Lista Vacía ===")

    engine = SearchEngine()
    query = SearchQuery()

    result = engine.search([], query)

    assert result.total_count == 0
    assert result.segments == []
    assert result.total_pages == 0

    print("✓ Búsqueda en lista vacía manejada correctamente")


def test_search_without_filters():
    """Test de búsqueda sin filtros"""
    print("\n=== Test: Búsqueda Sin Filtros ===")

    engine = SearchEngine()
    segments = create_test_segments()
    query = SearchQuery()

    result = engine.search(segments, query)

    assert result.total_count == 6
    assert len(result.segments) == 6

    print(f"✓ Búsqueda sin filtros retorna todos los {result.total_count} segmentos")


def test_filter_equals():
    """Test de filtro de igualdad"""
    print("\n=== Test: Filtro EQUALS ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar solo GOLD
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('tier', FilterOperator.EQUALS, 'GOLD')
        ])
    )

    result = engine.search(segments, query)

    assert result.total_count == 2
    assert all(s['tier'] == 'GOLD' for s in result.segments)

    print(f"✓ Filtro tier=GOLD encontró {result.total_count} segmentos")


def test_filter_greater_than():
    """Test de filtro mayor que"""
    print("\n=== Test: Filtro GREATER_EQUAL ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar score >= 7.5
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('score', FilterOperator.GREATER_EQUAL, 7.5)
        ])
    )

    result = engine.search(segments, query)

    assert all(s['score'] >= 7.5 for s in result.segments)
    print(f"✓ Filtro score>=7.5 encontró {result.total_count} segmentos")


def test_filter_contains():
    """Test de filtro contiene (para arrays)"""
    print("\n=== Test: Filtro CONTAINS ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar segmentos con tag "persona"
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('tags', FilterOperator.CONTAINS, 'persona')
        ])
    )

    result = engine.search(segments, query)

    assert result.total_count == 2
    assert all('persona' in s['tags'] for s in result.segments)

    print(f"✓ Filtro tags contains 'persona' encontró {result.total_count} segmentos")


def test_filter_in():
    """Test de filtro IN (en lista)"""
    print("\n=== Test: Filtro IN ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar GOLD o SILVER
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('tier', FilterOperator.IN, ['GOLD', 'SILVER'])
        ])
    )

    result = engine.search(segments, query)

    assert all(s['tier'] in ['GOLD', 'SILVER'] for s in result.segments)
    print(f"✓ Filtro tier IN [GOLD, SILVER] encontró {result.total_count} segmentos")


def test_filter_between():
    """Test de filtro BETWEEN"""
    print("\n=== Test: Filtro BETWEEN ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar score entre 6 y 8
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('score', FilterOperator.BETWEEN, [6.0, 8.0])
        ])
    )

    result = engine.search(segments, query)

    assert all(6.0 <= s['score'] <= 8.0 for s in result.segments)
    print(f"✓ Filtro score BETWEEN [6, 8] encontró {result.total_count} segmentos")


def test_filter_is_true():
    """Test de filtro IS_TRUE"""
    print("\n=== Test: Filtro IS_TRUE ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar key moments
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('is_key_moment', FilterOperator.IS_TRUE)
        ])
    )

    result = engine.search(segments, query)

    assert all(s['is_key_moment'] == True for s in result.segments)
    print(f"✓ Filtro is_key_moment=true encontró {result.total_count} segmentos")


def test_filter_is_false():
    """Test de filtro IS_FALSE"""
    print("\n=== Test: Filtro IS_FALSE ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar no repetidos
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('is_repeated_take', FilterOperator.IS_FALSE)
        ])
    )

    result = engine.search(segments, query)

    assert all(s['is_repeated_take'] == False for s in result.segments)
    print(f"✓ Filtro is_repeated=false encontró {result.total_count} segmentos")


def test_combined_filters_and():
    """Test de filtros combinados con AND"""
    print("\n=== Test: Filtros Combinados (AND) ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # GOLD + con rostros
    query = SearchQuery(
        filters=FilterGroup(
            filters=[
                Filter('tier', FilterOperator.EQUALS, 'GOLD'),
                Filter('face_analysis.has_faces', FilterOperator.IS_TRUE)
            ],
            operator=LogicalOperator.AND
        )
    )

    result = engine.search(segments, query)

    for s in result.segments:
        assert s['tier'] == 'GOLD'
        assert s['face_analysis']['has_faces'] == True

    print(f"✓ Filtro AND (GOLD + faces) encontró {result.total_count} segmentos")


def test_combined_filters_or():
    """Test de filtros combinados con OR"""
    print("\n=== Test: Filtros Combinados (OR) ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # GOLD O score >= 8
    query = SearchQuery(
        filters=FilterGroup(
            filters=[
                Filter('tier', FilterOperator.EQUALS, 'GOLD'),
                Filter('face_count', FilterOperator.GREATER_EQUAL, 2)
            ],
            operator=LogicalOperator.OR
        )
    )

    result = engine.search(segments, query)

    print(f"✓ Filtro OR (GOLD | faces>=2) encontró {result.total_count} segmentos")


def test_sorting_ascending():
    """Test de ordenamiento ascendente"""
    print("\n=== Test: Ordenamiento Ascendente ===")

    engine = SearchEngine()
    segments = create_test_segments()

    query = SearchQuery(sort_by='score', sort_order=SortOrder.ASC)
    result = engine.search(segments, query)

    scores = [s['score'] for s in result.segments]
    assert scores == sorted(scores)

    print(f"✓ Ordenamiento ascendente por score funciona")


def test_sorting_descending():
    """Test de ordenamiento descendente"""
    print("\n=== Test: Ordenamiento Descendente ===")

    engine = SearchEngine()
    segments = create_test_segments()

    query = SearchQuery(sort_by='score', sort_order=SortOrder.DESC)
    result = engine.search(segments, query)

    scores = [s['score'] for s in result.segments]
    assert scores == sorted(scores, reverse=True)

    print(f"✓ Ordenamiento descendente por score funciona")


def test_pagination():
    """Test de paginación"""
    print("\n=== Test: Paginación ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Página 1, 2 items por página
    query = SearchQuery(page=1, page_size=2)
    result = engine.search(segments, query)

    assert len(result.segments) == 2
    assert result.page == 1
    assert result.total_pages == 3

    # Página 2
    query2 = SearchQuery(page=2, page_size=2)
    result2 = engine.search(segments, query2)

    assert len(result2.segments) == 2
    assert result2.page == 2

    print(f"✓ Paginación funciona correctamente")
    print(f"  - Total: {result.total_count}, Páginas: {result.total_pages}")


def test_quick_search():
    """Test de búsqueda rápida"""
    print("\n=== Test: Búsqueda Rápida ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar GOLD
    results = engine.quick_search(segments, tier="GOLD")
    assert len(results) == 2
    print(f"✓ quick_search(tier=GOLD) encontró {len(results)} segmentos")

    # Buscar con rostros
    results2 = engine.quick_search(segments, has_faces=True)
    assert all(s['face_analysis']['has_faces'] for s in results2)
    print(f"✓ quick_search(has_faces=True) encontró {len(results2)} segmentos")

    # Buscar por score mínimo
    results3 = engine.quick_search(segments, score_min=7.0)
    assert all(s['score'] >= 7.0 for s in results3)
    print(f"✓ quick_search(score_min=7.0) encontró {len(results3)} segmentos")


def test_nested_field_access():
    """Test de acceso a campos anidados"""
    print("\n=== Test: Acceso a Campos Anidados ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar por metrics.motion_mean
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('metrics.brightness_mean', FilterOperator.GREATER_EQUAL, 0.4)
        ])
    )

    result = engine.search(segments, query)
    print(f"✓ Filtro por campo anidado metrics.brightness_mean encontró {result.total_count} segmentos")


def test_field_aliases():
    """Test de alias de campos"""
    print("\n=== Test: Alias de Campos ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Usar alias 'quality' en lugar de 'score'
    query = SearchQuery(
        filters=FilterGroup(filters=[
            Filter('quality', FilterOperator.GREATER_EQUAL, 8.0)
        ])
    )

    result = engine.search(segments, query)
    assert all(s['score'] >= 8.0 for s in result.segments)

    print(f"✓ Alias 'quality' -> 'score' funciona correctamente")


def test_predefined_searches():
    """Test de búsquedas predefinidas"""
    print("\n=== Test: Búsquedas Predefinidas ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # find_gold_segments
    gold = engine.find_gold_segments(segments)
    assert all(s['tier'] == 'GOLD' for s in gold)
    print(f"✓ find_gold_segments encontró {len(gold)} segmentos")

    # find_usable_segments
    usable = engine.find_usable_segments(segments)
    assert all(s['tier'] in ['GOLD', 'SILVER'] for s in usable)
    assert all(not s['is_repeated_take'] for s in usable)
    print(f"✓ find_usable_segments encontró {len(usable)} segmentos")

    # find_segments_with_faces
    with_faces = engine.find_segments_with_faces(segments)
    assert all(s['face_analysis']['has_faces'] for s in with_faces)
    print(f"✓ find_segments_with_faces encontró {len(with_faces)} segmentos")

    # find_key_moments
    key_moments = engine.find_key_moments(segments)
    assert all(s['is_key_moment'] for s in key_moments)
    print(f"✓ find_key_moments encontró {len(key_moments)} segmentos")

    # find_static_shots
    static = engine.find_static_shots(segments)
    assert all(s['shot_type'] == 'ESTATICA' for s in static)
    print(f"✓ find_static_shots encontró {len(static)} segmentos")


def test_find_by_scene():
    """Test de búsqueda por escena"""
    print("\n=== Test: Búsqueda por Escena ===")

    engine = SearchEngine()
    segments = create_test_segments()

    results = engine.find_by_scene(segments, 1)
    assert all(s['scene_group_id'] == 1 for s in results)

    print(f"✓ find_by_scene(1) encontró {len(results)} segmentos")


def test_find_segments_in_range():
    """Test de búsqueda por rango temporal"""
    print("\n=== Test: Búsqueda por Rango Temporal ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Buscar entre 5s y 15s
    results = engine.find_segments_in_range(segments, 5.0, 15.0)

    print(f"✓ find_segments_in_range(5, 15) encontró {len(results)} segmentos")


def test_build_query_from_dict():
    """Test de construcción de query desde diccionario"""
    print("\n=== Test: Build Query from Dict ===")

    query_dict = {
        'filters': {
            'operator': 'and',
            'filters': [
                {'field': 'tier', 'operator': 'eq', 'value': 'GOLD'},
                {'field': 'score', 'operator': 'gte', 'value': 8.0}
            ]
        },
        'sort_by': 'score',
        'sort_order': 'desc',
        'page': 1,
        'page_size': 10
    }

    query = build_query_from_dict(query_dict)

    assert query.sort_by == 'score'
    assert query.sort_order == SortOrder.DESC
    assert query.page == 1
    assert query.page_size == 10
    assert query.filters is not None

    print("✓ build_query_from_dict funciona correctamente")


def test_search_result_dataclass():
    """Test de la dataclass SearchResult"""
    print("\n=== Test: Dataclass SearchResult ===")

    engine = SearchEngine()
    segments = create_test_segments()
    query = SearchQuery(page=1, page_size=2)

    result = engine.search(segments, query)
    d = result.to_dict()

    assert 'segments' in d
    assert 'total_count' in d
    assert 'page' in d
    assert 'total_pages' in d
    assert 'has_next' in d
    assert 'has_prev' in d

    print("✓ SearchResult.to_dict() funciona correctamente")


def test_get_search_summary():
    """Test de la función get_search_summary"""
    print("\n=== Test: Función get_search_summary ===")

    engine = SearchEngine()
    segments = create_test_segments()

    # Con resultados
    result = engine.search(segments, SearchQuery())
    summary = get_search_summary(result)

    assert summary['found'] == 6
    assert 'description' in summary

    print(f"✓ get_search_summary: {summary['description']}")

    # Sin resultados
    result_empty = engine.search([], SearchQuery())
    summary_empty = get_search_summary(result_empty)

    assert summary_empty['found'] == 0
    print(f"✓ Resumen vacío: {summary_empty['description']}")


def test_get_available_filters():
    """Test de la función get_available_filters"""
    print("\n=== Test: Función get_available_filters ===")

    filters_info = get_available_filters()

    assert 'fields' in filters_info
    assert 'operators' in filters_info
    assert 'logical_operators' in filters_info
    assert 'sort_fields' in filters_info

    print(f"✓ get_available_filters retorna {len(filters_info['fields'])} campos")
    print(f"✓ Operadores disponibles: {len(filters_info['operators'])}")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TESTS DE SEARCH ENGINE")
    print("=" * 60)

    test_engine_initialization()
    test_filter_operator_enum()
    test_empty_search()
    test_search_without_filters()
    test_filter_equals()
    test_filter_greater_than()
    test_filter_contains()
    test_filter_in()
    test_filter_between()
    test_filter_is_true()
    test_filter_is_false()
    test_combined_filters_and()
    test_combined_filters_or()
    test_sorting_ascending()
    test_sorting_descending()
    test_pagination()
    test_quick_search()
    test_nested_field_access()
    test_field_aliases()
    test_predefined_searches()
    test_find_by_scene()
    test_find_segments_in_range()
    test_build_query_from_dict()
    test_search_result_dataclass()
    test_get_search_summary()
    test_get_available_filters()

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
