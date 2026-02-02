#!/usr/bin/env python3
"""
Face Analyzer Module v1.0
Análisis detallado de rostros en video:
- Detección de rostros (frontal y perfil)
- Análisis de ojos (abiertos/cerrados)
- Evaluación de headroom y framing
- Estado de foco específico del rostro
- Problemas de encuadre (rostro cortado, sin headroom)
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum


class FaceFramingIssue(Enum):
    """Problemas de encuadre de rostros"""
    NONE = "none"
    NO_HEADROOM = "no_headroom"           # Sin espacio sobre la cabeza
    TOO_MUCH_HEADROOM = "too_much_headroom"  # Demasiado espacio sobre la cabeza
    FACE_CUT_TOP = "face_cut_top"         # Rostro cortado arriba
    FACE_CUT_BOTTOM = "face_cut_bottom"   # Rostro cortado abajo
    FACE_CUT_LEFT = "face_cut_left"       # Rostro cortado izquierda
    FACE_CUT_RIGHT = "face_cut_right"     # Rostro cortado derecha
    OFF_CENTER = "off_center"             # Rostro muy descentrado
    LOOKING_OUT_OF_FRAME = "looking_out"  # Mirando fuera del frame (nose room)


class EyeState(Enum):
    """Estado de los ojos"""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    UNKNOWN = "unknown"


@dataclass
class DetailedFaceInfo:
    """Información detallada de un rostro detectado"""
    # Posición y tamaño
    bbox: Tuple[int, int, int, int]       # (x, y, w, h)
    center: Tuple[int, int]               # Centro del rostro
    coverage: float                        # % del frame que ocupa

    # Posición relativa
    position_h: str                        # "left", "center", "right"
    position_v: str                        # "top", "middle", "bottom"
    normalized_x: float                    # 0-1, posición horizontal normalizada
    normalized_y: float                    # 0-1, posición vertical normalizada

    # Estado de foco
    in_focus: bool
    sharpness: float
    focus_quality: str                     # "excellent", "good", "acceptable", "soft", "blurry"

    # Ojos
    eyes_detected: int
    left_eye: Optional[Tuple[int, int, int, int]]   # bbox del ojo izquierdo
    right_eye: Optional[Tuple[int, int, int, int]]  # bbox del ojo derecho
    eye_state: EyeState
    both_eyes_visible: bool

    # Encuadre
    headroom_ratio: float                  # Espacio sobre la cabeza (0-1)
    headroom_ok: bool
    chin_room_ratio: float                 # Espacio bajo la barbilla
    is_partial: bool                       # Si está cortado
    framing_issues: List[FaceFramingIssue]

    # Orientación (si es detectable)
    is_frontal: bool
    is_profile: bool

    def to_dict(self):
        return {
            'bbox': self.bbox,
            'center': self.center,
            'coverage': self.coverage,
            'position_h': self.position_h,
            'position_v': self.position_v,
            'normalized_x': self.normalized_x,
            'normalized_y': self.normalized_y,
            'in_focus': self.in_focus,
            'sharpness': self.sharpness,
            'focus_quality': self.focus_quality,
            'eyes_detected': self.eyes_detected,
            'eye_state': self.eye_state.value,
            'both_eyes_visible': self.both_eyes_visible,
            'headroom_ratio': self.headroom_ratio,
            'headroom_ok': self.headroom_ok,
            'chin_room_ratio': self.chin_room_ratio,
            'is_partial': self.is_partial,
            'framing_issues': [issue.value for issue in self.framing_issues],
            'is_frontal': self.is_frontal,
            'is_profile': self.is_profile,
        }


@dataclass
class FaceAnalysisResult:
    """Resultado completo del análisis de rostros de un frame"""
    face_count: int
    faces: List[DetailedFaceInfo]

    # Agregados
    any_in_focus: bool
    all_in_focus: bool
    any_eyes_closed: bool
    any_framing_issues: bool
    best_face_sharpness: float
    worst_face_sharpness: float

    # Para tomas con personas
    primary_face: Optional[DetailedFaceInfo]
    issues_summary: List[str]

    def to_dict(self):
        return {
            'face_count': self.face_count,
            'faces': [f.to_dict() for f in self.faces],
            'any_in_focus': self.any_in_focus,
            'all_in_focus': self.all_in_focus,
            'any_eyes_closed': self.any_eyes_closed,
            'any_framing_issues': self.any_framing_issues,
            'best_face_sharpness': self.best_face_sharpness,
            'worst_face_sharpness': self.worst_face_sharpness,
            'primary_face': self.primary_face.to_dict() if self.primary_face else None,
            'issues_summary': self.issues_summary,
        }


class FaceAnalyzer:
    """
    Analizador detallado de rostros usando OpenCV.
    """

    def __init__(self, config=None):
        self.config = config or {}

        # Cargar clasificadores Haar
        self._load_cascades()

        # Umbrales configurables
        self.thresholds = {
            # Foco
            'focus_excellent': 150,
            'focus_good': 100,
            'focus_acceptable': 60,
            'focus_soft': 40,

            # Headroom (espacio sobre la cabeza)
            'headroom_min': 0.05,          # Mínimo 5% del frame sobre la cabeza
            'headroom_max': 0.25,          # Máximo 25% del frame sobre la cabeza
            'headroom_ideal_min': 0.08,
            'headroom_ideal_max': 0.18,

            # Detección de ojos cerrados
            'eye_aspect_ratio_threshold': 0.2,  # EAR bajo = ojos cerrados

            # Posición
            'center_tolerance': 0.15,       # Tolerancia para considerar "centrado"
            'edge_margin': 10,              # Píxeles de margen para considerar "cortado"
        }

    def _load_cascades(self):
        """Carga los clasificadores Haar de OpenCV"""
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.face_cascade_alt = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
            )
            self.profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_profileface.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            self.eye_cascade_glasses = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye_tree_eyeglasses.xml'
            )
            self.cascades_loaded = True
        except Exception as e:
            print(f"Warning: Could not load Haar cascades: {e}")
            self.cascades_loaded = False

    def analyze_frame(self, frame: np.ndarray, gray: np.ndarray = None) -> FaceAnalysisResult:
        """
        Analiza todos los rostros en un frame.

        Args:
            frame: Frame BGR
            gray: Frame en escala de grises (opcional)

        Returns:
            FaceAnalysisResult con información detallada de todos los rostros
        """
        if gray is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape

        # Detectar rostros
        faces_info = self._detect_and_analyze_faces(frame, gray, h, w)

        # Crear resultado agregado
        if not faces_info:
            return FaceAnalysisResult(
                face_count=0,
                faces=[],
                any_in_focus=False,
                all_in_focus=False,
                any_eyes_closed=False,
                any_framing_issues=False,
                best_face_sharpness=0,
                worst_face_sharpness=0,
                primary_face=None,
                issues_summary=[]
            )

        # Calcular agregados
        any_in_focus = any(f.in_focus for f in faces_info)
        all_in_focus = all(f.in_focus for f in faces_info)
        any_eyes_closed = any(f.eye_state == EyeState.CLOSED for f in faces_info)
        any_framing_issues = any(len(f.framing_issues) > 0 for f in faces_info)

        sharpness_values = [f.sharpness for f in faces_info]
        best_sharpness = max(sharpness_values)
        worst_sharpness = min(sharpness_values)

        # Rostro principal (el más grande o más centrado)
        primary_face = self._select_primary_face(faces_info, w, h)

        # Generar resumen de problemas
        issues = self._generate_issues_summary(faces_info)

        return FaceAnalysisResult(
            face_count=len(faces_info),
            faces=faces_info,
            any_in_focus=any_in_focus,
            all_in_focus=all_in_focus,
            any_eyes_closed=any_eyes_closed,
            any_framing_issues=any_framing_issues,
            best_face_sharpness=best_sharpness,
            worst_face_sharpness=worst_sharpness,
            primary_face=primary_face,
            issues_summary=issues
        )

    def _detect_and_analyze_faces(self, frame: np.ndarray, gray: np.ndarray,
                                   h: int, w: int) -> List[DetailedFaceInfo]:
        """Detecta y analiza todos los rostros en el frame"""
        if not self.cascades_loaded:
            return []

        faces_info = []
        frame_area = h * w

        # Detectar rostros frontales
        frontal_faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        # Si no hay frontales, intentar con cascade alternativo
        if len(frontal_faces) == 0:
            frontal_faces = self.face_cascade_alt.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
            )

        # Procesar rostros frontales
        for (x, y, fw, fh) in frontal_faces:
            face_info = self._analyze_single_face(
                frame, gray, x, y, fw, fh, h, w, frame_area, is_frontal=True
            )
            faces_info.append(face_info)

        # Detectar perfiles si no hay frontales
        if len(faces_info) == 0:
            profile_faces = self.profile_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
            )
            for (x, y, fw, fh) in profile_faces:
                face_info = self._analyze_single_face(
                    frame, gray, x, y, fw, fh, h, w, frame_area, is_frontal=False
                )
                faces_info.append(face_info)

        # Ordenar por cobertura (más grande primero)
        faces_info.sort(key=lambda f: f.coverage, reverse=True)

        return faces_info

    def _analyze_single_face(self, frame: np.ndarray, gray: np.ndarray,
                              x: int, y: int, fw: int, fh: int,
                              h: int, w: int, frame_area: int,
                              is_frontal: bool) -> DetailedFaceInfo:
        """Analiza un rostro individual en detalle"""

        # Calcular cobertura
        face_area = fw * fh
        coverage = face_area / frame_area

        # Calcular centro
        center_x = x + fw // 2
        center_y = y + fh // 2

        # Posición normalizada (0-1)
        normalized_x = center_x / w
        normalized_y = center_y / h

        # Determinar posición categórica
        position_h = self._categorize_horizontal_position(normalized_x)
        position_v = self._categorize_vertical_position(normalized_y)

        # Extraer ROI del rostro
        face_roi_gray = gray[y:y+fh, x:x+fw]
        face_roi_color = frame[y:y+fh, x:x+fw]

        # Analizar foco
        sharpness = cv2.Laplacian(face_roi_gray, cv2.CV_64F).var() if face_roi_gray.size > 0 else 0
        in_focus, focus_quality = self._evaluate_focus(sharpness)

        # Detectar ojos
        eyes_info = self._detect_eyes(face_roi_gray, face_roi_color, fw, fh) if is_frontal else {
            'count': 0, 'left': None, 'right': None, 'state': EyeState.UNKNOWN, 'both_visible': False
        }

        # Calcular headroom
        headroom_ratio = y / h
        chin_room_ratio = (h - (y + fh)) / h

        # Evaluar headroom
        headroom_ok = (self.thresholds['headroom_ideal_min'] <= headroom_ratio <=
                       self.thresholds['headroom_ideal_max'])

        # Detectar si está cortado
        margin = self.thresholds['edge_margin']
        is_partial = (x < margin or y < margin or
                      x + fw > w - margin or y + fh > h - margin)

        # Detectar problemas de encuadre
        framing_issues = self._detect_framing_issues(
            x, y, fw, fh, w, h, headroom_ratio, chin_room_ratio, normalized_x
        )

        return DetailedFaceInfo(
            bbox=(x, y, fw, fh),
            center=(center_x, center_y),
            coverage=coverage,
            position_h=position_h,
            position_v=position_v,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            in_focus=in_focus,
            sharpness=sharpness,
            focus_quality=focus_quality,
            eyes_detected=eyes_info['count'],
            left_eye=eyes_info['left'],
            right_eye=eyes_info['right'],
            eye_state=eyes_info['state'],
            both_eyes_visible=eyes_info['both_visible'],
            headroom_ratio=headroom_ratio,
            headroom_ok=headroom_ok,
            chin_room_ratio=chin_room_ratio,
            is_partial=is_partial,
            framing_issues=framing_issues,
            is_frontal=is_frontal,
            is_profile=not is_frontal
        )

    def _categorize_horizontal_position(self, normalized_x: float) -> str:
        """Categoriza posición horizontal"""
        if normalized_x < 0.33:
            return "left"
        elif normalized_x > 0.66:
            return "right"
        else:
            return "center"

    def _categorize_vertical_position(self, normalized_y: float) -> str:
        """Categoriza posición vertical"""
        if normalized_y < 0.33:
            return "top"
        elif normalized_y > 0.66:
            return "bottom"
        else:
            return "middle"

    def _evaluate_focus(self, sharpness: float) -> Tuple[bool, str]:
        """Evalúa la calidad de foco basado en sharpness"""
        if sharpness >= self.thresholds['focus_excellent']:
            return True, "excellent"
        elif sharpness >= self.thresholds['focus_good']:
            return True, "good"
        elif sharpness >= self.thresholds['focus_acceptable']:
            return True, "acceptable"
        elif sharpness >= self.thresholds['focus_soft']:
            return False, "soft"
        else:
            return False, "blurry"

    def _detect_eyes(self, face_gray: np.ndarray, face_color: np.ndarray,
                     fw: int, fh: int) -> dict:
        """Detecta ojos y su estado en el ROI del rostro"""
        result = {
            'count': 0,
            'left': None,
            'right': None,
            'state': EyeState.UNKNOWN,
            'both_visible': False
        }

        if face_gray.size == 0:
            return result

        # Buscar en la mitad superior del rostro (donde están los ojos)
        eye_region = face_gray[0:int(fh*0.6), :]

        if eye_region.size == 0:
            return result

        # Detectar ojos
        eyes = self.eye_cascade.detectMultiScale(
            eye_region, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15)
        )

        # Si no encuentra, probar con cascade para gafas
        if len(eyes) < 2 and self.eye_cascade_glasses is not None:
            eyes_glasses = self.eye_cascade_glasses.detectMultiScale(
                eye_region, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15)
            )
            if len(eyes_glasses) > len(eyes):
                eyes = eyes_glasses

        result['count'] = len(eyes)

        if len(eyes) >= 2:
            # Ordenar por posición X para identificar izquierdo/derecho
            eyes = sorted(eyes, key=lambda e: e[0])
            result['left'] = tuple(eyes[0])
            result['right'] = tuple(eyes[1])
            result['both_visible'] = True
            result['state'] = EyeState.OPEN
        elif len(eyes) == 1:
            # Solo un ojo visible
            result['left'] = tuple(eyes[0])
            result['state'] = EyeState.PARTIALLY_CLOSED  # O podría ser perfil
        else:
            # Sin ojos detectados - posiblemente cerrados o muy borroso
            # Intentar detectar si es por ojos cerrados vs borroso
            result['state'] = self._infer_eye_state(face_gray, fh)

        return result

    def _infer_eye_state(self, face_gray: np.ndarray, fh: int) -> EyeState:
        """
        Intenta inferir el estado de los ojos cuando no se detectan directamente.
        Usa análisis de textura en la región de los ojos.
        """
        # Región de ojos (tercio superior del rostro)
        eye_region = face_gray[int(fh*0.15):int(fh*0.45), :]

        if eye_region.size == 0:
            return EyeState.UNKNOWN

        # Calcular varianza - ojos abiertos tienen más detalle
        variance = cv2.Laplacian(eye_region, cv2.CV_64F).var()

        # Si hay poca varianza en la región de ojos, probablemente están cerrados
        if variance < 30:
            return EyeState.CLOSED
        elif variance < 60:
            return EyeState.PARTIALLY_CLOSED
        else:
            return EyeState.UNKNOWN  # No podemos determinar con certeza

    def _detect_framing_issues(self, x: int, y: int, fw: int, fh: int,
                                w: int, h: int, headroom_ratio: float,
                                chin_room_ratio: float,
                                normalized_x: float) -> List[FaceFramingIssue]:
        """Detecta problemas de encuadre del rostro"""
        issues = []
        margin = self.thresholds['edge_margin']

        # Verificar cortes
        if y < margin:
            issues.append(FaceFramingIssue.FACE_CUT_TOP)
        if y + fh > h - margin:
            issues.append(FaceFramingIssue.FACE_CUT_BOTTOM)
        if x < margin:
            issues.append(FaceFramingIssue.FACE_CUT_LEFT)
        if x + fw > w - margin:
            issues.append(FaceFramingIssue.FACE_CUT_RIGHT)

        # Verificar headroom
        if headroom_ratio < self.thresholds['headroom_min']:
            issues.append(FaceFramingIssue.NO_HEADROOM)
        elif headroom_ratio > self.thresholds['headroom_max']:
            issues.append(FaceFramingIssue.TOO_MUCH_HEADROOM)

        # Verificar si está muy descentrado (y no es intencional)
        center_tolerance = self.thresholds['center_tolerance']
        if normalized_x < 0.5 - center_tolerance * 2 or normalized_x > 0.5 + center_tolerance * 2:
            # Muy descentrado - podría ser problema o intencional (regla de tercios)
            # Solo marcar como problema si está en el borde extremo
            if normalized_x < 0.2 or normalized_x > 0.8:
                issues.append(FaceFramingIssue.OFF_CENTER)

        return issues

    def _select_primary_face(self, faces: List[DetailedFaceInfo],
                              w: int, h: int) -> DetailedFaceInfo:
        """Selecciona el rostro principal (más importante)"""
        if not faces:
            return None

        if len(faces) == 1:
            return faces[0]

        # Scoring para seleccionar el más importante
        def face_importance_score(face: DetailedFaceInfo) -> float:
            score = 0

            # Tamaño importa mucho
            score += face.coverage * 100

            # Centrado es bueno
            center_dist = abs(face.normalized_x - 0.5) + abs(face.normalized_y - 0.4)
            score -= center_dist * 20

            # En foco es importante
            if face.in_focus:
                score += 30

            # Sin problemas de encuadre
            score -= len(face.framing_issues) * 10

            # Ojos visibles
            if face.both_eyes_visible:
                score += 15

            return score

        return max(faces, key=face_importance_score)

    def _generate_issues_summary(self, faces: List[DetailedFaceInfo]) -> List[str]:
        """Genera un resumen legible de los problemas encontrados"""
        issues = []

        for i, face in enumerate(faces):
            prefix = f"Rostro {i+1}: " if len(faces) > 1 else ""

            # Problemas de foco
            if not face.in_focus:
                issues.append(f"{prefix}Fuera de foco ({face.focus_quality})")

            # Problemas de ojos
            if face.eye_state == EyeState.CLOSED:
                issues.append(f"{prefix}Ojos cerrados")
            elif face.eye_state == EyeState.PARTIALLY_CLOSED:
                issues.append(f"{prefix}Ojos parcialmente cerrados")

            # Problemas de encuadre
            for framing_issue in face.framing_issues:
                issue_names = {
                    FaceFramingIssue.NO_HEADROOM: "Sin espacio sobre la cabeza",
                    FaceFramingIssue.TOO_MUCH_HEADROOM: "Demasiado espacio sobre la cabeza",
                    FaceFramingIssue.FACE_CUT_TOP: "Rostro cortado arriba",
                    FaceFramingIssue.FACE_CUT_BOTTOM: "Rostro cortado abajo",
                    FaceFramingIssue.FACE_CUT_LEFT: "Rostro cortado izquierda",
                    FaceFramingIssue.FACE_CUT_RIGHT: "Rostro cortado derecha",
                    FaceFramingIssue.OFF_CENTER: "Rostro muy descentrado",
                }
                if framing_issue in issue_names:
                    issues.append(f"{prefix}{issue_names[framing_issue]}")

        return issues

    def get_quick_face_metrics(self, frame: np.ndarray, gray: np.ndarray = None) -> dict:
        """
        Versión rápida para uso frame-by-frame durante análisis.
        Retorna solo métricas esenciales.
        """
        if gray is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape

        if not self.cascades_loaded:
            return {
                'face_count': 0,
                'primary_face_coverage': 0,
                'faces_in_focus': False,
                'any_eyes_closed': False,
                'framing_issues_count': 0,
            }

        # Detección rápida
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30)
        )

        if len(faces) == 0:
            return {
                'face_count': 0,
                'primary_face_coverage': 0,
                'faces_in_focus': False,
                'any_eyes_closed': False,
                'framing_issues_count': 0,
            }

        frame_area = h * w
        faces_info = []

        for (x, y, fw, fh) in faces:
            coverage = (fw * fh) / frame_area
            face_gray = gray[y:y+fh, x:x+fw]
            sharpness = cv2.Laplacian(face_gray, cv2.CV_64F).var() if face_gray.size > 0 else 0
            in_focus = sharpness > self.thresholds['focus_acceptable']

            # Quick eye check
            eye_region = face_gray[0:int(fh*0.5), :]
            eyes = self.eye_cascade.detectMultiScale(
                eye_region, scaleFactor=1.2, minNeighbors=2, minSize=(10, 10)
            ) if eye_region.size > 0 else []

            # Quick framing check
            margin = 10
            is_cut = (x < margin or y < margin or
                      x + fw > w - margin or y + fh > h - margin)
            headroom = y / h
            bad_headroom = headroom < 0.03 or headroom > 0.30

            faces_info.append({
                'coverage': coverage,
                'in_focus': in_focus,
                'eyes_visible': len(eyes) >= 2,
                'has_issues': is_cut or bad_headroom
            })

        # Ordenar por cobertura
        faces_info.sort(key=lambda f: f['coverage'], reverse=True)
        primary = faces_info[0]

        return {
            'face_count': len(faces_info),
            'primary_face_coverage': primary['coverage'],
            'faces_in_focus': any(f['in_focus'] for f in faces_info),
            'all_faces_in_focus': all(f['in_focus'] for f in faces_info),
            'any_eyes_closed': not all(f['eyes_visible'] for f in faces_info),
            'framing_issues_count': sum(1 for f in faces_info if f['has_issues']),
            'primary_face_in_focus': primary['in_focus'],
            'primary_eyes_visible': primary['eyes_visible'],
        }


# Funciones de utilidad

def get_face_issue_severity(issues: List[FaceFramingIssue]) -> str:
    """Determina la severidad de los problemas de encuadre"""
    if not issues:
        return "none"

    severe_issues = {
        FaceFramingIssue.FACE_CUT_TOP,
        FaceFramingIssue.FACE_CUT_BOTTOM,
        FaceFramingIssue.NO_HEADROOM,
    }

    if any(issue in severe_issues for issue in issues):
        return "severe"

    moderate_issues = {
        FaceFramingIssue.FACE_CUT_LEFT,
        FaceFramingIssue.FACE_CUT_RIGHT,
        FaceFramingIssue.TOO_MUCH_HEADROOM,
    }

    if any(issue in moderate_issues for issue in issues):
        return "moderate"

    return "minor"


def summarize_face_analysis(result: FaceAnalysisResult) -> str:
    """Genera un resumen de una línea del análisis de rostros"""
    if result.face_count == 0:
        return "Sin rostros detectados"

    parts = []

    # Cantidad
    if result.face_count == 1:
        parts.append("1 rostro")
    else:
        parts.append(f"{result.face_count} rostros")

    # Foco
    if result.all_in_focus:
        parts.append("en foco")
    elif result.any_in_focus:
        parts.append("foco parcial")
    else:
        parts.append("fuera de foco")

    # Ojos
    if result.any_eyes_closed:
        parts.append("ojos cerrados")

    # Problemas
    if result.any_framing_issues:
        parts.append("problemas de encuadre")

    return " | ".join(parts)


if __name__ == "__main__":
    # Test básico
    analyzer = FaceAnalyzer()
    print("FaceAnalyzer inicializado correctamente")
    print(f"Cascades loaded: {analyzer.cascades_loaded}")
