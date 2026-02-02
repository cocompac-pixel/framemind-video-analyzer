#!/usr/bin/env python3
"""
Scene Grouper Module v1.0
Agrupación de segmentos por setup/escena visual.

Funcionalidades:
- Extracción de características visuales (histogramas de color, textura)
- Clustering jerárquico para agrupar segmentos similares
- Detección de cambios de escena/setup
- Asignación de grupos/escenas a segmentos
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
from collections import defaultdict


class SceneChangeType(Enum):
    """Tipos de cambio de escena"""
    NONE = "none"
    SOFT_CUT = "soft_cut"           # Cambio suave (similar iluminación/color)
    HARD_CUT = "hard_cut"           # Cambio abrupto
    LOCATION_CHANGE = "location"    # Cambio de locación
    LIGHTING_CHANGE = "lighting"    # Cambio de iluminación
    ANGLE_CHANGE = "angle"          # Solo cambio de ángulo (mismo setup)


@dataclass
class VisualFingerprint:
    """Huella visual de un segmento para comparación"""
    segment_id: int

    # Histogramas de color (HSV)
    hue_hist: np.ndarray
    sat_hist: np.ndarray
    val_hist: np.ndarray

    # Características de textura
    edge_density: float
    texture_variance: float

    # Características de iluminación
    avg_brightness: float
    brightness_std: float
    contrast: float

    # Color dominante
    dominant_colors: List[Tuple[int, int, int]]

    # Características espaciales
    spatial_distribution: np.ndarray  # Distribución de actividad en cuadrantes

    def to_feature_vector(self) -> np.ndarray:
        """Convierte a vector de características para clustering"""
        features = []

        # Histogramas normalizados (reducidos)
        features.extend(self.hue_hist[:16])  # 16 bins de hue
        features.extend(self.sat_hist[:8])   # 8 bins de saturación
        features.extend(self.val_hist[:8])   # 8 bins de valor

        # Características escalares
        features.append(self.edge_density)
        features.append(self.texture_variance / 1000)  # Normalizar
        features.append(self.avg_brightness)
        features.append(self.brightness_std)
        features.append(self.contrast)

        # Distribución espacial
        features.extend(self.spatial_distribution.flatten())

        return np.array(features, dtype=np.float32)


@dataclass
class SceneGroup:
    """Grupo de segmentos que pertenecen a la misma escena/setup"""
    group_id: int
    name: str                         # Nombre generado o asignado
    segments: List[int]               # IDs de segmentos en este grupo
    representative_segment: int       # Segmento más representativo

    # Características promedio del grupo
    avg_brightness: float
    dominant_color: Tuple[int, int, int]

    # Metadatos
    total_duration: float
    segment_count: int

    # Calidad del grupo
    visual_consistency: float         # Qué tan similares son los segmentos (0-1)

    def to_dict(self):
        return {
            'group_id': self.group_id,
            'name': self.name,
            'segments': self.segments,
            'representative_segment': self.representative_segment,
            'avg_brightness': self.avg_brightness,
            'dominant_color': self.dominant_color,
            'total_duration': self.total_duration,
            'segment_count': self.segment_count,
            'visual_consistency': self.visual_consistency,
        }


@dataclass
class SceneAnalysisResult:
    """Resultado del análisis de escenas"""
    groups: List[SceneGroup]
    segment_to_group: Dict[int, int]  # Mapeo segmento -> grupo
    scene_changes: List[Dict]          # Lista de cambios de escena detectados
    total_groups: int

    def to_dict(self):
        return {
            'groups': [g.to_dict() for g in self.groups],
            'segment_to_group': self.segment_to_group,
            'scene_changes': self.scene_changes,
            'total_groups': self.total_groups,
        }


class SceneGrouper:
    """
    Agrupa segmentos de video por similitud visual (setup/escena).
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Umbrales configurables
        self.thresholds = {
            # Similitud para considerar misma escena
            'similarity_threshold': 0.75,

            # Histogramas
            'hue_bins': 32,
            'sat_bins': 16,
            'val_bins': 16,

            # Cambio de escena
            'hard_cut_threshold': 0.5,   # Diferencia para hard cut
            'soft_cut_threshold': 0.25,  # Diferencia para soft cut

            # Clustering
            'min_group_size': 1,         # Mínimo segmentos por grupo
            'max_groups': 20,            # Máximo grupos a generar
        }

    def analyze_project(self, segments: List[Dict],
                        frames_data: List[Dict] = None) -> SceneAnalysisResult:
        """
        Analiza todos los segmentos de un proyecto y los agrupa por escena.

        Args:
            segments: Lista de segmentos con métricas
            frames_data: Datos de frames (opcional, para análisis más detallado)

        Returns:
            SceneAnalysisResult con grupos y mapeos
        """
        if not segments:
            return SceneAnalysisResult(
                groups=[],
                segment_to_group={},
                scene_changes=[],
                total_groups=0
            )

        # Extraer fingerprints de cada segmento
        fingerprints = self._extract_fingerprints(segments)

        # Detectar cambios de escena
        scene_changes = self._detect_scene_changes(fingerprints, segments)

        # Clustering de segmentos
        groups, segment_to_group = self._cluster_segments(fingerprints, segments)

        return SceneAnalysisResult(
            groups=groups,
            segment_to_group=segment_to_group,
            scene_changes=scene_changes,
            total_groups=len(groups)
        )

    def _extract_fingerprints(self, segments: List[Dict]) -> List[VisualFingerprint]:
        """Extrae fingerprints visuales de cada segmento"""
        fingerprints = []

        for i, segment in enumerate(segments):
            metrics = segment.get('metrics', {})

            # Crear histogramas sintéticos basados en métricas disponibles
            brightness = metrics.get('brightness_mean', 0.5)
            contrast = metrics.get('contrast_mean', 0.5)
            edge_density = metrics.get('edge_density', 0.1)

            # Histograma de hue (sintético basado en características)
            hue_hist = self._create_synthetic_histogram(
                brightness, self.thresholds['hue_bins']
            )

            # Histograma de saturación
            sat_hist = self._create_synthetic_histogram(
                contrast, self.thresholds['sat_bins']
            )

            # Histograma de valor
            val_hist = self._create_synthetic_histogram(
                brightness, self.thresholds['val_bins']
            )

            # Distribución espacial (basada en balance)
            h_balance = metrics.get('h_balance', 0.5)
            v_balance = metrics.get('v_balance', 0.5)
            spatial = np.array([
                [1 - h_balance, h_balance],
                [1 - v_balance, v_balance]
            ])

            # Color dominante estimado
            dominant_color = self._estimate_dominant_color(brightness, contrast)

            fp = VisualFingerprint(
                segment_id=i,
                hue_hist=hue_hist,
                sat_hist=sat_hist,
                val_hist=val_hist,
                edge_density=edge_density,
                texture_variance=metrics.get('sharpness_mean', 100),
                avg_brightness=brightness,
                brightness_std=metrics.get('brightness_std', 0.1),
                contrast=contrast,
                dominant_colors=[dominant_color],
                spatial_distribution=spatial
            )

            fingerprints.append(fp)

        return fingerprints

    def _create_synthetic_histogram(self, center_value: float, bins: int) -> np.ndarray:
        """
        Crea un histograma sintético centrado en un valor.
        Útil cuando no tenemos acceso a los frames originales.
        """
        hist = np.zeros(bins, dtype=np.float32)
        center_bin = int(center_value * (bins - 1))

        # Distribución gaussiana alrededor del centro
        for i in range(bins):
            distance = abs(i - center_bin)
            hist[i] = np.exp(-distance * distance / (bins / 4))

        # Normalizar
        hist = hist / (hist.sum() + 1e-6)
        return hist

    def _estimate_dominant_color(self, brightness: float,
                                  contrast: float) -> Tuple[int, int, int]:
        """Estima un color dominante basado en métricas"""
        # Mapear brightness a escala 0-255
        v = int(brightness * 255)

        # Estimar saturación basada en contraste
        s = int(contrast * 128)

        # Hue neutral (gris) por defecto
        h = 0

        return (h, s, v)

    def _detect_scene_changes(self, fingerprints: List[VisualFingerprint],
                               segments: List[Dict]) -> List[Dict]:
        """Detecta cambios de escena entre segmentos consecutivos"""
        changes = []

        for i in range(1, len(fingerprints)):
            prev_fp = fingerprints[i - 1]
            curr_fp = fingerprints[i]

            # Calcular distancia entre fingerprints
            distance = self._calculate_fingerprint_distance(prev_fp, curr_fp)

            # Determinar tipo de cambio
            change_type = SceneChangeType.NONE

            if distance > self.thresholds['hard_cut_threshold']:
                change_type = SceneChangeType.HARD_CUT
            elif distance > self.thresholds['soft_cut_threshold']:
                # Determinar si es cambio de iluminación o locación
                brightness_diff = abs(prev_fp.avg_brightness - curr_fp.avg_brightness)
                if brightness_diff > 0.3:
                    change_type = SceneChangeType.LIGHTING_CHANGE
                else:
                    change_type = SceneChangeType.SOFT_CUT

            if change_type != SceneChangeType.NONE:
                changes.append({
                    'from_segment': i - 1,
                    'to_segment': i,
                    'timestamp': segments[i]['start_time'],
                    'change_type': change_type.value,
                    'distance': float(distance),
                    'confidence': min(1.0, distance / self.thresholds['hard_cut_threshold'])
                })

        return changes

    def _calculate_fingerprint_distance(self, fp1: VisualFingerprint,
                                         fp2: VisualFingerprint) -> float:
        """Calcula distancia entre dos fingerprints visuales"""
        # Distancia de histogramas (correlación)
        hue_dist = 1 - cv2.compareHist(
            fp1.hue_hist.astype(np.float32),
            fp2.hue_hist.astype(np.float32),
            cv2.HISTCMP_CORREL
        )

        sat_dist = 1 - cv2.compareHist(
            fp1.sat_hist.astype(np.float32),
            fp2.sat_hist.astype(np.float32),
            cv2.HISTCMP_CORREL
        )

        val_dist = 1 - cv2.compareHist(
            fp1.val_hist.astype(np.float32),
            fp2.val_hist.astype(np.float32),
            cv2.HISTCMP_CORREL
        )

        # Distancia de características escalares
        brightness_dist = abs(fp1.avg_brightness - fp2.avg_brightness)
        edge_dist = abs(fp1.edge_density - fp2.edge_density)

        # Ponderar distancias
        total_dist = (
            hue_dist * 0.25 +
            sat_dist * 0.15 +
            val_dist * 0.25 +
            brightness_dist * 0.25 +
            edge_dist * 0.10
        )

        return float(total_dist)

    def _cluster_segments(self, fingerprints: List[VisualFingerprint],
                          segments: List[Dict]) -> Tuple[List[SceneGroup], Dict[int, int]]:
        """
        Agrupa segmentos por similitud visual usando clustering jerárquico simple.
        """
        if not fingerprints:
            return [], {}

        n_segments = len(fingerprints)

        # Calcular matriz de distancias
        distance_matrix = np.zeros((n_segments, n_segments))
        for i in range(n_segments):
            for j in range(i + 1, n_segments):
                dist = self._calculate_fingerprint_distance(
                    fingerprints[i], fingerprints[j]
                )
                distance_matrix[i, j] = dist
                distance_matrix[j, i] = dist

        # Clustering simple: agrupar por umbral de similitud
        # Usando algoritmo de componentes conectados
        similarity_threshold = 1 - self.thresholds['similarity_threshold']

        # Inicializar cada segmento en su propio grupo
        segment_to_group = {i: i for i in range(n_segments)}

        # Unir grupos similares
        for i in range(n_segments):
            for j in range(i + 1, n_segments):
                if distance_matrix[i, j] < similarity_threshold:
                    # Unir grupos
                    old_group = segment_to_group[j]
                    new_group = segment_to_group[i]
                    for k in range(n_segments):
                        if segment_to_group[k] == old_group:
                            segment_to_group[k] = new_group

        # Renumerar grupos consecutivamente
        unique_groups = sorted(set(segment_to_group.values()))
        group_mapping = {old: new for new, old in enumerate(unique_groups)}
        segment_to_group = {k: group_mapping[v] for k, v in segment_to_group.items()}

        # Crear objetos SceneGroup
        groups = self._create_scene_groups(
            segment_to_group, fingerprints, segments, distance_matrix
        )

        return groups, segment_to_group

    def _create_scene_groups(self, segment_to_group: Dict[int, int],
                              fingerprints: List[VisualFingerprint],
                              segments: List[Dict],
                              distance_matrix: np.ndarray) -> List[SceneGroup]:
        """Crea objetos SceneGroup a partir del clustering"""
        groups = []

        # Agrupar segmentos por grupo
        group_segments = defaultdict(list)
        for seg_id, group_id in segment_to_group.items():
            group_segments[group_id].append(seg_id)

        for group_id, seg_ids in sorted(group_segments.items()):
            # Calcular características del grupo
            avg_brightness = np.mean([
                fingerprints[i].avg_brightness for i in seg_ids
            ])

            # Encontrar segmento representativo (más cercano al centroide)
            if len(seg_ids) == 1:
                representative = seg_ids[0]
                consistency = 1.0
            else:
                # Calcular distancias internas
                internal_distances = []
                for i in seg_ids:
                    avg_dist = np.mean([
                        distance_matrix[i, j] for j in seg_ids if j != i
                    ])
                    internal_distances.append((i, avg_dist))

                # El representativo es el de menor distancia promedio
                representative = min(internal_distances, key=lambda x: x[1])[0]

                # Consistencia = 1 - distancia promedio interna
                avg_internal_dist = np.mean([d for _, d in internal_distances])
                consistency = max(0, 1 - avg_internal_dist)

            # Calcular duración total
            total_duration = sum(
                segments[i].get('duration', 0) for i in seg_ids
            )

            # Generar nombre descriptivo
            name = self._generate_group_name(
                group_id, avg_brightness, len(seg_ids)
            )

            # Color dominante del grupo
            dominant_color = fingerprints[representative].dominant_colors[0]

            group = SceneGroup(
                group_id=group_id,
                name=name,
                segments=seg_ids,
                representative_segment=representative,
                avg_brightness=float(avg_brightness),
                dominant_color=dominant_color,
                total_duration=float(total_duration),
                segment_count=len(seg_ids),
                visual_consistency=float(consistency)
            )

            groups.append(group)

        return groups

    def _generate_group_name(self, group_id: int, brightness: float,
                              segment_count: int) -> str:
        """Genera un nombre descriptivo para el grupo"""
        # Descripción de iluminación
        if brightness < 0.3:
            light_desc = "Oscuro"
        elif brightness < 0.5:
            light_desc = "Medio"
        elif brightness < 0.7:
            light_desc = "Claro"
        else:
            light_desc = "Brillante"

        # Letra de grupo
        group_letter = chr(65 + (group_id % 26))  # A, B, C, ...

        return f"Setup {group_letter} ({light_desc})"

    def get_similar_segments(self, segments: List[Dict],
                              reference_segment_idx: int,
                              top_n: int = 5) -> List[Tuple[int, float]]:
        """
        Encuentra los N segmentos más similares a uno dado.

        Returns:
            Lista de tuplas (segment_idx, similarity_score)
        """
        if not segments or reference_segment_idx >= len(segments):
            return []

        fingerprints = self._extract_fingerprints(segments)
        ref_fp = fingerprints[reference_segment_idx]

        similarities = []
        for i, fp in enumerate(fingerprints):
            if i != reference_segment_idx:
                distance = self._calculate_fingerprint_distance(ref_fp, fp)
                similarity = 1 - distance
                similarities.append((i, similarity))

        # Ordenar por similitud descendente
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_n]


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def get_scene_summary(result: SceneAnalysisResult) -> Dict:
    """Genera un resumen del análisis de escenas"""
    if not result.groups:
        return {
            'total_groups': 0,
            'total_scene_changes': 0,
            'largest_group_size': 0,
            'avg_group_size': 0,
            'avg_consistency': 0,
        }

    group_sizes = [g.segment_count for g in result.groups]
    consistencies = [g.visual_consistency for g in result.groups]

    return {
        'total_groups': result.total_groups,
        'total_scene_changes': len(result.scene_changes),
        'largest_group_size': max(group_sizes),
        'smallest_group_size': min(group_sizes),
        'avg_group_size': sum(group_sizes) / len(group_sizes),
        'avg_consistency': sum(consistencies) / len(consistencies),
        'hard_cuts': sum(1 for c in result.scene_changes if c['change_type'] == 'hard_cut'),
        'soft_cuts': sum(1 for c in result.scene_changes if c['change_type'] == 'soft_cut'),
    }


def format_scene_groups_for_display(result: SceneAnalysisResult,
                                     segments: List[Dict]) -> List[Dict]:
    """Formatea grupos para mostrar en UI"""
    formatted = []

    for group in result.groups:
        # Obtener información de segmentos del grupo
        group_segments = [segments[i] for i in group.segments if i < len(segments)]

        # Calcular estadísticas del grupo
        tiers = [s.get('tier', 'unknown') for s in group_segments]
        tier_counts = {t: tiers.count(t) for t in set(tiers)}

        formatted.append({
            'group_id': group.group_id,
            'name': group.name,
            'segment_count': group.segment_count,
            'total_duration': round(group.total_duration, 2),
            'visual_consistency': round(group.visual_consistency * 100, 1),
            'tier_distribution': tier_counts,
            'best_tier': min(tier_counts.keys(),
                            key=lambda t: {'gold': 0, 'silver': 1, 'bronze': 2, 'discard': 3}.get(t, 4)),
            'representative_segment': group.representative_segment,
        })

    return formatted


if __name__ == "__main__":
    # Test básico
    grouper = SceneGrouper()
    print("SceneGrouper inicializado correctamente")
    print(f"Thresholds: {grouper.thresholds}")
