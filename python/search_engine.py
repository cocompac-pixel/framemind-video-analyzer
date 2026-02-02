#!/usr/bin/env python3
"""
Search Engine Module v1.0
Motor de búsqueda transversal para segmentos de video.

Funcionalidades:
- Búsqueda por múltiples criterios combinados
- Filtrado avanzado con operadores lógicos (AND, OR, NOT)
- Queries complejas sobre todo el proyecto
- Búsqueda por rangos numéricos
- Búsqueda por tags, tiers, tipos de plano, etc.
- Ordenamiento y paginación de resultados
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Union
from enum import Enum
import re


class FilterOperator(Enum):
    """Operadores para filtros"""
    EQUALS = "eq"
    NOT_EQUALS = "neq"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    BETWEEN = "between"
    EXISTS = "exists"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


class SortOrder(Enum):
    """Orden de clasificación"""
    ASC = "asc"
    DESC = "desc"


class LogicalOperator(Enum):
    """Operadores lógicos para combinar filtros"""
    AND = "and"
    OR = "or"


@dataclass
class Filter:
    """Representa un filtro individual"""
    field: str
    operator: FilterOperator
    value: Any = None

    def to_dict(self):
        return {
            'field': self.field,
            'operator': self.operator.value,
            'value': self.value,
        }


@dataclass
class FilterGroup:
    """Grupo de filtros con operador lógico"""
    filters: List[Union[Filter, 'FilterGroup']]
    operator: LogicalOperator = LogicalOperator.AND

    def to_dict(self):
        return {
            'operator': self.operator.value,
            'filters': [
                f.to_dict() if hasattr(f, 'to_dict') else f
                for f in self.filters
            ],
        }


@dataclass
class SearchQuery:
    """Query de búsqueda completa"""
    filters: Optional[FilterGroup] = None
    sort_by: str = "index"
    sort_order: SortOrder = SortOrder.ASC
    page: int = 1
    page_size: int = 50
    include_fields: Optional[List[str]] = None
    exclude_fields: Optional[List[str]] = None

    def to_dict(self):
        return {
            'filters': self.filters.to_dict() if self.filters else None,
            'sort_by': self.sort_by,
            'sort_order': self.sort_order.value,
            'page': self.page,
            'page_size': self.page_size,
            'include_fields': self.include_fields,
            'exclude_fields': self.exclude_fields,
        }


@dataclass
class SearchResult:
    """Resultado de búsqueda"""
    segments: List[Dict]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    query: SearchQuery

    def to_dict(self):
        return {
            'segments': self.segments,
            'total_count': self.total_count,
            'page': self.page,
            'page_size': self.page_size,
            'total_pages': self.total_pages,
            'has_next': self.page < self.total_pages,
            'has_prev': self.page > 1,
        }


class SearchEngine:
    """
    Motor de búsqueda transversal para segmentos de video.
    Permite búsquedas complejas con múltiples criterios.
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Campos indexados para búsqueda rápida
        self.searchable_fields = {
            # Campos básicos
            'index', 'score', 'tier', 'duration', 'start_time', 'end_time',

            # Tipo de toma
            'shot_type', 'framing_type', 'framing_type_display',

            # Métricas
            'metrics.brightness_mean', 'metrics.contrast_mean',
            'metrics.sharpness_mean', 'metrics.motion_mean',
            'metrics.motion_std', 'metrics.edge_density',

            # Rostros
            'face_count', 'face_analysis.has_faces',
            'face_analysis.avg_face_count', 'face_analysis.primary_face_coverage',
            'any_eyes_closed',

            # Escenas y takes
            'scene_group_id', 'scene_group_name',
            'take_group_id', 'is_best_take', 'is_repeated_take',

            # Tags
            'tags', 'is_key_moment', 'key_moment_type',
            'auto_description',
        }

        # Alias de campos para búsqueda más intuitiva
        self.field_aliases = {
            'quality': 'score',
            'brightness': 'metrics.brightness_mean',
            'contrast': 'metrics.contrast_mean',
            'sharpness': 'metrics.sharpness_mean',
            'motion': 'metrics.motion_mean',
            'stability': 'metrics.motion_std',
            'faces': 'face_count',
            'scene': 'scene_group_id',
            'take': 'take_group_id',
        }

    def search(self, segments: List[Dict], query: SearchQuery) -> SearchResult:
        """
        Ejecuta una búsqueda sobre los segmentos.

        Args:
            segments: Lista de segmentos a buscar
            query: Query de búsqueda

        Returns:
            SearchResult con los resultados
        """
        if not segments:
            return SearchResult(
                segments=[],
                total_count=0,
                page=1,
                page_size=query.page_size,
                total_pages=0,
                query=query
            )

        # Aplicar filtros
        filtered = segments
        if query.filters:
            filtered = self._apply_filter_group(segments, query.filters)

        # Ordenar
        sorted_segments = self._sort_segments(filtered, query.sort_by, query.sort_order)

        # Paginar
        total_count = len(sorted_segments)
        total_pages = (total_count + query.page_size - 1) // query.page_size

        start_idx = (query.page - 1) * query.page_size
        end_idx = start_idx + query.page_size
        page_segments = sorted_segments[start_idx:end_idx]

        # Filtrar campos si se especifica
        if query.include_fields or query.exclude_fields:
            page_segments = [
                self._filter_segment_fields(seg, query.include_fields, query.exclude_fields)
                for seg in page_segments
            ]

        return SearchResult(
            segments=page_segments,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            query=query
        )

    def quick_search(self, segments: List[Dict], **kwargs) -> List[Dict]:
        """
        Búsqueda rápida con parámetros simples.

        Ejemplos:
            quick_search(segments, tier="GOLD")
            quick_search(segments, score_min=7.0, has_faces=True)
            quick_search(segments, tags=["persona", "estatico"])
        """
        filters = []

        # Procesar kwargs comunes
        if 'tier' in kwargs:
            filters.append(Filter('tier', FilterOperator.EQUALS, kwargs['tier']))

        if 'tiers' in kwargs:
            filters.append(Filter('tier', FilterOperator.IN, kwargs['tiers']))

        if 'score_min' in kwargs:
            filters.append(Filter('score', FilterOperator.GREATER_EQUAL, kwargs['score_min']))

        if 'score_max' in kwargs:
            filters.append(Filter('score', FilterOperator.LESS_EQUAL, kwargs['score_max']))

        if 'duration_min' in kwargs:
            filters.append(Filter('duration', FilterOperator.GREATER_EQUAL, kwargs['duration_min']))

        if 'duration_max' in kwargs:
            filters.append(Filter('duration', FilterOperator.LESS_EQUAL, kwargs['duration_max']))

        if 'has_faces' in kwargs:
            op = FilterOperator.IS_TRUE if kwargs['has_faces'] else FilterOperator.IS_FALSE
            filters.append(Filter('face_analysis.has_faces', op))

        if 'shot_type' in kwargs:
            filters.append(Filter('shot_type', FilterOperator.EQUALS, kwargs['shot_type']))

        if 'framing_type' in kwargs:
            filters.append(Filter('framing_type', FilterOperator.CONTAINS, kwargs['framing_type']))

        if 'tags' in kwargs:
            for tag in kwargs['tags']:
                filters.append(Filter('tags', FilterOperator.CONTAINS, tag))

        if 'has_tag' in kwargs:
            filters.append(Filter('tags', FilterOperator.CONTAINS, kwargs['has_tag']))

        if 'scene_group' in kwargs:
            filters.append(Filter('scene_group_id', FilterOperator.EQUALS, kwargs['scene_group']))

        if 'is_key_moment' in kwargs:
            op = FilterOperator.IS_TRUE if kwargs['is_key_moment'] else FilterOperator.IS_FALSE
            filters.append(Filter('is_key_moment', op))

        if 'is_best_take' in kwargs:
            op = FilterOperator.IS_TRUE if kwargs['is_best_take'] else FilterOperator.IS_FALSE
            filters.append(Filter('is_best_take', op))

        if 'is_repeated' in kwargs:
            op = FilterOperator.IS_TRUE if kwargs['is_repeated'] else FilterOperator.IS_FALSE
            filters.append(Filter('is_repeated_take', op))

        if 'exclude_repeated' in kwargs and kwargs['exclude_repeated']:
            filters.append(Filter('is_repeated_take', FilterOperator.IS_FALSE))

        # Crear query
        filter_group = FilterGroup(filters=filters) if filters else None

        sort_by = kwargs.get('sort_by', 'index')
        sort_order = SortOrder.DESC if kwargs.get('sort_desc', False) else SortOrder.ASC

        query = SearchQuery(
            filters=filter_group,
            sort_by=sort_by,
            sort_order=sort_order,
            page=1,
            page_size=len(segments)  # Sin paginación
        )

        result = self.search(segments, query)
        return result.segments

    def _apply_filter_group(self, segments: List[Dict],
                            filter_group: FilterGroup) -> List[Dict]:
        """Aplica un grupo de filtros a los segmentos"""

        if filter_group.operator == LogicalOperator.AND:
            result = segments
            for f in filter_group.filters:
                if isinstance(f, FilterGroup):
                    result = self._apply_filter_group(result, f)
                else:
                    result = [s for s in result if self._apply_filter(s, f)]
            return result

        else:  # OR
            result_set = set()
            for f in filter_group.filters:
                if isinstance(f, FilterGroup):
                    matching = self._apply_filter_group(segments, f)
                else:
                    matching = [s for s in segments if self._apply_filter(s, f)]

                for seg in matching:
                    result_set.add(seg.get('index', id(seg)))

            return [s for s in segments if s.get('index', id(s)) in result_set]

    def _apply_filter(self, segment: Dict, filter: Filter) -> bool:
        """Aplica un filtro individual a un segmento"""

        # Resolver alias de campo
        field = self.field_aliases.get(filter.field, filter.field)

        # Obtener valor del segmento (soporta campos anidados)
        value = self._get_nested_value(segment, field)

        op = filter.operator
        filter_value = filter.value

        # Operadores que no requieren valor
        if op == FilterOperator.EXISTS:
            return value is not None

        if op == FilterOperator.IS_TRUE:
            return value is True

        if op == FilterOperator.IS_FALSE:
            return value is False or value is None

        # Si el valor es None, la mayoría de comparaciones fallan
        if value is None:
            return op == FilterOperator.NOT_EQUALS

        # Comparaciones
        if op == FilterOperator.EQUALS:
            return value == filter_value

        if op == FilterOperator.NOT_EQUALS:
            return value != filter_value

        if op == FilterOperator.GREATER_THAN:
            return value > filter_value

        if op == FilterOperator.GREATER_EQUAL:
            return value >= filter_value

        if op == FilterOperator.LESS_THAN:
            return value < filter_value

        if op == FilterOperator.LESS_EQUAL:
            return value <= filter_value

        if op == FilterOperator.IN:
            return value in filter_value

        if op == FilterOperator.NOT_IN:
            return value not in filter_value

        if op == FilterOperator.CONTAINS:
            if isinstance(value, list):
                return filter_value in value
            elif isinstance(value, str):
                return filter_value.lower() in value.lower()
            return False

        if op == FilterOperator.NOT_CONTAINS:
            if isinstance(value, list):
                return filter_value not in value
            elif isinstance(value, str):
                return filter_value.lower() not in value.lower()
            return True

        if op == FilterOperator.STARTS_WITH:
            return isinstance(value, str) and value.lower().startswith(filter_value.lower())

        if op == FilterOperator.ENDS_WITH:
            return isinstance(value, str) and value.lower().endswith(filter_value.lower())

        if op == FilterOperator.BETWEEN:
            if isinstance(filter_value, (list, tuple)) and len(filter_value) == 2:
                return filter_value[0] <= value <= filter_value[1]
            return False

        return False

    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Obtiene un valor anidado de un diccionario usando notación de punto"""
        parts = path.split('.')
        current = obj

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current

    def _sort_segments(self, segments: List[Dict], sort_by: str,
                       sort_order: SortOrder) -> List[Dict]:
        """Ordena los segmentos"""

        # Resolver alias
        field = self.field_aliases.get(sort_by, sort_by)

        def get_sort_key(seg):
            value = self._get_nested_value(seg, field)
            # Manejar None
            if value is None:
                return (1, 0)  # Poner None al final
            return (0, value)

        reverse = sort_order == SortOrder.DESC
        return sorted(segments, key=get_sort_key, reverse=reverse)

    def _filter_segment_fields(self, segment: Dict,
                               include: Optional[List[str]],
                               exclude: Optional[List[str]]) -> Dict:
        """Filtra los campos de un segmento"""

        if include:
            return {k: v for k, v in segment.items() if k in include}

        if exclude:
            return {k: v for k, v in segment.items() if k not in exclude}

        return segment

    # =========================================================
    # MÉTODOS DE BÚSQUEDA PREDEFINIDAS (shortcuts)
    # =========================================================

    def find_gold_segments(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra todos los segmentos GOLD"""
        return self.quick_search(segments, tier="GOLD", sort_by="score", sort_desc=True)

    def find_usable_segments(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra segmentos usables (GOLD + SILVER, excluyendo repetidos)"""
        return self.quick_search(
            segments,
            tiers=["GOLD", "SILVER"],
            exclude_repeated=True,
            sort_by="score",
            sort_desc=True
        )

    def find_segments_with_faces(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra segmentos con rostros detectados"""
        return self.quick_search(segments, has_faces=True)

    def find_key_moments(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra todos los momentos clave"""
        return self.quick_search(segments, is_key_moment=True)

    def find_best_takes(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra los mejores takes de cada grupo"""
        return self.quick_search(segments, is_best_take=True)

    def find_by_scene(self, segments: List[Dict], scene_id: int) -> List[Dict]:
        """Encuentra segmentos de una escena específica"""
        return self.quick_search(segments, scene_group=scene_id)

    def find_by_shot_type(self, segments: List[Dict], shot_type: str) -> List[Dict]:
        """Encuentra segmentos por tipo de toma"""
        return self.quick_search(segments, shot_type=shot_type)

    def find_by_framing(self, segments: List[Dict], framing: str) -> List[Dict]:
        """Encuentra segmentos por tipo de encuadre"""
        return self.quick_search(segments, framing_type=framing)

    def find_static_shots(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra tomas estáticas"""
        return self.quick_search(segments, shot_type="ESTATICA")

    def find_interview_candidates(self, segments: List[Dict]) -> List[Dict]:
        """Encuentra segmentos candidatos a entrevista"""
        return self.quick_search(
            segments,
            has_faces=True,
            has_tag="entrevista",
            sort_by="score",
            sort_desc=True
        )

    def find_segments_in_range(self, segments: List[Dict],
                               start_time: float, end_time: float) -> List[Dict]:
        """Encuentra segmentos dentro de un rango temporal"""
        filters = [
            Filter('start_time', FilterOperator.GREATER_EQUAL, start_time),
            Filter('end_time', FilterOperator.LESS_EQUAL, end_time),
        ]

        query = SearchQuery(
            filters=FilterGroup(filters=filters),
            sort_by='start_time'
        )

        return self.search(segments, query).segments


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def build_query_from_dict(query_dict: Dict) -> SearchQuery:
    """Construye una SearchQuery desde un diccionario (para API)"""

    filters = None
    if 'filters' in query_dict and query_dict['filters']:
        filters = _parse_filter_group(query_dict['filters'])

    sort_order = SortOrder.DESC if query_dict.get('sort_order') == 'desc' else SortOrder.ASC

    return SearchQuery(
        filters=filters,
        sort_by=query_dict.get('sort_by', 'index'),
        sort_order=sort_order,
        page=query_dict.get('page', 1),
        page_size=query_dict.get('page_size', 50),
        include_fields=query_dict.get('include_fields'),
        exclude_fields=query_dict.get('exclude_fields'),
    )


def _parse_filter_group(filter_dict: Dict) -> FilterGroup:
    """Parsea un diccionario de filtros"""

    operator = LogicalOperator.AND
    if filter_dict.get('operator') == 'or':
        operator = LogicalOperator.OR

    filters = []
    for f in filter_dict.get('filters', []):
        if 'filters' in f:  # Es un grupo anidado
            filters.append(_parse_filter_group(f))
        else:
            op = FilterOperator(f.get('operator', 'eq'))
            filters.append(Filter(
                field=f['field'],
                operator=op,
                value=f.get('value')
            ))

    return FilterGroup(filters=filters, operator=operator)


def get_search_summary(result: SearchResult) -> Dict:
    """Genera un resumen de los resultados de búsqueda"""

    if result.total_count == 0:
        return {
            'found': 0,
            'description': 'No se encontraron segmentos',
        }

    return {
        'found': result.total_count,
        'showing': len(result.segments),
        'page': result.page,
        'total_pages': result.total_pages,
        'description': f'{result.total_count} segmentos encontrados, '
                       f'mostrando página {result.page} de {result.total_pages}',
    }


def get_available_filters() -> Dict:
    """Retorna información sobre los filtros disponibles"""
    return {
        'fields': [
            {'name': 'tier', 'type': 'string', 'values': ['GOLD', 'SILVER', 'BRONZE', 'DISCARD']},
            {'name': 'score', 'type': 'number', 'range': [0, 10]},
            {'name': 'duration', 'type': 'number', 'description': 'Duración en segundos'},
            {'name': 'shot_type', 'type': 'string', 'values': ['ESTATICA', 'PANEO', 'TILT', 'TRACKING']},
            {'name': 'framing_type', 'type': 'string', 'description': 'Tipo de encuadre'},
            {'name': 'face_count', 'type': 'number', 'description': 'Número de rostros'},
            {'name': 'tags', 'type': 'array', 'description': 'Tags del segmento'},
            {'name': 'scene_group_id', 'type': 'number', 'description': 'ID de grupo de escena'},
            {'name': 'is_key_moment', 'type': 'boolean'},
            {'name': 'is_best_take', 'type': 'boolean'},
            {'name': 'is_repeated_take', 'type': 'boolean'},
        ],
        'operators': [op.value for op in FilterOperator],
        'logical_operators': ['and', 'or'],
        'sort_fields': ['index', 'score', 'duration', 'start_time', 'face_count'],
    }


if __name__ == "__main__":
    # Test básico
    engine = SearchEngine()
    print("SearchEngine inicializado correctamente")
    print(f"Campos buscables: {len(engine.searchable_fields)}")
    print(f"Alias disponibles: {engine.field_aliases}")
