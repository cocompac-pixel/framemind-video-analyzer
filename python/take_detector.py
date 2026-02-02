#!/usr/bin/env python3
"""
Take Detector Module v1.0
Detección de takes repetidos (múltiples intentos de la misma toma).

Funcionalidades:
- Identificación de segmentos que son repeticiones de la misma acción
- Agrupación de takes por similitud visual y de contenido
- Selección automática del mejor take de cada grupo
- Marcado de takes descartables
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
from collections import defaultdict


class TakeRelationType(Enum):
    """Tipo de relación entre takes"""
    SAME_TAKE = "same_take"           # Mismo take (idéntico)
    REPEATED_TAKE = "repeated_take"    # Take repetido (mismo contenido, diferente intento)
    SIMILAR_SHOT = "similar_shot"      # Toma similar pero no repetición
    DIFFERENT = "different"            # Diferente completamente


@dataclass
class TakeMatch:
    """Representa una coincidencia entre dos segmentos como takes repetidos"""
    segment_a: int
    segment_b: int
    similarity_score: float           # 0-1, qué tan similares son
    relation_type: TakeRelationType
    confidence: float                 # Confianza en la detección

    # Detalles de la comparación
    visual_similarity: float          # Similitud visual
    duration_similarity: float        # Similitud de duración
    framing_match: bool               # Mismo tipo de plano
    scene_group_match: bool           # Mismo grupo de escena

    def to_dict(self):
        return {
            'segment_a': self.segment_a,
            'segment_b': self.segment_b,
            'similarity_score': self.similarity_score,
            'relation_type': self.relation_type.value,
            'confidence': self.confidence,
            'visual_similarity': self.visual_similarity,
            'duration_similarity': self.duration_similarity,
            'framing_match': self.framing_match,
            'scene_group_match': self.scene_group_match,
        }


@dataclass
class TakeGroup:
    """Grupo de takes repetidos"""
    group_id: int
    takes: List[int]                  # IDs de segmentos en este grupo
    best_take: int                    # ID del mejor take
    take_count: int

    # Información del grupo
    avg_score: float
    best_score: float
    worst_score: float

    # Recomendación
    recommended_takes: List[int]      # Takes recomendados para usar
    discard_takes: List[int]          # Takes a descartar

    def to_dict(self):
        return {
            'group_id': self.group_id,
            'takes': self.takes,
            'best_take': self.best_take,
            'take_count': self.take_count,
            'avg_score': self.avg_score,
            'best_score': self.best_score,
            'worst_score': self.worst_score,
            'recommended_takes': self.recommended_takes,
            'discard_takes': self.discard_takes,
        }


@dataclass
class TakeDetectionResult:
    """Resultado del análisis de takes repetidos"""
    take_groups: List[TakeGroup]
    matches: List[TakeMatch]
    segment_to_group: Dict[int, int]  # Mapeo segmento -> grupo de takes
    total_groups: int
    total_repeated_takes: int
    potential_savings_duration: float  # Duración que se podría ahorrar

    def to_dict(self):
        return {
            'take_groups': [g.to_dict() for g in self.take_groups],
            'matches': [m.to_dict() for m in self.matches],
            'segment_to_group': self.segment_to_group,
            'total_groups': self.total_groups,
            'total_repeated_takes': self.total_repeated_takes,
            'potential_savings_duration': self.potential_savings_duration,
        }


class TakeDetector:
    """
    Detecta takes repetidos (múltiples intentos de la misma toma).
    """

    def __init__(self, config=None):
        self.config = config or {}

        # HOTFIX V5.1: Umbrales ajustados para reducir falsos positivos
        self.thresholds = {
            # Similitud para considerar take repetido
            # HOTFIX: Subido de 0.70 a 0.85 para reducir falsos positivos
            'repeat_similarity_threshold': 0.85,

            # Similitud mínima para considerar relacionados
            'related_similarity_threshold': 0.60,

            # Tolerancia de duración (ratio)
            'duration_tolerance': 0.25,  # HOTFIX: Reducido de 30% a 25%

            # HOTFIX: Gap temporal mínimo entre takes (segundos)
            # Takes reales tienen tiempo de setup entre ellos
            'min_temporal_gap': 10.0,

            # Pesos para cálculo de similitud
            # HOTFIX: Aumentado peso visual, reducido framing
            'weight_visual': 0.45,        # HOTFIX: 0.35 -> 0.45
            'weight_framing': 0.15,       # HOTFIX: 0.25 -> 0.15
            'weight_duration': 0.15,
            'weight_scene_group': 0.15,
            'weight_faces': 0.10,

            # Umbral de confianza
            'min_confidence': 0.70,       # HOTFIX: 0.60 -> 0.70
        }

    def detect_repeated_takes(self, segments: List[Dict]) -> TakeDetectionResult:
        """
        Analiza segmentos y detecta takes repetidos.

        Args:
            segments: Lista de segmentos con métricas

        Returns:
            TakeDetectionResult con grupos y matches
        """
        if not segments or len(segments) < 2:
            return TakeDetectionResult(
                take_groups=[],
                matches=[],
                segment_to_group={},
                total_groups=0,
                total_repeated_takes=0,
                potential_savings_duration=0
            )

        # Encontrar todas las coincidencias
        matches = self._find_all_matches(segments)

        # Agrupar takes repetidos
        groups, segment_to_group = self._group_repeated_takes(matches, segments)

        # Calcular duración potencial de ahorro
        savings = self._calculate_savings(groups, segments)

        return TakeDetectionResult(
            take_groups=groups,
            matches=matches,
            segment_to_group=segment_to_group,
            total_groups=len(groups),
            total_repeated_takes=sum(g.take_count - 1 for g in groups),
            potential_savings_duration=savings
        )

    def _find_all_matches(self, segments: List[Dict]) -> List[TakeMatch]:
        """Encuentra todas las coincidencias entre segmentos"""
        matches = []
        n = len(segments)

        for i in range(n):
            for j in range(i + 1, n):
                match = self._compare_segments(segments[i], segments[j], i, j)
                if match and match.similarity_score >= self.thresholds['related_similarity_threshold']:
                    matches.append(match)

        # Ordenar por similitud descendente
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return matches

    def _compare_segments(self, seg_a: Dict, seg_b: Dict,
                          idx_a: int, idx_b: int) -> Optional[TakeMatch]:
        """Compara dos segmentos y determina si son takes repetidos"""

        # HOTFIX V5.1: Validar gap temporal
        # Los takes repetidos reales tienen tiempo de setup entre ellos
        start_a = seg_a.get('start_time', 0)
        start_b = seg_b.get('start_time', 0)
        temporal_gap = abs(start_a - start_b)
        
        if temporal_gap < self.thresholds['min_temporal_gap']:
            # Demasiado cercanos para ser takes diferentes
            return None

        # Extraer métricas
        metrics_a = seg_a.get('metrics', {})
        metrics_b = seg_b.get('metrics', {})

        # 1. Similitud visual (basada en métricas de imagen)
        visual_sim = self._calculate_visual_similarity(metrics_a, metrics_b)

        # 2. Similitud de duración
        dur_a = seg_a.get('duration', 0)
        dur_b = seg_b.get('duration', 0)
        duration_sim = self._calculate_duration_similarity(dur_a, dur_b)

        # 3. Coincidencia de tipo de plano
        framing_a = seg_a.get('framing_type', 'DESCONOCIDO')
        framing_b = seg_b.get('framing_type', 'DESCONOCIDO')
        framing_match = framing_a == framing_b and framing_a != 'DESCONOCIDO'

        # 4. Coincidencia de grupo de escena
        group_a = seg_a.get('scene_group_id', -1)
        group_b = seg_b.get('scene_group_id', -1)
        scene_match = group_a == group_b and group_a >= 0

        # 5. Similitud de rostros
        face_sim = self._calculate_face_similarity(seg_a, seg_b)

        # Calcular similitud total ponderada
        weights = self.thresholds
        total_sim = (
            visual_sim * weights['weight_visual'] +
            (1.0 if framing_match else 0.0) * weights['weight_framing'] +
            duration_sim * weights['weight_duration'] +
            (1.0 if scene_match else 0.0) * weights['weight_scene_group'] +
            face_sim * weights['weight_faces']
        )

        # Normalizar al rango 0-1
        total_sim = min(1.0, max(0.0, total_sim))

        # Determinar tipo de relación
        if total_sim >= self.thresholds['repeat_similarity_threshold']:
            if total_sim >= 0.90:
                relation = TakeRelationType.SAME_TAKE
            else:
                relation = TakeRelationType.REPEATED_TAKE
        elif total_sim >= self.thresholds['related_similarity_threshold']:
            relation = TakeRelationType.SIMILAR_SHOT
        else:
            relation = TakeRelationType.DIFFERENT

        # Calcular confianza
        confidence = self._calculate_confidence(
            visual_sim, duration_sim, framing_match, scene_match
        )

        if confidence < self.thresholds['min_confidence']:
            return None

        return TakeMatch(
            segment_a=idx_a,
            segment_b=idx_b,
            similarity_score=total_sim,
            relation_type=relation,
            confidence=confidence,
            visual_similarity=visual_sim,
            duration_similarity=duration_sim,
            framing_match=framing_match,
            scene_group_match=scene_match
        )

    def _calculate_visual_similarity(self, metrics_a: Dict, metrics_b: Dict) -> float:
        """Calcula similitud visual entre dos conjuntos de métricas"""

        # Comparar brightness
        bright_a = metrics_a.get('brightness_mean', 0.5)
        bright_b = metrics_b.get('brightness_mean', 0.5)
        bright_sim = 1 - abs(bright_a - bright_b)

        # Comparar contraste
        contrast_a = metrics_a.get('contrast_mean', 0.5)
        contrast_b = metrics_b.get('contrast_mean', 0.5)
        contrast_sim = 1 - abs(contrast_a - contrast_b)

        # Comparar edge density
        edge_a = metrics_a.get('edge_density', 0.1)
        edge_b = metrics_b.get('edge_density', 0.1)
        edge_sim = 1 - min(1, abs(edge_a - edge_b) * 5)

        # Comparar sharpness (normalizado)
        sharp_a = metrics_a.get('sharpness_mean', 100) / 200
        sharp_b = metrics_b.get('sharpness_mean', 100) / 200
        sharp_sim = 1 - min(1, abs(sharp_a - sharp_b))

        # Comparar movimiento
        motion_a = metrics_a.get('motion_mean', 0)
        motion_b = metrics_b.get('motion_mean', 0)
        motion_sim = 1 - min(1, abs(motion_a - motion_b) / 5)

        # Promedio ponderado
        visual_sim = (
            bright_sim * 0.25 +
            contrast_sim * 0.15 +
            edge_sim * 0.20 +
            sharp_sim * 0.20 +
            motion_sim * 0.20
        )

        return float(visual_sim)

    def _calculate_duration_similarity(self, dur_a: float, dur_b: float) -> float:
        """Calcula similitud de duración"""
        if dur_a <= 0 or dur_b <= 0:
            return 0.0

        # Ratio de duración
        ratio = min(dur_a, dur_b) / max(dur_a, dur_b)

        # Convertir a similitud (1.0 si son iguales, menos si difieren)
        tolerance = self.thresholds['duration_tolerance']
        if ratio >= (1 - tolerance):
            return 1.0
        else:
            return ratio

    def _calculate_face_similarity(self, seg_a: Dict, seg_b: Dict) -> float:
        """Calcula similitud basada en rostros detectados"""

        face_a = seg_a.get('face_analysis', {})
        face_b = seg_b.get('face_analysis', {})

        # Si ninguno tiene rostros, son "similares" en ese aspecto
        has_faces_a = face_a.get('has_faces', False)
        has_faces_b = face_b.get('has_faces', False)

        if not has_faces_a and not has_faces_b:
            return 1.0

        if has_faces_a != has_faces_b:
            return 0.3  # Uno tiene rostros y otro no

        # Ambos tienen rostros - comparar cantidad y cobertura
        count_a = face_a.get('avg_face_count', 0)
        count_b = face_b.get('avg_face_count', 0)

        coverage_a = face_a.get('primary_face_coverage', 0)
        coverage_b = face_b.get('primary_face_coverage', 0)

        # Similitud de cantidad
        if max(count_a, count_b) > 0:
            count_sim = min(count_a, count_b) / max(count_a, count_b)
        else:
            count_sim = 1.0

        # Similitud de cobertura
        if max(coverage_a, coverage_b) > 0:
            coverage_sim = 1 - abs(coverage_a - coverage_b) / max(coverage_a, coverage_b)
        else:
            coverage_sim = 1.0

        return (count_sim * 0.5 + coverage_sim * 0.5)

    def _calculate_confidence(self, visual_sim: float, duration_sim: float,
                               framing_match: bool, scene_match: bool) -> float:
        """Calcula confianza en la detección"""

        # Base de confianza
        confidence = 0.3

        # Aumentar por similitud visual alta
        if visual_sim > 0.8:
            confidence += 0.25
        elif visual_sim > 0.6:
            confidence += 0.15

        # Aumentar por duración similar
        if duration_sim > 0.9:
            confidence += 0.15
        elif duration_sim > 0.7:
            confidence += 0.10

        # Bonus por coincidencia de framing
        if framing_match:
            confidence += 0.15

        # Bonus por mismo grupo de escena
        if scene_match:
            confidence += 0.15

        return min(1.0, confidence)

    def _group_repeated_takes(self, matches: List[TakeMatch],
                               segments: List[Dict]) -> Tuple[List[TakeGroup], Dict[int, int]]:
        """Agrupa segmentos en grupos de takes repetidos"""

        n_segments = len(segments)

        # Usar union-find para agrupar
        parent = list(range(n_segments))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Unir segmentos que son takes repetidos
        for match in matches:
            if match.relation_type in [TakeRelationType.SAME_TAKE, TakeRelationType.REPEATED_TAKE]:
                union(match.segment_a, match.segment_b)

        # Construir grupos
        group_members = defaultdict(list)
        for i in range(n_segments):
            root = find(i)
            group_members[root].append(i)

        # Filtrar solo grupos con más de un miembro (takes repetidos)
        groups = []
        segment_to_group = {}

        group_id = 0
        for root, members in group_members.items():
            if len(members) > 1:
                # CORREGIDO: Excluir segmentos garbage del grupo para best_take
                valid_members = [
                    i for i in members
                    if not segments[i].get('is_garbage') and
                       segments[i].get('tier') not in ['garbage', 'discard']
                ]

                # Calcular estadísticas del grupo
                # Si hay válidos, usar sus scores; si no, usar todos para estadísticas
                stats_members = valid_members if valid_members else members
                scores = [segments[i].get('score', 0) for i in stats_members]
                durations = [segments[i].get('duration', 0) for i in members]

                # CORREGIDO: Solo asignar best_take si hay miembros válidos (no garbage)
                # Si todos son garbage, best_take será -1 (ninguno)
                if valid_members:
                    best_idx = max(valid_members, key=lambda i: segments[i].get('score', 0))
                else:
                    best_idx = -1  # Ningún best_take si todos son garbage

                # Determinar takes a recomendar y descartar
                sorted_by_score = sorted(members, key=lambda i: segments[i].get('score', 0), reverse=True)
                recommended = sorted_by_score[:1]  # Solo el mejor
                discard = sorted_by_score[1:]      # El resto

                group = TakeGroup(
                    group_id=group_id,
                    takes=members,
                    best_take=best_idx,
                    take_count=len(members),
                    avg_score=sum(scores) / len(scores),
                    best_score=max(scores),
                    worst_score=min(scores),
                    recommended_takes=recommended,
                    discard_takes=discard
                )

                groups.append(group)

                for member in members:
                    segment_to_group[member] = group_id

                group_id += 1

        return groups, segment_to_group

    def _calculate_savings(self, groups: List[TakeGroup], segments: List[Dict]) -> float:
        """Calcula la duración potencial de ahorro descartando takes repetidos"""

        total_savings = 0
        for group in groups:
            # Sumar duración de takes a descartar
            for seg_idx in group.discard_takes:
                total_savings += segments[seg_idx].get('duration', 0)

        return total_savings

    def get_take_recommendations(self, result: TakeDetectionResult,
                                  segments: List[Dict]) -> Dict:
        """
        Genera recomendaciones sobre qué takes usar.
        """
        recommendations = {
            'use': [],      # Segmentos recomendados para usar
            'consider': [], # Segmentos a considerar
            'skip': [],     # Segmentos a saltar/descartar
        }

        # Segmentos que son parte de grupos de takes
        grouped_segments = set(result.segment_to_group.keys())

        for i, seg in enumerate(segments):
            if i in grouped_segments:
                group_id = result.segment_to_group[i]
                group = next(g for g in result.take_groups if g.group_id == group_id)

                if i in group.recommended_takes:
                    recommendations['use'].append({
                        'segment_idx': i,
                        'reason': f'Mejor take del grupo {group_id} ({group.take_count} takes)',
                        'score': seg.get('score', 0),
                        'alternatives': len(group.discard_takes)
                    })
                else:
                    recommendations['skip'].append({
                        'segment_idx': i,
                        'reason': f'Take repetido (grupo {group_id}), usar segmento {group.best_take}',
                        'score': seg.get('score', 0),
                        'better_alternative': group.best_take
                    })
            else:
                # Segmento único, usar según su tier
                tier = seg.get('tier', 'discard')
                if tier in ['gold', 'silver']:
                    recommendations['use'].append({
                        'segment_idx': i,
                        'reason': f'Take único ({tier})',
                        'score': seg.get('score', 0),
                    })
                elif tier == 'bronze':
                    recommendations['consider'].append({
                        'segment_idx': i,
                        'reason': 'Take único con calidad aceptable',
                        'score': seg.get('score', 0),
                    })
                else:
                    recommendations['skip'].append({
                        'segment_idx': i,
                        'reason': 'Calidad insuficiente',
                        'score': seg.get('score', 0),
                    })

        return recommendations


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def get_take_summary(result: TakeDetectionResult) -> Dict:
    """Genera un resumen del análisis de takes"""
    if not result.take_groups:
        return {
            'total_groups': 0,
            'total_repeated_takes': 0,
            'potential_savings_seconds': 0,
            'recommendation': 'No se encontraron takes repetidos',
        }

    return {
        'total_groups': result.total_groups,
        'total_repeated_takes': result.total_repeated_takes,
        'potential_savings_seconds': round(result.potential_savings_duration, 1),
        'avg_takes_per_group': round(
            sum(g.take_count for g in result.take_groups) / len(result.take_groups), 1
        ),
        'recommendation': f'Se pueden eliminar {result.total_repeated_takes} takes repetidos, '
                          f'ahorrando {result.potential_savings_duration:.1f}s',
    }


def format_take_groups_for_display(result: TakeDetectionResult,
                                    segments: List[Dict]) -> List[Dict]:
    """Formatea grupos de takes para mostrar en UI"""
    formatted = []

    for group in result.take_groups:
        takes_info = []
        for seg_idx in group.takes:
            seg = segments[seg_idx]
            takes_info.append({
                'segment_idx': seg_idx,
                'score': seg.get('score', 0),
                'tier': seg.get('tier', 'unknown'),
                'duration': seg.get('duration', 0),
                'is_best': seg_idx == group.best_take,
                'recommendation': 'usar' if seg_idx == group.best_take else 'descartar'
            })

        formatted.append({
            'group_id': group.group_id,
            'take_count': group.take_count,
            'best_take': group.best_take,
            'takes': takes_info,
            'summary': f'{group.take_count} takes, mejor: segmento {group.best_take}'
        })

    return formatted


if __name__ == "__main__":
    # Test básico
    detector = TakeDetector()
    print("TakeDetector inicializado correctamente")
    print(f"Thresholds: {detector.thresholds}")
