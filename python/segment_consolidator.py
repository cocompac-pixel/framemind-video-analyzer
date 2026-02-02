"""
Segment Consolidator - Post-procesamiento para consolidar micro-segmentos
en clips más útiles para edición.

Funcionalidades:
1. Duración mínima de segmento (2 segundos por defecto)
2. Fusión inteligente de segmentos similares consecutivos
3. Preservación de atributos especiales (key moments, best takes, etc.)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from copy import deepcopy


# Configuración por defecto
DEFAULT_MIN_DURATION = 2.0  # segundos
DEFAULT_MERGE_SIMILAR = True


@dataclass
class ConsolidationConfig:
    """Configuración para la consolidación de segmentos"""
    min_duration: float = DEFAULT_MIN_DURATION
    merge_similar: bool = DEFAULT_MERGE_SIMILAR
    # Tolerancia para considerar scores "similares" (diferencia máxima)
    score_tolerance: float = 2.0
    # Permitir fusionar diferentes tiers si son adyacentes (gold+silver)
    allow_tier_merge: bool = True
    # Tiers que pueden fusionarse entre sí
    mergeable_tiers: tuple = ('gold', 'silver')


class SegmentConsolidator:
    """
    Consolida segmentos de video para producir clips más útiles para edición.
    """

    def __init__(self, config: Optional[ConsolidationConfig] = None):
        self.config = config or ConsolidationConfig()

    def consolidate(self, segments: List[Dict[str, Any]], video_duration: float = None) -> List[Dict[str, Any]]:
        """
        Procesa una lista de segmentos y devuelve una versión consolidada.

        Args:
            segments: Lista de segmentos del análisis original
            video_duration: Duración total del video (opcional, para validación)

        Returns:
            Lista de segmentos consolidados
        """
        if not segments:
            return []

        # Paso 1: Ordenar por tiempo de inicio
        sorted_segments = sorted(segments, key=lambda s: s.get('start_time', 0))

        # Paso 2: Fusionar segmentos similares consecutivos
        if self.config.merge_similar:
            sorted_segments = self._merge_similar_segments(sorted_segments)

        # Paso 3: Eliminar/absorber micro-segmentos
        consolidated = self._handle_micro_segments(sorted_segments)

        # Paso 4: Recalcular estadísticas agregadas
        consolidated = self._recalculate_stats(consolidated)

        return consolidated

    def _can_merge(self, seg1: Dict, seg2: Dict) -> bool:
        """
        Determina si dos segmentos pueden fusionarse.

        Criterios:
        - Mismo tipo de plano (shot_type)
        - Tier compatible (mismo tier o ambos en mergeable_tiers)
        - Scores similares (dentro de tolerancia)
        - Sin atributos especiales conflictivos
        """
        # Deben ser consecutivos (seg2 empieza donde seg1 termina)
        if abs(seg2.get('start_time', 0) - seg1.get('end_time', 0)) > 0.1:
            return False

        # Mismo tipo de plano
        if seg1.get('shot_type') != seg2.get('shot_type'):
            return False

        # Verificar tiers
        tier1 = seg1.get('tier', 'discard')
        tier2 = seg2.get('tier', 'discard')

        if tier1 == tier2:
            pass  # OK, mismo tier
        elif self.config.allow_tier_merge:
            # Permitir fusión de tiers compatibles
            if not (tier1 in self.config.mergeable_tiers and tier2 in self.config.mergeable_tiers):
                return False
        else:
            return False

        # No fusionar si alguno es garbage
        if tier1 == 'garbage' or tier2 == 'garbage':
            return False

        # Verificar scores similares
        score1 = seg1.get('score', 0)
        score2 = seg2.get('score', 0)
        if abs(score1 - score2) > self.config.score_tolerance:
            return False

        # No fusionar si tienen atributos especiales diferentes
        # (ej: uno es key_moment y otro no)
        special_attrs = ['is_key_moment', 'is_best_take', 'is_garbage']
        for attr in special_attrs:
            if seg1.get(attr) != seg2.get(attr):
                # Excepción: si ninguno tiene el atributo especial, OK
                if seg1.get(attr) or seg2.get(attr):
                    return False

        return True

    def _merge_two_segments(self, seg1: Dict, seg2: Dict) -> Dict:
        """
        Fusiona dos segmentos en uno solo.
        """
        merged = deepcopy(seg1)

        # Extender tiempo
        merged['end_time'] = seg2['end_time']
        merged['duration'] = merged['end_time'] - merged['start_time']

        # Promedio de scores
        score1 = seg1.get('score', 0)
        score2 = seg2.get('score', 0)
        dur1 = seg1.get('end_time', 0) - seg1.get('start_time', 0)
        dur2 = seg2.get('end_time', 0) - seg2.get('start_time', 0)

        # Score ponderado por duración
        if dur1 + dur2 > 0:
            merged['score'] = (score1 * dur1 + score2 * dur2) / (dur1 + dur2)

        # Tier: usar el mejor de los dos
        tier_priority = {'gold': 4, 'silver': 3, 'bronze': 2, 'discard': 1, 'garbage': 0}
        tier1 = seg1.get('tier', 'discard')
        tier2 = seg2.get('tier', 'discard')
        merged['tier'] = tier1 if tier_priority.get(tier1, 0) >= tier_priority.get(tier2, 0) else tier2

        # Combinar tags
        tags1 = set(seg1.get('tags', []))
        tags2 = set(seg2.get('tags', []))
        merged['tags'] = list(tags1 | tags2)

        # Preservar atributos especiales si alguno los tiene
        for attr in ['is_key_moment', 'is_best_take', 'key_moment_type', 'key_moment_reason']:
            if seg1.get(attr) or seg2.get(attr):
                merged[attr] = seg1.get(attr) or seg2.get(attr)

        # Métricas: promediar
        if 'metrics' in seg1 and 'metrics' in seg2:
            merged_metrics = {}
            all_keys = set(seg1.get('metrics', {}).keys()) | set(seg2.get('metrics', {}).keys())
            for key in all_keys:
                val1 = seg1.get('metrics', {}).get(key, 0)
                val2 = seg2.get('metrics', {}).get(key, 0)
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    merged_metrics[key] = (val1 * dur1 + val2 * dur2) / (dur1 + dur2) if dur1 + dur2 > 0 else 0
                else:
                    merged_metrics[key] = val1 or val2
            merged['metrics'] = merged_metrics

        # Face count: máximo
        merged['face_count'] = max(seg1.get('face_count', 0), seg2.get('face_count', 0))

        # Marcar como consolidado
        merged['_consolidated'] = True
        merged['_merged_count'] = seg1.get('_merged_count', 1) + seg2.get('_merged_count', 1)

        return merged

    def _merge_similar_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Fusiona segmentos similares consecutivos.
        """
        if len(segments) <= 1:
            return segments

        result = []
        current = deepcopy(segments[0])

        for i in range(1, len(segments)):
            next_seg = segments[i]

            if self._can_merge(current, next_seg):
                # Fusionar
                current = self._merge_two_segments(current, next_seg)
            else:
                # No se puede fusionar, guardar actual y empezar nuevo
                result.append(current)
                current = deepcopy(next_seg)

        # Agregar el último
        result.append(current)

        return result

    def _handle_micro_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Maneja segmentos que son más cortos que la duración mínima.

        Estrategia:
        1. Si es un segmento especial (key_moment, best_take), preservarlo
        2. Si no, intentar fusionarlo con el adyacente más similar
        3. Si no se puede fusionar, descartarlo (absorber en adyacente)
        """
        if len(segments) <= 1:
            return segments

        result = []
        i = 0

        while i < len(segments):
            seg = segments[i]
            duration = seg.get('end_time', 0) - seg.get('start_time', 0)

            # Si cumple duración mínima o es especial, mantener
            if duration >= self.config.min_duration:
                result.append(deepcopy(seg))
                i += 1
                continue

            # Micro-segmento: verificar si es especial
            # Solo preservar si:
            # - Es key_moment Y tiene al menos 1.0s (un momento clave debe ser visible)
            # - Es best_take Y tiene al menos 1.0s (una mejor toma debe ser usable)
            # Los segmentos repeated_take NUNCA se preservan solos (siempre fusionar)
            MIN_SPECIAL = 1.0

            is_special = (
                duration >= MIN_SPECIAL and
                (seg.get('is_key_moment') or seg.get('is_best_take')) and
                not seg.get('is_repeated_take')  # Repetidos nunca son especiales
            )

            if is_special:
                # Preservar aunque sea menor que min_duration
                result.append(deepcopy(seg))
                i += 1
                continue

            # Intentar fusionar con adyacente
            fused = False

            # Preferir fusionar con el anterior si existe y es similar
            if result and self._can_merge_relaxed(result[-1], seg):
                result[-1] = self._merge_two_segments(result[-1], seg)
                fused = True
            # Si no, intentar con el siguiente
            elif i + 1 < len(segments) and self._can_merge_relaxed(seg, segments[i + 1]):
                # Fusionar con siguiente y procesarlo después
                merged = self._merge_two_segments(seg, segments[i + 1])
                segments[i + 1] = merged
                fused = True

            # Si no se pudo fusionar, absorber en el más cercano
            if not fused:
                if result:
                    # Extender el segmento anterior para cubrir este
                    result[-1]['end_time'] = seg['end_time']
                    result[-1]['duration'] = result[-1]['end_time'] - result[-1]['start_time']
                elif i + 1 < len(segments):
                    # Extender el siguiente para cubrir este
                    segments[i + 1]['start_time'] = seg['start_time']
                    segments[i + 1]['duration'] = segments[i + 1]['end_time'] - segments[i + 1]['start_time']
                else:
                    # Último recurso: mantener aunque sea corto
                    result.append(deepcopy(seg))

            i += 1

        return result

    def _can_merge_relaxed(self, seg1: Dict, seg2: Dict) -> bool:
        """
        Versión relajada de can_merge para micro-segmentos.
        Más permisivo para permitir fusión de segmentos cortos.
        """
        # Consecutivos (con tolerancia)
        if abs(seg2.get('start_time', 0) - seg1.get('end_time', 0)) > 0.15:
            return False

        # No garbage
        if seg1.get('tier') == 'garbage' or seg2.get('tier') == 'garbage':
            return False
        if seg1.get('is_garbage') or seg2.get('is_garbage'):
            return False

        # Si uno de los dos es un micro-segmento repetido, ser MUY permisivo
        dur1 = seg1.get('end_time', 0) - seg1.get('start_time', 0)
        dur2 = seg2.get('end_time', 0) - seg2.get('start_time', 0)
        is_micro_repeated = (
            (dur1 < self.config.min_duration and seg1.get('is_repeated_take')) or
            (dur2 < self.config.min_duration and seg2.get('is_repeated_take'))
        )

        # Para micro-segmentos repetidos, permitir fusión con cualquier tipo similar
        if is_micro_repeated:
            # Agrupar tipos similares de forma muy amplia
            static_types = {'ESTATICA', 'TRIPOD', 'LOCKED'}
            movement_types = {'MOVIMIENTO_FLUIDO', 'PANEO', 'TILT', 'TRACKING', 'DOLLY', 'SHAKY'}

            shot1 = seg1.get('shot_type', '')
            shot2 = seg2.get('shot_type', '')

            # Permitir si son del mismo grupo amplio
            if shot1 == shot2:
                return True
            if shot1 in static_types and shot2 in static_types:
                return True
            if shot1 in movement_types and shot2 in movement_types:
                return True
            # Incluso permitir mezcla entre grupos si es un repetido muy corto
            if dur1 < 1.0 or dur2 < 1.0:
                return True

        # Mismo tipo de plano (para no-repetidos)
        shot1 = seg1.get('shot_type', '')
        shot2 = seg2.get('shot_type', '')

        # Agrupar tipos similares
        static_types = {'ESTATICA', 'TRIPOD', 'LOCKED'}
        movement_types = {'MOVIMIENTO_FLUIDO', 'PANEO', 'TILT', 'TRACKING', 'DOLLY'}

        if shot1 == shot2:
            return True
        if shot1 in static_types and shot2 in static_types:
            return True
        if shot1 in movement_types and shot2 in movement_types:
            return True

        return False

    def _recalculate_stats(self, segments: List[Dict]) -> List[Dict]:
        """
        Recalcula estadísticas después de la consolidación.
        """
        for seg in segments:
            # Actualizar duración
            seg['duration'] = seg.get('end_time', 0) - seg.get('start_time', 0)

            # Regenerar human_readable si existe el framework
            if 'evaluation' in seg:
                seg['human_readable'] = self._generate_human_readable(seg)

        return segments

    def _generate_human_readable(self, seg: Dict) -> Dict:
        """
        Genera descripciones legibles para el segmento.
        """
        tier = seg.get('tier', 'discard')
        shot_type = seg.get('shot_type', 'DESCONOCIDO')

        action_map = {
            'gold': 'Usar',
            'silver': 'Revisar',
            'bronze': 'Backup',
            'discard': 'Descartar',
            'garbage': 'Eliminar'
        }

        return {
            'action': action_map.get(tier, 'Revisar'),
            'stability': {
                'status': 'good' if tier in ('gold', 'silver') else 'warning',
                'phrase': f'{shot_type} consolidado'
            }
        }


def consolidate_video_segments(
    segments: List[Dict[str, Any]],
    min_duration: float = DEFAULT_MIN_DURATION,
    merge_similar: bool = DEFAULT_MERGE_SIMILAR
) -> List[Dict[str, Any]]:
    """
    Función de conveniencia para consolidar segmentos de un video.

    Args:
        segments: Lista de segmentos del análisis
        min_duration: Duración mínima de segmento en segundos
        merge_similar: Si fusionar segmentos similares consecutivos

    Returns:
        Lista de segmentos consolidados
    """
    config = ConsolidationConfig(
        min_duration=min_duration,
        merge_similar=merge_similar
    )
    consolidator = SegmentConsolidator(config)
    return consolidator.consolidate(segments)


# Para testing
if __name__ == '__main__':
    # Ejemplo de segmentos con micro-fragmentos
    test_segments = [
        {'start_time': 0.0, 'end_time': 0.5, 'shot_type': 'PANEO', 'tier': 'gold', 'score': 8.0},
        {'start_time': 0.5, 'end_time': 0.8, 'shot_type': 'PANEO', 'tier': 'silver', 'score': 7.5},
        {'start_time': 0.8, 'end_time': 3.0, 'shot_type': 'PANEO', 'tier': 'gold', 'score': 8.2},
        {'start_time': 3.0, 'end_time': 3.3, 'shot_type': 'PANEO', 'tier': 'gold', 'score': 7.8},
        {'start_time': 3.3, 'end_time': 6.0, 'shot_type': 'PANEO', 'tier': 'gold', 'score': 8.5},
        {'start_time': 6.0, 'end_time': 8.0, 'shot_type': 'ESTATICA', 'tier': 'silver', 'score': 6.0},
        {'start_time': 8.0, 'end_time': 8.2, 'shot_type': 'ESTATICA', 'tier': 'bronze', 'score': 5.0},
        {'start_time': 8.2, 'end_time': 10.0, 'shot_type': 'ESTATICA', 'tier': 'silver', 'score': 6.5},
    ]

    print("=== Segmentos originales ===")
    for s in test_segments:
        dur = s['end_time'] - s['start_time']
        print(f"  {s['start_time']:.1f}-{s['end_time']:.1f} ({dur:.1f}s) {s['shot_type']} {s['tier']}")

    consolidated = consolidate_video_segments(test_segments)

    print("\n=== Segmentos consolidados ===")
    for s in consolidated:
        dur = s['end_time'] - s['start_time']
        merged = s.get('_merged_count', 1)
        print(f"  {s['start_time']:.1f}-{s['end_time']:.1f} ({dur:.1f}s) {s['shot_type']} {s['tier']} [merged: {merged}]")
