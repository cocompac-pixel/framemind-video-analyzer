#!/usr/bin/env python3
"""
Context Tagger Module v1.0
Etiquetado contextual automático de segmentos de video.

Funcionalidades:
- Tags automáticos basados en contenido visual
- Detección de momentos clave (key moments)
- Clasificación de contexto (interior/exterior, día/noche, etc.)
- Detección de actividad/acción
- Metadata enriquecida para cada segmento
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
import numpy as np


class TagCategory(Enum):
    """Categorías de tags"""
    CONTENT = "content"           # Qué hay en el frame (personas, objetos)
    CONTEXT = "context"           # Contexto (interior, exterior, día, noche)
    ACTIVITY = "activity"         # Actividad detectada
    QUALITY = "quality"           # Tags de calidad técnica
    COMPOSITION = "composition"   # Composición visual
    MOOD = "mood"                 # Tono/atmósfera
    KEY_MOMENT = "key_moment"     # Momentos clave


class ContentTag(Enum):
    """Tags de contenido"""
    # Personas
    PERSON = "persona"
    MULTIPLE_PEOPLE = "varias_personas"
    FACE_VISIBLE = "rostro_visible"
    FACE_CLOSE_UP = "primer_plano_rostro"
    INTERVIEW = "entrevista"

    # Encuadre
    WIDE_SHOT = "plano_general"
    MEDIUM_SHOT = "plano_medio"
    CLOSE_UP = "primer_plano"
    DETAIL_SHOT = "plano_detalle"

    # Movimiento
    STATIC = "estatico"
    MOVEMENT = "con_movimiento"
    CAMERA_MOTION = "movimiento_camara"
    ACTION = "accion"


class ContextTag(Enum):
    """Tags de contexto ambiental"""
    # Iluminación
    BRIGHT = "iluminado"
    DARK = "oscuro"
    HIGH_CONTRAST = "alto_contraste"
    LOW_CONTRAST = "bajo_contraste"
    BACKLIT = "contraluz"

    # Ambiente (inferido)
    POSSIBLY_INTERIOR = "posible_interior"
    POSSIBLY_EXTERIOR = "posible_exterior"


class QualityTag(Enum):
    """Tags de calidad técnica"""
    SHARP = "nitido"
    SOFT_FOCUS = "enfoque_suave"
    BLURRY = "borroso"
    WELL_EXPOSED = "bien_expuesto"
    OVEREXPOSED = "sobreexpuesto"
    UNDEREXPOSED = "subexpuesto"
    STABLE = "estable"
    SHAKY = "tembloroso"
    IN_FOCUS = "en_foco"
    OUT_OF_FOCUS = "fuera_de_foco"


class KeyMomentType(Enum):
    """Tipos de momentos clave"""
    BEST_QUALITY = "mejor_calidad"
    BEST_OF_SCENE = "mejor_de_escena"
    UNIQUE_CONTENT = "contenido_unico"
    CLIMAX = "climax"
    TRANSITION = "transicion"
    OPENING = "apertura"
    CLOSING = "cierre"


@dataclass
class Tag:
    """Representa un tag individual"""
    name: str
    category: TagCategory
    confidence: float = 1.0
    source: str = "auto"  # auto, manual, inferred

    def to_dict(self):
        return {
            'name': self.name,
            'category': self.category.value,
            'confidence': self.confidence,
            'source': self.source,
        }


@dataclass
class KeyMoment:
    """Representa un momento clave detectado"""
    segment_idx: int
    moment_type: KeyMomentType
    reason: str
    score: float
    timestamp: float = 0.0

    def to_dict(self):
        return {
            'segment_idx': self.segment_idx,
            'moment_type': self.moment_type.value,
            'reason': self.reason,
            'score': self.score,
            'timestamp': self.timestamp,
        }


@dataclass
class SegmentTags:
    """Tags completos de un segmento"""
    segment_idx: int
    tags: List[Tag]
    key_moment: Optional[KeyMoment] = None
    auto_description: str = ""

    def to_dict(self):
        return {
            'segment_idx': self.segment_idx,
            'tags': [t.to_dict() for t in self.tags],
            'tag_names': [t.name for t in self.tags],
            'key_moment': self.key_moment.to_dict() if self.key_moment else None,
            'auto_description': self.auto_description,
            'tag_count': len(self.tags),
        }

    def get_tags_by_category(self, category: TagCategory) -> List[Tag]:
        return [t for t in self.tags if t.category == category]


@dataclass
class TaggingResult:
    """Resultado completo del etiquetado"""
    segment_tags: List[SegmentTags]
    key_moments: List[KeyMoment]
    all_tags_used: Set[str]
    tag_frequency: Dict[str, int]

    def to_dict(self):
        return {
            'segment_tags': [st.to_dict() for st in self.segment_tags],
            'key_moments': [km.to_dict() for km in self.key_moments],
            'all_tags_used': list(self.all_tags_used),
            'tag_frequency': self.tag_frequency,
            'total_segments': len(self.segment_tags),
            'total_key_moments': len(self.key_moments),
        }


class ContextTagger:
    """
    Genera tags contextuales automáticos para segmentos de video.
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Umbrales para clasificación
        self.thresholds = {
            # Brillo
            'bright_threshold': 0.65,
            'dark_threshold': 0.35,

            # Contraste
            'high_contrast_threshold': 0.6,
            'low_contrast_threshold': 0.3,

            # Movimiento
            'static_motion_max': 1.0,
            'high_motion_min': 5.0,

            # Enfoque
            'sharp_threshold': 100,
            'blurry_threshold': 50,

            # Rostros
            'face_close_up_coverage': 0.15,
            'interview_face_coverage': 0.08,

            # Calidad para key moments
            'key_moment_min_score': 7.5,
        }

    def tag_segments(self, segments: List[Dict]) -> TaggingResult:
        """
        Genera tags para todos los segmentos.

        Args:
            segments: Lista de segmentos con métricas

        Returns:
            TaggingResult con tags de todos los segmentos
        """
        if not segments:
            return TaggingResult(
                segment_tags=[],
                key_moments=[],
                all_tags_used=set(),
                tag_frequency={}
            )

        segment_tags = []
        all_tags = set()
        tag_counts = {}

        for i, seg in enumerate(segments):
            tags = self._generate_tags_for_segment(seg, i, segments)
            segment_tags.append(tags)

            # Acumular tags
            for tag in tags.tags:
                all_tags.add(tag.name)
                tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1

        # Detectar momentos clave
        key_moments = self._detect_key_moments(segments, segment_tags)

        # Asignar key_moments a segment_tags
        for km in key_moments:
            if km.segment_idx < len(segment_tags):
                segment_tags[km.segment_idx].key_moment = km

        return TaggingResult(
            segment_tags=segment_tags,
            key_moments=key_moments,
            all_tags_used=all_tags,
            tag_frequency=tag_counts
        )

    def _generate_tags_for_segment(self, segment: Dict, idx: int,
                                    all_segments: List[Dict]) -> SegmentTags:
        """Genera todos los tags para un segmento"""
        tags = []

        # 1. Tags de contenido (personas, encuadre)
        tags.extend(self._generate_content_tags(segment))

        # 2. Tags de contexto (iluminación, ambiente)
        tags.extend(self._generate_context_tags(segment))

        # 3. Tags de calidad técnica
        tags.extend(self._generate_quality_tags(segment))

        # 4. Tags de composición
        tags.extend(self._generate_composition_tags(segment))

        # Generar descripción automática
        description = self._generate_auto_description(segment, tags)

        return SegmentTags(
            segment_idx=idx,
            tags=tags,
            auto_description=description
        )

    def _generate_content_tags(self, segment: Dict) -> List[Tag]:
        """Genera tags de contenido"""
        tags = []
        metrics = segment.get('metrics', {})
        face_analysis = segment.get('face_analysis', {})
        framing = segment.get('framing', {})

        # Rostros/Personas
        face_count = face_analysis.get('avg_face_count', 0)
        face_coverage = face_analysis.get('primary_face_coverage', 0)

        if face_count > 0:
            tags.append(Tag(
                name=ContentTag.PERSON.value,
                category=TagCategory.CONTENT,
                confidence=min(1.0, face_count)
            ))

            if face_count >= 2:
                tags.append(Tag(
                    name=ContentTag.MULTIPLE_PEOPLE.value,
                    category=TagCategory.CONTENT,
                    confidence=min(1.0, face_count / 2)
                ))

            tags.append(Tag(
                name=ContentTag.FACE_VISIBLE.value,
                category=TagCategory.CONTENT
            ))

            if face_coverage >= self.thresholds['face_close_up_coverage']:
                tags.append(Tag(
                    name=ContentTag.FACE_CLOSE_UP.value,
                    category=TagCategory.CONTENT,
                    confidence=min(1.0, face_coverage / 0.25)
                ))

            # Detectar posible entrevista
            if (face_coverage >= self.thresholds['interview_face_coverage'] and
                metrics.get('motion_mean', 10) < 2.0):
                tags.append(Tag(
                    name=ContentTag.INTERVIEW.value,
                    category=TagCategory.CONTENT,
                    confidence=0.7,
                    source="inferred"
                ))

        # Tipo de plano (desde framing)
        framing_type = segment.get('framing_type', '')
        if 'WIDE' in framing_type or 'GENERAL' in framing_type:
            tags.append(Tag(name=ContentTag.WIDE_SHOT.value, category=TagCategory.CONTENT))
        elif 'MEDIUM' in framing_type or 'MEDIO' in framing_type:
            tags.append(Tag(name=ContentTag.MEDIUM_SHOT.value, category=TagCategory.CONTENT))
        elif 'CLOSE' in framing_type or 'PRIMER' in framing_type:
            tags.append(Tag(name=ContentTag.CLOSE_UP.value, category=TagCategory.CONTENT))
        elif 'DETAIL' in framing_type or 'DETALLE' in framing_type:
            tags.append(Tag(name=ContentTag.DETAIL_SHOT.value, category=TagCategory.CONTENT))

        # Movimiento
        motion = metrics.get('motion_mean', 0)
        shot_type = segment.get('shot_type', '')

        if motion < self.thresholds['static_motion_max']:
            tags.append(Tag(name=ContentTag.STATIC.value, category=TagCategory.CONTENT))
        elif motion > self.thresholds['high_motion_min']:
            tags.append(Tag(
                name=ContentTag.ACTION.value,
                category=TagCategory.CONTENT,
                confidence=min(1.0, motion / 10)
            ))
        else:
            tags.append(Tag(name=ContentTag.MOVEMENT.value, category=TagCategory.CONTENT))

        if shot_type in ['PANEO', 'TILT', 'TRACKING']:
            tags.append(Tag(name=ContentTag.CAMERA_MOTION.value, category=TagCategory.CONTENT))

        return tags

    def _generate_context_tags(self, segment: Dict) -> List[Tag]:
        """Genera tags de contexto ambiental"""
        tags = []
        metrics = segment.get('metrics', {})

        # Brillo
        brightness = metrics.get('brightness_mean', 0.5)

        if brightness >= self.thresholds['bright_threshold']:
            tags.append(Tag(
                name=ContextTag.BRIGHT.value,
                category=TagCategory.CONTEXT,
                confidence=min(1.0, (brightness - 0.5) * 2)
            ))
            # Inferir posible exterior
            if brightness > 0.7:
                tags.append(Tag(
                    name=ContextTag.POSSIBLY_EXTERIOR.value,
                    category=TagCategory.CONTEXT,
                    confidence=0.5,
                    source="inferred"
                ))
        elif brightness <= self.thresholds['dark_threshold']:
            tags.append(Tag(
                name=ContextTag.DARK.value,
                category=TagCategory.CONTEXT,
                confidence=min(1.0, (0.5 - brightness) * 2)
            ))
            # Inferir posible interior
            tags.append(Tag(
                name=ContextTag.POSSIBLY_INTERIOR.value,
                category=TagCategory.CONTEXT,
                confidence=0.4,
                source="inferred"
            ))

        # Contraste
        contrast = metrics.get('contrast_mean', 0.5)

        if contrast >= self.thresholds['high_contrast_threshold']:
            tags.append(Tag(
                name=ContextTag.HIGH_CONTRAST.value,
                category=TagCategory.CONTEXT
            ))
        elif contrast <= self.thresholds['low_contrast_threshold']:
            tags.append(Tag(
                name=ContextTag.LOW_CONTRAST.value,
                category=TagCategory.CONTEXT
            ))

        # Detectar contraluz (alto contraste + siluetas oscuras en fondo brillante)
        if brightness > 0.6 and contrast > 0.5:
            edge_density = metrics.get('edge_density', 0)
            if edge_density < 0.15:  # Pocas líneas = posible silueta
                tags.append(Tag(
                    name=ContextTag.BACKLIT.value,
                    category=TagCategory.CONTEXT,
                    confidence=0.6,
                    source="inferred"
                ))

        return tags

    def _generate_quality_tags(self, segment: Dict) -> List[Tag]:
        """Genera tags de calidad técnica"""
        tags = []
        metrics = segment.get('metrics', {})

        # Nitidez/Enfoque
        sharpness = metrics.get('sharpness_mean', 100)

        if sharpness >= self.thresholds['sharp_threshold']:
            tags.append(Tag(
                name=QualityTag.SHARP.value,
                category=TagCategory.QUALITY
            ))
            tags.append(Tag(
                name=QualityTag.IN_FOCUS.value,
                category=TagCategory.QUALITY
            ))
        elif sharpness <= self.thresholds['blurry_threshold']:
            tags.append(Tag(
                name=QualityTag.BLURRY.value,
                category=TagCategory.QUALITY
            ))
            tags.append(Tag(
                name=QualityTag.OUT_OF_FOCUS.value,
                category=TagCategory.QUALITY
            ))
        else:
            tags.append(Tag(
                name=QualityTag.SOFT_FOCUS.value,
                category=TagCategory.QUALITY
            ))

        # Exposición (basado en brillo)
        brightness = metrics.get('brightness_mean', 0.5)

        if 0.35 <= brightness <= 0.70:
            tags.append(Tag(
                name=QualityTag.WELL_EXPOSED.value,
                category=TagCategory.QUALITY
            ))
        elif brightness > 0.80:
            tags.append(Tag(
                name=QualityTag.OVEREXPOSED.value,
                category=TagCategory.QUALITY
            ))
        elif brightness < 0.20:
            tags.append(Tag(
                name=QualityTag.UNDEREXPOSED.value,
                category=TagCategory.QUALITY
            ))

        # Estabilidad
        motion_std = metrics.get('motion_std', 0)
        shot_type = segment.get('shot_type', '')

        if shot_type == 'ESTATICA' or motion_std < 0.5:
            tags.append(Tag(
                name=QualityTag.STABLE.value,
                category=TagCategory.QUALITY
            ))
        elif motion_std > 3.0 or 'SHAKY' in shot_type.upper():
            tags.append(Tag(
                name=QualityTag.SHAKY.value,
                category=TagCategory.QUALITY
            ))

        return tags

    def _generate_composition_tags(self, segment: Dict) -> List[Tag]:
        """Genera tags de composición visual"""
        tags = []
        metrics = segment.get('metrics', {})
        face_analysis = segment.get('face_analysis', {})

        # Podríamos expandir esto con detección de regla de tercios,
        # balance visual, etc. Por ahora, tags básicos.

        edge_density = metrics.get('edge_density', 0.1)

        if edge_density > 0.25:
            tags.append(Tag(
                name="complejo_visualmente",
                category=TagCategory.COMPOSITION,
                confidence=min(1.0, edge_density / 0.4)
            ))
        elif edge_density < 0.08:
            tags.append(Tag(
                name="minimalista",
                category=TagCategory.COMPOSITION,
                confidence=0.7
            ))

        # Rostros centrados/bien encuadrados
        if face_analysis.get('has_faces', False):
            framing_issues = face_analysis.get('avg_framing_issues', 0)
            if framing_issues == 0:
                tags.append(Tag(
                    name="rostro_bien_encuadrado",
                    category=TagCategory.COMPOSITION
                ))

        return tags

    def _detect_key_moments(self, segments: List[Dict],
                            segment_tags: List[SegmentTags]) -> List[KeyMoment]:
        """Detecta momentos clave en el video"""
        key_moments = []

        if not segments:
            return key_moments

        # 1. Mejor calidad general
        # SOLO marcar como key moment si:
        # - NO pertenece a un grupo de takes repetidos (ya tienen el badge de alternativas)
        # - NO es garbage (pre_roll, post_roll, etc.)
        # IMPORTANTE: Excluir TODO segmento con take_group_id, no solo is_repeated_take
        # porque is_best_take también pertenece a un grupo y no debe tener estrella
        valid_indices = [
            i for i in range(len(segments))
            if not segments[i].get('is_garbage') and
               segments[i].get('take_group_id') is None and  # CORREGIDO: excluir TODOS los que pertenecen a grupos
               segments[i].get('tier') not in ['garbage', 'discard']
        ]

        if valid_indices:
            best_score_idx = max(valid_indices, key=lambda i: segments[i].get('score', 0))
            best_score = segments[best_score_idx].get('score', 0)

            if best_score >= self.thresholds['key_moment_min_score']:
                key_moments.append(KeyMoment(
                    segment_idx=best_score_idx,
                    moment_type=KeyMomentType.BEST_QUALITY,
                    reason=f"Mejor puntuación del proyecto ({best_score:.1f})",
                    score=best_score,
                    timestamp=segments[best_score_idx].get('start_time', 0)
                ))

        # 2. Mejor de cada grupo de escena - DESHABILITADO
        # Esta lógica marcaba el mejor de cada grupo repetido como key moment,
        # pero eso es redundante con is_best_take que ya indica cuál conservar.
        # Las estrellas solo deben ser para contenido ÚNICO y destacado.
        #
        # scene_groups = {}
        # for i, seg in enumerate(segments):
        #     group_id = seg.get('scene_group_id', -1)
        #     if group_id >= 0:
        #         if group_id not in scene_groups:
        #             scene_groups[group_id] = []
        #         scene_groups[group_id].append((i, seg.get('score', 0)))
        #
        # for group_id, members in scene_groups.items():
        #     if len(members) > 1:
        #         best_in_group = max(members, key=lambda x: x[1])
        #         idx, score = best_in_group
        #         if score >= self.thresholds['key_moment_min_score'] - 0.5:
        #             # Evitar duplicar si ya es el mejor global
        #             if idx != best_score_idx:
        #                 key_moments.append(KeyMoment(
        #                     segment_idx=idx,
        #                     moment_type=KeyMomentType.BEST_OF_SCENE,
        #                     reason=f"Mejor toma de la escena {group_id + 1}",
        #                     score=score,
        #                     timestamp=segments[idx].get('start_time', 0)
        #                 ))

        # 3. Contenido único (segmentos que no tienen repeticiones)
        for i, seg in enumerate(segments):
            # CORREGIDO: Excluir garbage de key moments
            if seg.get('is_garbage') or seg.get('tier') in ['garbage', 'discard']:
                continue

            take_group = seg.get('take_group_id')

            # Si no pertenece a ningún grupo de takes y tiene buena calidad
            if take_group is None and seg.get('score', 0) >= 7.0:
                # Verificar que es contenido interesante
                has_face = seg.get('face_analysis', {}).get('has_faces', False)
                if has_face or seg.get('framing_type', '') not in ['DESCONOCIDO', '']:
                    key_moments.append(KeyMoment(
                        segment_idx=i,
                        moment_type=KeyMomentType.UNIQUE_CONTENT,
                        reason="Toma única sin repeticiones",
                        score=seg.get('score', 0),
                        timestamp=seg.get('start_time', 0)
                    ))

        # 4. Apertura y cierre - DESHABILITADO
        # Esta lógica marcaba automáticamente el primer y último segmento como key moments,
        # lo cual generaba demasiadas estrellas sin valor real para el editor.
        # Solo deben ser key moments los segmentos con calidad excepcional (mejor_calidad)
        # o los mejores takes de una escena repetida (best_of_scene).
        #
        # if len(segments) >= 2:
        #     # Apertura: primer segmento con calidad aceptable
        #     for i, seg in enumerate(segments[:3]):  # Primeros 3
        #         if seg.get('score', 0) >= 6.0 and seg.get('tier', '') != 'DISCARD':
        #             key_moments.append(KeyMoment(
        #                 segment_idx=i,
        #                 moment_type=KeyMomentType.OPENING,
        #                 reason="Posible toma de apertura",
        #                 score=seg.get('score', 0),
        #                 timestamp=seg.get('start_time', 0)
        #             ))
        #             break
        #
        #     # Cierre: último segmento con calidad aceptable
        #     for i in range(len(segments) - 1, max(0, len(segments) - 4), -1):
        #         seg = segments[i]
        #         if seg.get('score', 0) >= 6.0 and seg.get('tier', '') != 'DISCARD':
        #             key_moments.append(KeyMoment(
        #                 segment_idx=i,
        #                 moment_type=KeyMomentType.CLOSING,
        #                 reason="Posible toma de cierre",
        #                 score=seg.get('score', 0),
        #                 timestamp=seg.get('start_time', 0)
        #             ))
        #             break

        # Ordenar por timestamp
        key_moments.sort(key=lambda km: km.timestamp)

        # Limitar duplicados (un segmento puede ser key moment por una sola razón)
        seen_segments = set()
        unique_moments = []
        for km in key_moments:
            if km.segment_idx not in seen_segments:
                unique_moments.append(km)
                seen_segments.add(km.segment_idx)

        return unique_moments

    def _generate_auto_description(self, segment: Dict, tags: List[Tag]) -> str:
        """Genera una descripción automática del segmento"""
        parts = []

        # Tipo de plano
        framing_display = segment.get('framing_type_display', '')
        if framing_display:
            parts.append(framing_display)

        # Personas
        face_count = segment.get('face_analysis', {}).get('avg_face_count', 0)
        if face_count >= 2:
            parts.append(f"con {int(face_count)} personas")
        elif face_count >= 1:
            parts.append("con persona")

        # Movimiento
        shot_type = segment.get('shot_type', '')
        if shot_type == 'PANEO':
            parts.append("con paneo")
        elif shot_type == 'TILT':
            parts.append("con tilt")
        elif shot_type == 'TRACKING':
            parts.append("con seguimiento")
        elif shot_type == 'ESTATICA':
            parts.append("estática")

        # Calidad
        tier = segment.get('tier', '')
        if tier == 'GOLD':
            parts.append("(excelente)")
        elif tier == 'SILVER':
            parts.append("(buena)")
        elif tier == 'DISCARD':
            parts.append("(descartable)")

        return ", ".join(parts) if parts else "Segmento sin clasificar"

    def get_segments_by_tag(self, result: TaggingResult, tag_name: str) -> List[int]:
        """Obtiene índices de segmentos que tienen un tag específico"""
        return [
            st.segment_idx
            for st in result.segment_tags
            if any(t.name == tag_name for t in st.tags)
        ]

    def get_tag_statistics(self, result: TaggingResult) -> Dict:
        """Genera estadísticas de tags"""
        if not result.segment_tags:
            return {
                'total_tags': 0,
                'unique_tags': 0,
                'avg_tags_per_segment': 0,
                'most_common': [],
                'by_category': {},
            }

        # Contar por categoría
        by_category = {}
        for st in result.segment_tags:
            for tag in st.tags:
                cat = tag.category.value
                if cat not in by_category:
                    by_category[cat] = {}
                by_category[cat][tag.name] = by_category[cat].get(tag.name, 0) + 1

        # Tags más comunes
        most_common = sorted(
            result.tag_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        total_tags = sum(len(st.tags) for st in result.segment_tags)

        return {
            'total_tags': total_tags,
            'unique_tags': len(result.all_tags_used),
            'avg_tags_per_segment': total_tags / len(result.segment_tags),
            'most_common': [{'tag': t, 'count': c} for t, c in most_common],
            'by_category': by_category,
            'key_moments_count': len(result.key_moments),
        }


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def get_tagging_summary(result: TaggingResult) -> Dict:
    """Genera un resumen del etiquetado"""
    if not result.segment_tags:
        return {
            'total_segments': 0,
            'total_tags': 0,
            'key_moments': 0,
            'description': 'Sin segmentos para etiquetar',
        }

    total_tags = sum(len(st.tags) for st in result.segment_tags)

    return {
        'total_segments': len(result.segment_tags),
        'total_tags': total_tags,
        'unique_tags': len(result.all_tags_used),
        'key_moments': len(result.key_moments),
        'avg_tags_per_segment': round(total_tags / len(result.segment_tags), 1),
        'description': f'{len(result.segment_tags)} segmentos etiquetados con {total_tags} tags, '
                       f'{len(result.key_moments)} momentos clave detectados',
    }


def format_tags_for_display(segment_tags: SegmentTags) -> Dict:
    """Formatea tags de un segmento para mostrar en UI"""
    tags_by_category = {}

    for tag in segment_tags.tags:
        cat = tag.category.value
        if cat not in tags_by_category:
            tags_by_category[cat] = []
        tags_by_category[cat].append({
            'name': tag.name,
            'confidence': tag.confidence,
        })

    return {
        'segment_idx': segment_tags.segment_idx,
        'tags_by_category': tags_by_category,
        'all_tags': [t.name for t in segment_tags.tags],
        'description': segment_tags.auto_description,
        'is_key_moment': segment_tags.key_moment is not None,
        'key_moment_type': segment_tags.key_moment.moment_type.value if segment_tags.key_moment else None,
    }


if __name__ == "__main__":
    # Test básico
    tagger = ContextTagger()
    print("ContextTagger inicializado correctamente")
    print(f"Thresholds: {tagger.thresholds}")
