#!/usr/bin/env python3
"""
Shot Classifier Module v1.0
Clasifica el tipo de plano/encuadre de cada segmento:
- Plano General / Establecimiento (ELS/LS)
- Plano Medio (MS)
- Close-up (CU)
- Extreme Close-up / Detalle (ECU)
- Over the Shoulder (OTS)
- POV / Subjetiva
- Two-shot / Group shot
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum
from pathlib import Path


class ShotType(Enum):
    """Tipos de plano cinematográficos"""
    EXTREME_WIDE = "PLANO_GENERAL_EXTREMO"    # Paisaje, establecimiento
    WIDE = "PLANO_GENERAL"                     # Escena completa, contexto
    MEDIUM_WIDE = "PLANO_AMERICANO"            # De rodillas para arriba
    MEDIUM = "PLANO_MEDIO"                     # De cintura para arriba
    MEDIUM_CLOSEUP = "PLANO_MEDIO_CORTO"       # De pecho para arriba
    CLOSEUP = "PRIMER_PLANO"                   # Rostro completo
    EXTREME_CLOSEUP = "PRIMERÍSIMO_PLANO"      # Detalle de rostro/objeto
    DETAIL = "PLANO_DETALLE"                   # Objeto específico
    OVER_SHOULDER = "OVER_THE_SHOULDER"        # Por encima del hombro
    POV = "PUNTO_DE_VISTA"                     # Subjetiva
    TWO_SHOT = "PLANO_DOS"                     # Dos personas
    GROUP = "PLANO_GRUPO"                      # Tres o más personas
    INSERT = "INSERT"                          # Detalle narrativo
    UNKNOWN = "DESCONOCIDO"


@dataclass
class FaceInfo:
    """Información de un rostro detectado"""
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    coverage: float                   # % del frame que ocupa
    position: str                     # "center", "left", "right", "top", "bottom"
    in_focus: bool                    # Si está enfocado
    sharpness: float                  # Varianza del Laplaciano
    eyes_detected: int                # Número de ojos detectados
    is_partial: bool                  # Si está cortado por el frame


@dataclass
class ShotClassification:
    """Resultado de clasificación de plano"""
    shot_type: ShotType
    confidence: float
    face_count: int
    primary_face_coverage: float      # Cobertura del rostro principal
    characteristics: List[str]        # ["shallow_dof", "movement", etc.]
    details: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'shot_type': self.shot_type.value,
            'shot_type_key': self.shot_type.name.lower(),
            'confidence': self.confidence,
            'face_count': self.face_count,
            'primary_face_coverage': self.primary_face_coverage,
            'characteristics': self.characteristics,
            'details': self.details
        }


class ShotClassifier:
    """
    Clasificador de tipos de plano basado en análisis visual.
    Usa OpenCV para detección de rostros y análisis de composición.
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Cargar clasificadores Haar de OpenCV
        self._load_haar_cascades()

        # Umbrales de clasificación
        self.thresholds = {
            # Cobertura de rostro para cada tipo de plano
            'extreme_closeup_min_coverage': 0.35,    # >35% del frame
            'closeup_min_coverage': 0.15,            # 15-35%
            'medium_closeup_min_coverage': 0.08,     # 8-15%
            'medium_min_coverage': 0.04,             # 4-8%
            'medium_wide_min_coverage': 0.02,        # 2-4%

            # Densidad de bordes para planos sin rostros
            'detail_edge_density_min': 0.15,         # Alta densidad = detalle
            'wide_edge_density_max': 0.08,           # Baja densidad = general

            # Detección de profundidad de campo
            'shallow_dof_ratio': 1.5,                # Centro 1.5x más nítido que bordes

            # Foreground blur para OTS
            'foreground_blur_threshold': 0.3,        # % del frame con blur en primer plano

            # Movimiento para POV
            'pov_motion_pattern_threshold': 0.6,     # Consistencia de movimiento tipo caminata
        }

    def _load_haar_cascades(self):
        """Carga los clasificadores Haar de OpenCV"""
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            self.profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_profileface.xml'
            )
            self.cascades_loaded = True
        except Exception as e:
            print(f"Warning: Could not load Haar cascades: {e}")
            self.cascades_loaded = False
            self.face_cascade = None
            self.eye_cascade = None
            self.profile_cascade = None

    def classify_frame(self, frame: np.ndarray, gray: np.ndarray = None,
                       motion_data: dict = None) -> ShotClassification:
        """
        Clasifica el tipo de plano de un frame individual.

        Args:
            frame: Frame BGR
            gray: Frame en escala de grises (opcional)
            motion_data: Datos de movimiento del frame (opcional)

        Returns:
            ShotClassification con el tipo de plano y detalles
        """
        if gray is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape
        frame_area = h * w

        # 1. Detectar rostros
        faces = self._detect_faces(gray, frame)

        # 2. Analizar composición
        composition = self._analyze_frame_composition(gray, frame)

        # 3. Detectar profundidad de campo
        dof_info = self._analyze_depth_of_field(gray)

        # 4. Clasificar basándose en toda la información
        classification = self._determine_shot_type(
            faces, composition, dof_info, motion_data, (h, w)
        )

        return classification

    def classify_segment(self, frames_data: List[dict],
                         representative_frame: np.ndarray = None) -> ShotClassification:
        """
        Clasifica el tipo de plano de un segmento completo.
        Usa el frame representativo o promedia múltiples frames.

        Args:
            frames_data: Lista de dicts con métricas por frame
            representative_frame: Frame representativo del segmento (opcional)

        Returns:
            ShotClassification agregada del segmento
        """
        if representative_frame is not None:
            # Usar frame representativo directamente
            return self.classify_frame(representative_frame)

        # Agregar métricas de múltiples frames
        if not frames_data:
            return ShotClassification(
                shot_type=ShotType.UNKNOWN,
                confidence=0.0,
                face_count=0,
                primary_face_coverage=0.0,
                characteristics=[]
            )

        # Usar métricas agregadas si están disponibles
        avg_face_count = np.mean([f.get('face_count', 0) for f in frames_data])
        avg_face_coverage = np.mean([f.get('primary_face_coverage', 0) for f in frames_data])
        avg_edge_density = np.mean([f.get('edge_density', 0) for f in frames_data])

        # Determinar tipo basándose en promedios
        return self._classify_from_metrics(
            avg_face_count, avg_face_coverage, avg_edge_density, frames_data
        )

    def _detect_faces(self, gray: np.ndarray, frame: np.ndarray) -> List[FaceInfo]:
        """Detecta rostros en el frame y analiza sus características"""
        faces = []

        if not self.cascades_loaded or self.face_cascade is None:
            return faces

        h, w = gray.shape
        frame_area = h * w

        # Detectar rostros frontales
        detected = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        # También buscar perfiles si no hay frontales
        if len(detected) == 0 and self.profile_cascade is not None:
            detected = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

        for (x, y, fw, fh) in detected:
            # Calcular cobertura
            face_area = fw * fh
            coverage = face_area / frame_area

            # Determinar posición
            center_x = x + fw / 2
            center_y = y + fh / 2
            position = self._determine_position(center_x, center_y, w, h)

            # Verificar si está enfocado
            face_roi = gray[y:y+fh, x:x+fw]
            sharpness = cv2.Laplacian(face_roi, cv2.CV_64F).var() if face_roi.size > 0 else 0
            in_focus = sharpness > 50

            # Detectar ojos
            eyes_detected = 0
            if self.eye_cascade is not None and face_roi.size > 0:
                eyes = self.eye_cascade.detectMultiScale(face_roi, 1.1, 3)
                eyes_detected = len(eyes)

            # Verificar si está cortado
            is_partial = (x < 5 or y < 5 or x + fw > w - 5 or y + fh > h - 5)

            faces.append(FaceInfo(
                bbox=(x, y, fw, fh),
                coverage=coverage,
                position=position,
                in_focus=in_focus,
                sharpness=sharpness,
                eyes_detected=eyes_detected,
                is_partial=is_partial
            ))

        # Ordenar por cobertura (más grande primero)
        faces.sort(key=lambda f: f.coverage, reverse=True)

        return faces

    def _determine_position(self, x: float, y: float, w: int, h: int) -> str:
        """Determina la posición de un punto en el frame"""
        # Dividir en tercios
        x_third = x / w
        y_third = y / h

        if x_third < 0.33:
            h_pos = "left"
        elif x_third > 0.66:
            h_pos = "right"
        else:
            h_pos = "center"

        if y_third < 0.33:
            v_pos = "top"
        elif y_third > 0.66:
            v_pos = "bottom"
        else:
            v_pos = "middle"

        if h_pos == "center" and v_pos == "middle":
            return "center"
        elif v_pos == "middle":
            return h_pos
        elif h_pos == "center":
            return v_pos
        else:
            return f"{v_pos}_{h_pos}"

    def _analyze_frame_composition(self, gray: np.ndarray, frame: np.ndarray) -> dict:
        """Analiza la composición general del frame"""
        h, w = gray.shape

        # Detectar bordes
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.mean(edges) / 255.0

        # Distribución de bordes por zonas
        thirds_h = h // 3
        thirds_w = w // 3

        edge_distribution = np.zeros((3, 3))
        for i in range(3):
            for j in range(3):
                region = edges[i*thirds_h:(i+1)*thirds_h, j*thirds_w:(j+1)*thirds_w]
                edge_distribution[i, j] = np.mean(region) / 255.0

        # Detectar si hay blur en primer plano (esquinas inferiores)
        bottom_left = gray[2*thirds_h:, :thirds_w]
        bottom_right = gray[2*thirds_h:, 2*thirds_w:]
        center = gray[thirds_h:2*thirds_h, thirds_w:2*thirds_w]

        bl_sharpness = cv2.Laplacian(bottom_left, cv2.CV_64F).var() if bottom_left.size > 0 else 0
        br_sharpness = cv2.Laplacian(bottom_right, cv2.CV_64F).var() if bottom_right.size > 0 else 0
        center_sharpness = cv2.Laplacian(center, cv2.CV_64F).var() if center.size > 0 else 0

        # Ratio de nitidez (detecta OTS con hombro borroso)
        foreground_sharpness = (bl_sharpness + br_sharpness) / 2
        foreground_blur_ratio = 0
        if center_sharpness > 0:
            foreground_blur_ratio = 1 - (foreground_sharpness / center_sharpness)

        # Detectar si hay elemento en primer plano (para OTS)
        has_foreground_element = foreground_blur_ratio > self.thresholds['foreground_blur_threshold']

        return {
            'edge_density': edge_density,
            'edge_distribution': edge_distribution,
            'center_sharpness': center_sharpness,
            'foreground_sharpness': foreground_sharpness,
            'foreground_blur_ratio': foreground_blur_ratio,
            'has_foreground_element': has_foreground_element,
        }

    def _analyze_depth_of_field(self, gray: np.ndarray) -> dict:
        """Analiza la profundidad de campo del frame"""
        h, w = gray.shape

        # Dividir en centro vs bordes
        margin_h = h // 4
        margin_w = w // 4

        center = gray[margin_h:h-margin_h, margin_w:w-margin_w]
        edges_regions = [
            gray[0:margin_h, :],           # Top
            gray[h-margin_h:, :],          # Bottom
            gray[:, 0:margin_w],           # Left
            gray[:, w-margin_w:]           # Right
        ]

        center_sharpness = cv2.Laplacian(center, cv2.CV_64F).var() if center.size > 0 else 0

        edge_sharpnesses = []
        for region in edges_regions:
            if region.size > 0:
                edge_sharpnesses.append(cv2.Laplacian(region, cv2.CV_64F).var())

        avg_edge_sharpness = np.mean(edge_sharpnesses) if edge_sharpnesses else 0

        # Ratio centro/bordes
        sharpness_ratio = center_sharpness / (avg_edge_sharpness + 0.001)

        # DOF poco profundo si el centro es mucho más nítido
        is_shallow_dof = sharpness_ratio > self.thresholds['shallow_dof_ratio']

        return {
            'center_sharpness': center_sharpness,
            'edge_sharpness': avg_edge_sharpness,
            'sharpness_ratio': sharpness_ratio,
            'is_shallow_dof': is_shallow_dof,
        }

    def _determine_shot_type(self, faces: List[FaceInfo], composition: dict,
                             dof_info: dict, motion_data: dict,
                             frame_size: Tuple[int, int]) -> ShotClassification:
        """
        Determina el tipo de plano basándose en toda la información recopilada.
        """
        characteristics = []
        details = {}

        # Agregar características de DOF
        if dof_info.get('is_shallow_dof'):
            characteristics.append('shallow_dof')

        # Caso 1: Hay rostros detectados
        if faces:
            return self._classify_with_faces(faces, composition, dof_info, characteristics)

        # Caso 2: No hay rostros - clasificar por composición
        return self._classify_without_faces(composition, dof_info, motion_data, characteristics)

    def _classify_with_faces(self, faces: List[FaceInfo], composition: dict,
                             dof_info: dict, characteristics: List[str]) -> ShotClassification:
        """Clasifica cuando hay rostros detectados"""
        face_count = len(faces)
        primary_face = faces[0]
        primary_coverage = primary_face.coverage

        # Agregar características de rostros
        if primary_face.in_focus:
            characteristics.append('face_in_focus')
        if primary_face.is_partial:
            characteristics.append('face_partial')

        details = {
            'face_count': face_count,
            'primary_face_coverage': primary_coverage,
            'primary_face_position': primary_face.position,
            'primary_face_in_focus': primary_face.in_focus,
        }

        # Detectar Over the Shoulder
        if (composition.get('has_foreground_element') and
            face_count >= 1 and
            primary_face.position in ['left', 'right', 'center']):
            characteristics.append('foreground_blur')
            return ShotClassification(
                shot_type=ShotType.OVER_SHOULDER,
                confidence=0.75,
                face_count=face_count,
                primary_face_coverage=primary_coverage,
                characteristics=characteristics,
                details=details
            )

        # Clasificar por cantidad de rostros
        if face_count >= 3:
            return ShotClassification(
                shot_type=ShotType.GROUP,
                confidence=0.85,
                face_count=face_count,
                primary_face_coverage=primary_coverage,
                characteristics=characteristics,
                details=details
            )

        if face_count == 2:
            return ShotClassification(
                shot_type=ShotType.TWO_SHOT,
                confidence=0.85,
                face_count=face_count,
                primary_face_coverage=primary_coverage,
                characteristics=characteristics,
                details=details
            )

        # Un solo rostro - clasificar por cobertura
        if primary_coverage >= self.thresholds['extreme_closeup_min_coverage']:
            shot_type = ShotType.EXTREME_CLOSEUP
            confidence = 0.9
        elif primary_coverage >= self.thresholds['closeup_min_coverage']:
            shot_type = ShotType.CLOSEUP
            confidence = 0.85
        elif primary_coverage >= self.thresholds['medium_closeup_min_coverage']:
            shot_type = ShotType.MEDIUM_CLOSEUP
            confidence = 0.8
        elif primary_coverage >= self.thresholds['medium_min_coverage']:
            shot_type = ShotType.MEDIUM
            confidence = 0.75
        elif primary_coverage >= self.thresholds['medium_wide_min_coverage']:
            shot_type = ShotType.MEDIUM_WIDE
            confidence = 0.7
        else:
            shot_type = ShotType.WIDE
            confidence = 0.65

        return ShotClassification(
            shot_type=shot_type,
            confidence=confidence,
            face_count=face_count,
            primary_face_coverage=primary_coverage,
            characteristics=characteristics,
            details=details
        )

    def _classify_without_faces(self, composition: dict, dof_info: dict,
                                motion_data: dict,
                                characteristics: List[str]) -> ShotClassification:
        """Clasifica cuando no hay rostros detectados"""
        edge_density = composition.get('edge_density', 0)
        is_shallow_dof = dof_info.get('is_shallow_dof', False)

        details = {
            'edge_density': edge_density,
            'shallow_dof': is_shallow_dof,
        }

        # Detectar POV por patrón de movimiento
        if motion_data:
            motion_pattern = motion_data.get('motion_pattern', '')
            if motion_pattern == 'walking' or self._is_pov_motion(motion_data):
                characteristics.append('pov_motion')
                return ShotClassification(
                    shot_type=ShotType.POV,
                    confidence=0.7,
                    face_count=0,
                    primary_face_coverage=0,
                    characteristics=characteristics,
                    details=details
                )

        # Plano detalle: alta densidad de bordes + DOF poco profundo
        if edge_density > self.thresholds['detail_edge_density_min'] and is_shallow_dof:
            characteristics.append('high_detail')
            return ShotClassification(
                shot_type=ShotType.DETAIL,
                confidence=0.75,
                face_count=0,
                primary_face_coverage=0,
                characteristics=characteristics,
                details=details
            )

        # Insert: densidad media-alta, probablemente objeto narrativo
        if edge_density > 0.1:
            return ShotClassification(
                shot_type=ShotType.INSERT,
                confidence=0.6,
                face_count=0,
                primary_face_coverage=0,
                characteristics=characteristics,
                details=details
            )

        # Plano general: baja densidad de bordes, sin rostros
        if edge_density < self.thresholds['wide_edge_density_max']:
            characteristics.append('low_detail')
            return ShotClassification(
                shot_type=ShotType.EXTREME_WIDE,
                confidence=0.7,
                face_count=0,
                primary_face_coverage=0,
                characteristics=characteristics,
                details=details
            )

        # Por defecto: plano general
        return ShotClassification(
            shot_type=ShotType.WIDE,
            confidence=0.5,
            face_count=0,
            primary_face_coverage=0,
            characteristics=characteristics,
            details=details
        )

    def _is_pov_motion(self, motion_data: dict) -> bool:
        """Detecta si el patrón de movimiento es tipo POV/caminata"""
        if not motion_data:
            return False

        # POV típico: movimiento vertical oscilante (cabeceo al caminar)
        # + movimiento horizontal consistente
        vertical_component = motion_data.get('vertical_component', 0)
        motion_magnitude = motion_data.get('motion_magnitude', 0)

        # Hay movimiento significativo con componente vertical
        if motion_magnitude > 1.5 and vertical_component > 0.3:
            return True

        return False

    def _classify_from_metrics(self, avg_face_count: float, avg_face_coverage: float,
                               avg_edge_density: float,
                               frames_data: List[dict]) -> ShotClassification:
        """Clasifica basándose en métricas promediadas"""
        characteristics = []

        if avg_face_count >= 2.5:
            shot_type = ShotType.GROUP
            confidence = 0.7
        elif avg_face_count >= 1.5:
            shot_type = ShotType.TWO_SHOT
            confidence = 0.7
        elif avg_face_count >= 0.5:
            # Clasificar por cobertura
            if avg_face_coverage >= self.thresholds['extreme_closeup_min_coverage']:
                shot_type = ShotType.EXTREME_CLOSEUP
                confidence = 0.75
            elif avg_face_coverage >= self.thresholds['closeup_min_coverage']:
                shot_type = ShotType.CLOSEUP
                confidence = 0.7
            elif avg_face_coverage >= self.thresholds['medium_min_coverage']:
                shot_type = ShotType.MEDIUM
                confidence = 0.65
            else:
                shot_type = ShotType.WIDE
                confidence = 0.6
        else:
            # Sin rostros
            if avg_edge_density > self.thresholds['detail_edge_density_min']:
                shot_type = ShotType.DETAIL
                confidence = 0.6
            elif avg_edge_density < self.thresholds['wide_edge_density_max']:
                shot_type = ShotType.EXTREME_WIDE
                confidence = 0.6
            else:
                shot_type = ShotType.WIDE
                confidence = 0.5

        return ShotClassification(
            shot_type=shot_type,
            confidence=confidence,
            face_count=int(round(avg_face_count)),
            primary_face_coverage=avg_face_coverage,
            characteristics=characteristics,
            details={
                'avg_face_count': avg_face_count,
                'avg_face_coverage': avg_face_coverage,
                'avg_edge_density': avg_edge_density,
            }
        )


# Funciones de utilidad

def get_shot_type_display_name(shot_type: ShotType) -> str:
    """Obtiene nombre legible para mostrar en UI"""
    names = {
        ShotType.EXTREME_WIDE: "Plano General Extremo",
        ShotType.WIDE: "Plano General",
        ShotType.MEDIUM_WIDE: "Plano Americano",
        ShotType.MEDIUM: "Plano Medio",
        ShotType.MEDIUM_CLOSEUP: "Plano Medio Corto",
        ShotType.CLOSEUP: "Primer Plano",
        ShotType.EXTREME_CLOSEUP: "Primerísimo Plano",
        ShotType.DETAIL: "Plano Detalle",
        ShotType.OVER_SHOULDER: "Over the Shoulder",
        ShotType.POV: "Punto de Vista",
        ShotType.TWO_SHOT: "Plano Dos",
        ShotType.GROUP: "Plano Grupo",
        ShotType.INSERT: "Insert",
        ShotType.UNKNOWN: "Desconocido",
    }
    return names.get(shot_type, shot_type.value)


def get_shot_type_short_name(shot_type: ShotType) -> str:
    """Obtiene nombre corto para badges/tags"""
    names = {
        ShotType.EXTREME_WIDE: "EWS",
        ShotType.WIDE: "WS",
        ShotType.MEDIUM_WIDE: "MWS",
        ShotType.MEDIUM: "MS",
        ShotType.MEDIUM_CLOSEUP: "MCU",
        ShotType.CLOSEUP: "CU",
        ShotType.EXTREME_CLOSEUP: "ECU",
        ShotType.DETAIL: "DET",
        ShotType.OVER_SHOULDER: "OTS",
        ShotType.POV: "POV",
        ShotType.TWO_SHOT: "2S",
        ShotType.GROUP: "GRP",
        ShotType.INSERT: "INS",
        ShotType.UNKNOWN: "?",
    }
    return names.get(shot_type, "?")


if __name__ == "__main__":
    # Test básico
    classifier = ShotClassifier()
    print("ShotClassifier inicializado correctamente")
    print(f"Haar cascades loaded: {classifier.cascades_loaded}")
    print(f"Tipos de plano disponibles: {[t.value for t in ShotType]}")
