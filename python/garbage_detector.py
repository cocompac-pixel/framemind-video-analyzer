#!/usr/bin/env python3
"""
Garbage Detector Module v1.0
Detecta contenido "basura" en videos que un editor descartaría inmediatamente:
- Tapa de lente / negro total
- Tomas accidentales (piso, cielo, nada)
- Pre-roll / Post-roll (segundos muertos)
- Flashes de exposición (ajuste de cámara)
- Cortes abruptos (grabación cortada a medio movimiento)
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum


class GarbageType(Enum):
    """Tipos de basura detectables"""
    LENS_CAP = "lens_cap"              # Tapa de lente
    BLACK_FRAME = "black_frame"        # Negro total
    UNIFORM_FRAME = "uniform_frame"    # Frame uniforme (sin contenido)
    SKY_SHOT = "sky_shot"              # Cámara apuntando al cielo
    GROUND_SHOT = "ground_shot"        # Cámara apuntando al piso
    ACCIDENTAL = "accidental"          # Toma accidental genérica
    PRE_ROLL = "pre_roll"              # Segundos muertos al inicio
    POST_ROLL = "post_roll"            # Segundos muertos al final
    EXPOSURE_FLASH = "exposure_flash"  # Flash de ajuste de exposición
    CUT_AT_START = "cut_at_start"      # Corte abrupto al inicio
    CUT_AT_END = "cut_at_end"          # Corte abrupto al final
    WHITEOUT = "whiteout"              # Frame completamente blanco/sobreexpuesto


@dataclass
class GarbageDetection:
    """Resultado de detección de basura para un segmento"""
    garbage_type: GarbageType
    confidence: float                   # 0.0 - 1.0
    start_time: float
    end_time: float
    recoverable: bool = False           # True si se puede recortar y salvar algo
    suggested_trim: Optional[Tuple[float, float]] = None  # (new_start, new_end) si recoverable
    details: dict = field(default_factory=dict)  # Detalles adicionales

    def to_dict(self):
        return {
            'garbage_type': self.garbage_type.value,
            'confidence': self.confidence,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'recoverable': self.recoverable,
            'suggested_trim': self.suggested_trim,
            'details': self.details
        }


class GarbageDetector:
    """
    Detector de basura en videos.
    Analiza frames para identificar contenido no usable.
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Umbrales configurables
        self.thresholds = {
            # Detección de negro/tapa
            'black_brightness_max': 0.02,       # Brillo máximo para negro total
            'lens_cap_variance_max': 5.0,       # Varianza máxima para tapa de lente
            'uniform_variance_max': 10.0,       # Varianza máxima para frame uniforme

            # Detección de cielo/piso
            'sky_brightness_min': 0.7,          # Brillo mínimo para detectar cielo
            'sky_saturation_max': 0.3,          # Saturación máxima para cielo
            'sky_edge_density_max': 0.02,       # Densidad de bordes máxima para cielo
            'ground_brightness_max': 0.35,      # Brillo máximo para piso
            'ground_texture_threshold': 0.1,    # Umbral de textura repetitiva

            # Pre/Post roll
            'dead_air_motion_max': 0.5,         # Movimiento máximo en dead air
            'dead_air_min_duration': 1.0,       # Duración mínima para considerar dead air
            'pre_roll_max_position': 0.15,      # Máximo % del video para pre-roll
            'post_roll_min_position': 0.85,     # Mínimo % del video para post-roll

            # Flash de exposición
            'flash_brightness_change_min': 0.25,  # Cambio mínimo de brillo para flash
            'flash_duration_max': 2.0,            # Duración máxima del flash (segundos)
            'flash_stabilization_time': 0.5,      # Tiempo para considerar estabilizado

            # Corte abrupto
            'abrupt_motion_min': 3.0,           # Movimiento mínimo para corte abrupto
            'abrupt_window_frames': 3,          # Frames a analizar en inicio/fin

            # Whiteout
            'white_brightness_min': 0.95,       # Brillo mínimo para whiteout
            'white_variance_max': 10.0,         # Varianza máxima para whiteout
        }

    def analyze_frames(self, frames_data: List[dict], video_duration: float) -> List[GarbageDetection]:
        """
        Analiza todos los frames y detecta segmentos de basura.

        Args:
            frames_data: Lista de dicts con métricas por frame (del analyzer principal)
            video_duration: Duración total del video en segundos

        Returns:
            Lista de GarbageDetection encontradas
        """
        if not frames_data:
            return []

        detections = []

        # 1. Detectar frames negros/uniformes/blancos
        uniform_detections = self._detect_uniform_segments(frames_data)
        detections.extend(uniform_detections)

        # 2. Detectar cielo/piso accidental
        accidental_detections = self._detect_accidental_shots(frames_data)
        detections.extend(accidental_detections)

        # 3. Detectar pre-roll / post-roll
        dead_air_detections = self._detect_dead_air(frames_data, video_duration)
        detections.extend(dead_air_detections)

        # 4. Detectar flash de exposición
        flash_detections = self._detect_exposure_flash(frames_data)
        detections.extend(flash_detections)

        # 5. Detectar cortes abruptos
        cut_detections = self._detect_abrupt_cuts(frames_data, video_duration)
        detections.extend(cut_detections)

        # Consolidar detecciones superpuestas
        detections = self._consolidate_detections(detections)

        return detections

    def analyze_single_frame(self, frame: np.ndarray, gray: np.ndarray = None) -> dict:
        """
        Analiza un frame individual para métricas de basura.
        Usado durante el análisis frame-by-frame.

        Args:
            frame: Frame BGR
            gray: Frame en escala de grises (opcional, se calcula si no se provee)

        Returns:
            Dict con métricas de basura del frame
        """
        if gray is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape

        # Calcular métricas básicas
        brightness = np.mean(gray) / 255.0
        variance = np.var(gray)

        # Detectar bordes para densidad
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.mean(edges) / 255.0

        # Análisis HSV para saturación
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1]) / 255.0

        # Analizar distribución de brillo (para detectar cielo/piso)
        top_third = gray[0:h//3, :]
        bottom_third = gray[2*h//3:, :]
        top_brightness = np.mean(top_third) / 255.0
        bottom_brightness = np.mean(bottom_third) / 255.0

        # Detectar textura repetitiva (para piso)
        texture_score = self._calculate_texture_repetition(gray)

        # Clasificación rápida
        garbage_flags = {
            'is_black': brightness < self.thresholds['black_brightness_max'],
            'is_uniform': variance < self.thresholds['uniform_variance_max'],
            'is_white': brightness > self.thresholds['white_brightness_min'] and variance < self.thresholds['white_variance_max'],
            'is_lens_cap': variance < self.thresholds['lens_cap_variance_max'],
            'is_likely_sky': (
                top_brightness > self.thresholds['sky_brightness_min'] and
                saturation < self.thresholds['sky_saturation_max'] and
                edge_density < self.thresholds['sky_edge_density_max']
            ),
            'is_likely_ground': (
                bottom_brightness < self.thresholds['ground_brightness_max'] and
                edge_density < 0.05 and
                texture_score > self.thresholds['ground_texture_threshold']
            ),
        }

        return {
            'brightness': brightness,
            'variance': variance,
            'edge_density': edge_density,
            'saturation': saturation,
            'top_brightness': top_brightness,
            'bottom_brightness': bottom_brightness,
            'texture_score': texture_score,
            'garbage_flags': garbage_flags,
        }

    def _calculate_texture_repetition(self, gray: np.ndarray) -> float:
        """
        Calcula score de textura repetitiva (alto = más repetitivo, como piso).
        Usa autocorrelación simplificada.
        """
        try:
            # Reducir tamaño para performance
            small = cv2.resize(gray, (64, 64))

            # Calcular gradientes
            gx = cv2.Sobel(small, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(small, cv2.CV_64F, 0, 1, ksize=3)

            # Magnitud de gradiente
            mag = np.sqrt(gx**2 + gy**2)

            # Calcular varianza de la magnitud normalizada
            # Textura repetitiva = varianza baja, textura variada = varianza alta
            if np.std(mag) < 1:
                return 0.5  # Caso edge

            # Normalizar
            mag_norm = mag / (np.max(mag) + 0.001)

            # Score: alta uniformidad en gradientes = repetitivo
            # Usamos coeficiente de variación inverso
            cv = np.std(mag_norm) / (np.mean(mag_norm) + 0.001)
            repetition_score = 1.0 / (1.0 + cv)

            return float(repetition_score)

        except Exception:
            return 0.0

    def _detect_uniform_segments(self, frames_data: List[dict]) -> List[GarbageDetection]:
        """Detecta segmentos de frames uniformes (negro, blanco, tapa)"""
        detections = []

        # Agrupar frames consecutivos del mismo tipo
        current_type = None
        segment_start = None
        segment_frames = []

        for i, frame in enumerate(frames_data):
            flags = frame.get('garbage_flags', {})
            timestamp = frame.get('timestamp', i * 0.1)

            # Determinar tipo de frame
            frame_type = None
            if flags.get('is_black') or flags.get('is_lens_cap'):
                frame_type = GarbageType.BLACK_FRAME if flags.get('is_black') else GarbageType.LENS_CAP
            elif flags.get('is_white'):
                frame_type = GarbageType.WHITEOUT
            elif flags.get('is_uniform'):
                frame_type = GarbageType.UNIFORM_FRAME

            # Cambio de tipo o fin
            if frame_type != current_type:
                # Cerrar segmento anterior si existe
                if current_type is not None and len(segment_frames) >= 3:  # Mínimo 3 frames
                    detections.append(self._create_uniform_detection(
                        current_type, segment_start, timestamp, segment_frames
                    ))

                # Iniciar nuevo segmento
                current_type = frame_type
                segment_start = timestamp
                segment_frames = [frame] if frame_type else []
            else:
                if frame_type:
                    segment_frames.append(frame)

        # Cerrar último segmento
        if current_type is not None and len(segment_frames) >= 3:
            last_timestamp = frames_data[-1].get('timestamp', len(frames_data) * 0.1)
            detections.append(self._create_uniform_detection(
                current_type, segment_start, last_timestamp, segment_frames
            ))

        return detections

    def _create_uniform_detection(self, garbage_type: GarbageType, start: float,
                                   end: float, frames: List[dict]) -> GarbageDetection:
        """Crea detección para segmento uniforme"""
        avg_brightness = np.mean([f.get('brightness', 0) for f in frames])
        avg_variance = np.mean([f.get('variance', 0) for f in frames])

        # Calcular confianza
        if garbage_type in [GarbageType.BLACK_FRAME, GarbageType.LENS_CAP]:
            confidence = 1.0 - (avg_brightness / self.thresholds['black_brightness_max'])
        elif garbage_type == GarbageType.WHITEOUT:
            confidence = (avg_brightness - 0.9) / 0.1  # 0.9-1.0 -> 0-1
        else:
            confidence = 1.0 - (avg_variance / self.thresholds['uniform_variance_max'])

        confidence = max(0.0, min(1.0, confidence))

        return GarbageDetection(
            garbage_type=garbage_type,
            confidence=confidence,
            start_time=start,
            end_time=end,
            recoverable=False,  # Frames uniformes no son recuperables
            details={
                'avg_brightness': avg_brightness,
                'avg_variance': avg_variance,
                'frame_count': len(frames)
            }
        )

    def _detect_accidental_shots(self, frames_data: List[dict]) -> List[GarbageDetection]:
        """Detecta tomas accidentales de cielo o piso"""
        detections = []

        current_type = None
        segment_start = None
        segment_frames = []

        for i, frame in enumerate(frames_data):
            flags = frame.get('garbage_flags', {})
            timestamp = frame.get('timestamp', i * 0.1)

            frame_type = None
            if flags.get('is_likely_sky'):
                frame_type = GarbageType.SKY_SHOT
            elif flags.get('is_likely_ground'):
                frame_type = GarbageType.GROUND_SHOT

            if frame_type != current_type:
                if current_type is not None and len(segment_frames) >= 5:  # Mínimo 0.5s a 10fps
                    detections.append(self._create_accidental_detection(
                        current_type, segment_start, timestamp, segment_frames
                    ))

                current_type = frame_type
                segment_start = timestamp
                segment_frames = [frame] if frame_type else []
            else:
                if frame_type:
                    segment_frames.append(frame)

        # Cerrar último
        if current_type is not None and len(segment_frames) >= 5:
            last_timestamp = frames_data[-1].get('timestamp', len(frames_data) * 0.1)
            detections.append(self._create_accidental_detection(
                current_type, segment_start, last_timestamp, segment_frames
            ))

        return detections

    def _create_accidental_detection(self, garbage_type: GarbageType, start: float,
                                      end: float, frames: List[dict]) -> GarbageDetection:
        """Crea detección para toma accidental"""
        avg_edge_density = np.mean([f.get('edge_density', 0) for f in frames])

        # Confianza basada en consistencia y falta de contenido
        confidence = 1.0 - min(avg_edge_density / 0.05, 1.0)
        confidence = max(0.5, min(1.0, confidence))  # Mínimo 0.5 porque ya pasó filtros

        return GarbageDetection(
            garbage_type=garbage_type,
            confidence=confidence,
            start_time=start,
            end_time=end,
            recoverable=False,
            details={
                'avg_edge_density': avg_edge_density,
                'frame_count': len(frames),
                'description': 'Cámara apuntando al cielo' if garbage_type == GarbageType.SKY_SHOT else 'Cámara apuntando al piso'
            }
        )

    def _detect_dead_air(self, frames_data: List[dict], video_duration: float) -> List[GarbageDetection]:
        """Detecta pre-roll y post-roll (segundos muertos sin acción)"""
        detections = []

        if len(frames_data) < 10:  # Muy corto para analizar
            return detections

        # Calcular posición relativa de cada frame
        pre_roll_end = video_duration * self.thresholds['pre_roll_max_position']
        post_roll_start = video_duration * self.thresholds['post_roll_min_position']

        # Analizar pre-roll (inicio del video)
        pre_roll_frames = []
        for frame in frames_data:
            timestamp = frame.get('timestamp', 0)
            if timestamp > pre_roll_end:
                break

            motion = frame.get('motion_magnitude', 0)
            if motion < self.thresholds['dead_air_motion_max']:
                pre_roll_frames.append(frame)
            else:
                # Si hay movimiento, terminó el pre-roll
                break

        if len(pre_roll_frames) >= int(self.thresholds['dead_air_min_duration'] * 10):  # 10 fps
            end_time = pre_roll_frames[-1].get('timestamp', 0) + 0.1
            detections.append(GarbageDetection(
                garbage_type=GarbageType.PRE_ROLL,
                confidence=0.8,
                start_time=0,
                end_time=end_time,
                recoverable=True,
                suggested_trim=(end_time, video_duration),
                details={
                    'frame_count': len(pre_roll_frames),
                    'description': 'Segundos muertos antes de la acción'
                }
            ))

        # Analizar post-roll (final del video)
        post_roll_frames = []
        for frame in reversed(frames_data):
            timestamp = frame.get('timestamp', 0)
            if timestamp < post_roll_start:
                break

            motion = frame.get('motion_magnitude', 0)
            if motion < self.thresholds['dead_air_motion_max']:
                post_roll_frames.append(frame)
            else:
                break

        if len(post_roll_frames) >= int(self.thresholds['dead_air_min_duration'] * 10):
            start_time = post_roll_frames[-1].get('timestamp', video_duration)
            detections.append(GarbageDetection(
                garbage_type=GarbageType.POST_ROLL,
                confidence=0.8,
                start_time=start_time,
                end_time=video_duration,
                recoverable=True,
                suggested_trim=(0, start_time),
                details={
                    'frame_count': len(post_roll_frames),
                    'description': 'Segundos muertos después del corte'
                }
            ))

        return detections

    def _detect_exposure_flash(self, frames_data: List[dict]) -> List[GarbageDetection]:
        """Detecta flash de ajuste de exposición al inicio"""
        detections = []

        if len(frames_data) < 20:  # Muy corto
            return detections

        # Analizar primeros 2-3 segundos (20-30 frames a 10fps)
        window_size = min(30, len(frames_data))
        window = frames_data[:window_size]

        brightnesses = [f.get('brightness', 0.5) for f in window]

        # Buscar cambio brusco de brillo
        for i in range(1, len(brightnesses) - 5):
            change = abs(brightnesses[i] - brightnesses[i-1])

            if change > self.thresholds['flash_brightness_change_min']:
                # Verificar que se estabiliza después
                post_change = brightnesses[i+1:i+6]
                if len(post_change) >= 3:
                    post_std = np.std(post_change)

                    if post_std < 0.05:  # Se estabilizó
                        flash_end = window[i + 5].get('timestamp', 0)

                        # Solo reportar si es en los primeros 2 segundos
                        if flash_end < self.thresholds['flash_duration_max']:
                            detections.append(GarbageDetection(
                                garbage_type=GarbageType.EXPOSURE_FLASH,
                                confidence=min(change / 0.3, 1.0),  # Normalizar confianza
                                start_time=0,
                                end_time=flash_end,
                                recoverable=True,
                                suggested_trim=(flash_end, None),  # None = hasta el final
                                details={
                                    'brightness_change': change,
                                    'stabilization_point': flash_end,
                                    'description': 'Ajuste automático de exposición'
                                }
                            ))
                            break  # Solo detectar un flash

        return detections

    def _detect_abrupt_cuts(self, frames_data: List[dict], video_duration: float) -> List[GarbageDetection]:
        """Detecta cortes abruptos donde la grabación inicia/termina a medio movimiento"""
        detections = []

        if len(frames_data) < 6:
            return detections

        window = self.thresholds['abrupt_window_frames']
        min_motion = self.thresholds['abrupt_motion_min']

        # Analizar inicio
        start_motions = [f.get('motion_magnitude', 0) for f in frames_data[:window]]
        if len(start_motions) >= window:
            avg_start_motion = np.mean(start_motions)

            if avg_start_motion > min_motion:
                # Alta moción al inicio = corte abrupto
                # Verificar consistencia de dirección (indica movimiento en curso)
                start_directions = [f.get('direction_consistency', 0) for f in frames_data[:window]]
                avg_direction_consistency = np.mean(start_directions)

                if avg_direction_consistency > 0.5:  # Movimiento direccional consistente
                    detections.append(GarbageDetection(
                        garbage_type=GarbageType.CUT_AT_START,
                        confidence=min(avg_start_motion / 5.0, 1.0),
                        start_time=0,
                        end_time=frames_data[window-1].get('timestamp', 0.3),
                        recoverable=False,  # No se puede recuperar lo que no se grabó
                        details={
                            'avg_motion': avg_start_motion,
                            'direction_consistency': avg_direction_consistency,
                            'description': 'Grabación iniciada a medio movimiento'
                        }
                    ))

        # Analizar final
        end_motions = [f.get('motion_magnitude', 0) for f in frames_data[-window:]]
        if len(end_motions) >= window:
            avg_end_motion = np.mean(end_motions)

            if avg_end_motion > min_motion:
                end_directions = [f.get('direction_consistency', 0) for f in frames_data[-window:]]
                avg_direction_consistency = np.mean(end_directions)

                if avg_direction_consistency > 0.5:
                    detections.append(GarbageDetection(
                        garbage_type=GarbageType.CUT_AT_END,
                        confidence=min(avg_end_motion / 5.0, 1.0),
                        start_time=frames_data[-window].get('timestamp', video_duration - 0.3),
                        end_time=video_duration,
                        recoverable=False,
                        details={
                            'avg_motion': avg_end_motion,
                            'direction_consistency': avg_direction_consistency,
                            'description': 'Grabación terminada a medio movimiento'
                        }
                    ))

        return detections

    def _consolidate_detections(self, detections: List[GarbageDetection]) -> List[GarbageDetection]:
        """
        Consolida detecciones superpuestas.
        Prioriza tipos más específicos sobre genéricos.
        """
        if len(detections) <= 1:
            return detections

        # Ordenar por tiempo de inicio
        detections.sort(key=lambda d: d.start_time)

        # Prioridad de tipos (mayor = más específico, tiene precedencia)
        priority = {
            GarbageType.LENS_CAP: 10,
            GarbageType.BLACK_FRAME: 9,
            GarbageType.WHITEOUT: 9,
            GarbageType.EXPOSURE_FLASH: 8,
            GarbageType.SKY_SHOT: 7,
            GarbageType.GROUND_SHOT: 7,
            GarbageType.CUT_AT_START: 6,
            GarbageType.CUT_AT_END: 6,
            GarbageType.PRE_ROLL: 5,
            GarbageType.POST_ROLL: 5,
            GarbageType.UNIFORM_FRAME: 4,
            GarbageType.ACCIDENTAL: 3,
        }

        consolidated = []
        for detection in detections:
            # Verificar superposición con detecciones existentes
            overlapping = None
            for i, existing in enumerate(consolidated):
                if self._detections_overlap(detection, existing):
                    overlapping = i
                    break

            if overlapping is not None:
                # Mantener la de mayor prioridad
                existing = consolidated[overlapping]
                if priority.get(detection.garbage_type, 0) > priority.get(existing.garbage_type, 0):
                    consolidated[overlapping] = detection
            else:
                consolidated.append(detection)

        return consolidated

    def _detections_overlap(self, d1: GarbageDetection, d2: GarbageDetection) -> bool:
        """Verifica si dos detecciones se superponen significativamente"""
        # Calcular intersección
        start = max(d1.start_time, d2.start_time)
        end = min(d1.end_time, d2.end_time)

        if start >= end:
            return False  # No hay intersección

        intersection = end - start
        d1_duration = d1.end_time - d1.start_time
        d2_duration = d2.end_time - d2.start_time

        # Superpuestos si la intersección es >50% de cualquiera de los dos
        return (intersection / d1_duration > 0.5) or (intersection / d2_duration > 0.5)


# Funciones de utilidad para uso rápido

def is_garbage_frame(brightness: float, variance: float, edge_density: float) -> Tuple[bool, Optional[str]]:
    """
    Función rápida para determinar si un frame es basura.

    Returns:
        (is_garbage, garbage_type_string o None)
    """
    if brightness < 0.02:
        return True, "black_frame"
    if brightness > 0.95 and variance < 10:
        return True, "whiteout"
    if variance < 5:
        return True, "lens_cap"
    if variance < 10:
        return True, "uniform_frame"
    if brightness > 0.7 and edge_density < 0.02:
        return True, "likely_sky"

    return False, None


def get_garbage_summary(detections: List[GarbageDetection]) -> dict:
    """
    Genera resumen de las detecciones de basura.

    Returns:
        Dict con estadísticas y recomendaciones
    """
    if not detections:
        return {
            'total_garbage_duration': 0,
            'garbage_count': 0,
            'types_found': [],
            'recoverable_duration': 0,
            'recommendation': 'No se detectó contenido basura'
        }

    total_duration = sum(d.end_time - d.start_time for d in detections)
    recoverable_duration = sum(
        d.end_time - d.start_time for d in detections if d.recoverable
    )
    types_found = list(set(d.garbage_type.value for d in detections))

    # Generar recomendación
    if total_duration > 5:
        recommendation = f'Se recomienda recortar {total_duration:.1f}s de contenido no usable'
    elif recoverable_duration > 0:
        recommendation = f'Considerar recortar {recoverable_duration:.1f}s de pre/post roll'
    else:
        recommendation = 'Basura detectada pero el video es mayormente usable'

    return {
        'total_garbage_duration': total_duration,
        'garbage_count': len(detections),
        'types_found': types_found,
        'recoverable_duration': recoverable_duration,
        'recommendation': recommendation,
        'detections': [d.to_dict() for d in detections]
    }


if __name__ == "__main__":
    # Test básico
    detector = GarbageDetector()
    print("GarbageDetector inicializado correctamente")
    print(f"Tipos detectables: {[t.value for t in GarbageType]}")
