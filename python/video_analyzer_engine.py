#!/usr/bin/env python3
"""
Video Analyzer Engine v5.0
- Segmentación inteligente (detecta cambios reales)
- Clasificación de tipo de toma
- Evaluación contextual por tipo
- Expediente completo con explicaciones
- NUEVO: Detección de basura (tapa, negro, pre/post roll, etc.)
"""

import cv2
import numpy as np
import subprocess
import json
from pathlib import Path
from collections import deque

# Importar detector de basura
from garbage_detector import GarbageDetector, GarbageType, get_garbage_summary

# Importar clasificador de planos (Fase 2)
from shot_classifier import ShotClassifier, ShotType, get_shot_type_display_name, get_shot_type_short_name

# Importar analizador de rostros (Fase 3)
from face_analyzer import FaceAnalyzer, FaceAnalysisResult, EyeState, summarize_face_analysis

# Importar agrupador de escenas (Fase 4)
from scene_grouper import SceneGrouper, SceneAnalysisResult, get_scene_summary

# Importar detector de takes repetidos (Fase 5)
from take_detector import TakeDetector, TakeDetectionResult, get_take_summary

# Importar etiquetador contextual (Fase 6)
from context_tagger import ContextTagger, TaggingResult, get_tagging_summary

# Importar consolidador de segmentos (Fase 7)
from segment_consolidator import consolidate_video_segments, ConsolidationConfig


class VideoAnalyzerV5:
    """Motor de análisis con segmentación inteligente y explicabilidad"""
    
    # Tipos de toma
    SHOT_STATIC = "ESTATICA"
    SHOT_PAN = "PANEO"
    SHOT_TILT = "TILT"
    SHOT_TRACKING = "TRACKING"
    SHOT_FLUID = "MOVIMIENTO_FLUIDO"
    SHOT_SHAKY = "SHAKY"
    SHOT_TRANSITION = "TRANSICION"
    
    def __init__(self, config=None):
        self.config = config or {}

        # Categorías de análisis técnico activas (del frontend)
        # Por defecto todas activas
        self.analysis_categories = self.config.get('analysis_categories', {
            'stability': True,
            'focus': True,
            'exposure': True,
            'composition': True,
        })

        # Opciones de análisis inteligente (del frontend)
        # Por defecto todas activas
        intelligent = self.config.get('intelligent_analysis', {
            'garbage_detection': True,
            'shot_classification': True,
            'face_analysis': True,
            'scene_grouping': True,
            'take_detection': True,
            'key_moments': True,
        })

        # Inicializar detector de basura (Fase 1)
        self.garbage_detector = GarbageDetector(config)
        self.detect_garbage = intelligent.get('garbage_detection', True)

        # Inicializar clasificador de planos (Fase 2)
        self.shot_classifier = ShotClassifier(config)
        self.classify_shots = intelligent.get('shot_classification', True)

        # Inicializar analizador de rostros (Fase 3)
        self.face_analyzer = FaceAnalyzer(config)
        self.analyze_faces = intelligent.get('face_analysis', True)

        # Inicializar agrupador de escenas (Fase 4)
        self.scene_grouper = SceneGrouper(config)
        self.group_scenes = intelligent.get('scene_grouping', True)

        # Inicializar detector de takes repetidos (Fase 5)
        self.take_detector = TakeDetector(config)
        self.detect_takes = intelligent.get('take_detection', True)

        # Inicializar etiquetador contextual (Fase 6) - también controla key moments
        self.context_tagger = ContextTagger(config)
        self.tag_segments = intelligent.get('key_moments', True)

        # Umbrales para detección de tipo de toma
        self.thresholds = {
            'static_max_motion': 0.8,        # Máximo movimiento para considerarse estática
            'pan_direction_consistency': 0.75, # 75% consistencia direccional para paneo
            'pan_horizontal_dominance': 0.7,  # 70% horizontal para ser paneo (vs tilt)
            'fluid_max_frequency': 4.0,       # Hz máximos para movimiento fluido
            'shaky_min_frequency': 6.0,       # Hz mínimos para considerarse shaky
            'transition_accel_threshold': 30, # Aceleración para detectar transición
            'segment_min_duration': 0.5,      # Duración mínima de segmento (segundos)
            'change_threshold': 0.4,          # Umbral para detectar cambio de segmento
            # Enfoque/Nitidez
            'focus_min_sharp': 50,            # Mínimo para considerarse "en foco"
            'focus_good': 100,                # Buen enfoque
            'focus_excellent': 200,           # Excelente enfoque
            'focus_discard_threshold': 30,    # Por debajo = DISCARD automático
        }
        
        # Umbrales de calidad por tipo de toma
        self.quality_thresholds = {
            self.SHOT_STATIC: {
                'micro_tremor_max': 0.5,      # Máximo micro-temblor aceptable
                'drift_max': 2.0,             # Máximo drift en pixeles
            },
            self.SHOT_PAN: {
                'speed_consistency_min': 0.8,  # Mínima consistencia de velocidad
                'vertical_stability_max': 1.5, # Máxima variación vertical
                'acceleration_max': 15,        # Máxima aceleración
            },
            self.SHOT_TILT: {
                'speed_consistency_min': 0.8,
                'horizontal_stability_max': 1.5,
                'acceleration_max': 15,
            },
            self.SHOT_FLUID: {
                'smoothness_min': 0.7,         # Mínima suavidad de curva
                'jerk_max': 20,                # Máximo "tirón" (derivada de aceleración)
            },
            self.SHOT_SHAKY: {
                # Siempre penalizado, pero menos si es intencional
                'intentional_pattern': False,
            },
        }
        
        # Umbrales de clasificación final
        self.tier_thresholds = {
            'gold_min': 8.0,
            'silver_min': 6.0,
            'bronze_min': 4.0,
        }

    def analyze_video(self, video_path):
        """Análisis completo de video con segmentación inteligente y detección de basura"""

        video_path = Path(video_path)
        if not video_path.exists():
            return {'success': False, 'error': 'Archivo no encontrado', 'filename': video_path.name}

        # Obtener metadata
        metadata = self._get_video_metadata(video_path)
        if not metadata:
            return {'success': False, 'error': 'No se pudo leer metadata', 'filename': video_path.name}

        # Extraer frames y calcular optical flow
        frames_data = self._extract_and_analyze_frames(video_path, metadata)
        if not frames_data:
            return {'success': False, 'error': 'No se pudieron analizar frames', 'filename': video_path.name}

        # NUEVO: Detección de basura (Fase 1)
        garbage_detections = []
        garbage_summary = {}
        if self.detect_garbage:
            garbage_detections = self.garbage_detector.analyze_frames(
                frames_data, metadata['duration']
            )
            garbage_summary = get_garbage_summary(garbage_detections)

        # Segmentación inteligente
        segments = self._segment_video(frames_data, metadata)

        # Clasificar y evaluar cada segmento
        evaluated_segments = []
        for segment in segments:
            evaluated = self._evaluate_segment(segment, metadata)

            # NUEVO: Marcar segmentos que coinciden con basura detectada
            evaluated = self._mark_garbage_segments(evaluated, garbage_detections)

            evaluated_segments.append(evaluated)

        # Calcular estadísticas globales (ahora incluye basura)
        stats = self._calculate_stats(evaluated_segments, metadata['duration'], garbage_summary)

        # Generar rangos por tier para XML
        ranges = self._generate_ranges(evaluated_segments)

        # NUEVO (Fase 4): Agrupar por escenas/setup
        scene_analysis = None
        scene_summary = {}
        if self.group_scenes and evaluated_segments:
            scene_analysis = self.scene_grouper.analyze_project(evaluated_segments)
            scene_summary = get_scene_summary(scene_analysis)

            # Agregar group_id a cada segmento
            for i, seg in enumerate(evaluated_segments):
                seg['scene_group_id'] = scene_analysis.segment_to_group.get(i, -1)
                # Encontrar nombre del grupo
                group_id = seg['scene_group_id']
                for g in scene_analysis.groups:
                    if g.group_id == group_id:
                        seg['scene_group_name'] = g.name
                        break
                else:
                    seg['scene_group_name'] = 'Sin grupo'

        # NUEVO (Fase 5): Detectar takes repetidos
        take_analysis = None
        take_summary = {}
        if self.detect_takes and evaluated_segments:
            take_analysis = self.take_detector.detect_repeated_takes(evaluated_segments)
            take_summary = get_take_summary(take_analysis)

            # Agregar take_group_id a cada segmento
            for i, seg in enumerate(evaluated_segments):
                if i in take_analysis.segment_to_group:
                    seg['take_group_id'] = take_analysis.segment_to_group[i]
                    # Marcar si es el mejor take o un repetido
                    group = next(
                        (g for g in take_analysis.take_groups if g.group_id == seg['take_group_id']),
                        None
                    )
                    if group:
                        # CORREGIDO: Nunca marcar como best_take si es garbage
                        is_best = i == group.best_take and not seg.get('is_garbage', False)
                        seg['is_best_take'] = is_best
                        seg['is_repeated_take'] = i in group.discard_takes
                        seg['take_alternatives'] = len(group.takes) - 1
                else:
                    seg['take_group_id'] = None
                    seg['is_best_take'] = None
                    seg['is_repeated_take'] = False
                    seg['take_alternatives'] = 0

        # NUEVO (Fase 6): Etiquetado contextual
        tagging_result = None
        tagging_summary = {}
        if self.tag_segments and evaluated_segments:
            tagging_result = self.context_tagger.tag_segments(evaluated_segments)
            tagging_summary = get_tagging_summary(tagging_result)

            # Agregar tags a cada segmento
            for seg_tags in tagging_result.segment_tags:
                idx = seg_tags.segment_idx
                if idx < len(evaluated_segments):
                    evaluated_segments[idx]['tags'] = [t.name for t in seg_tags.tags]
                    evaluated_segments[idx]['auto_description'] = seg_tags.auto_description
                    evaluated_segments[idx]['is_key_moment'] = seg_tags.key_moment is not None
                    if seg_tags.key_moment:
                        evaluated_segments[idx]['key_moment_type'] = seg_tags.key_moment.moment_type.value
                        evaluated_segments[idx]['key_moment_reason'] = seg_tags.key_moment.reason

        # =========================================================================
        # FASE 7: Consolidación de segmentos
        # Fusiona micro-segmentos y segmentos similares consecutivos
        # para producir clips más útiles para edición
        # =========================================================================
        original_count = len(evaluated_segments)
        evaluated_segments = consolidate_video_segments(
            evaluated_segments,
            min_duration=2.0,  # Mínimo 2 segundos por segmento
            merge_similar=True  # Fusionar segmentos similares consecutivos
        )
        consolidated_count = len(evaluated_segments)

        # PROTECCIÓN POST-CONSOLIDACIÓN: Asegurar que garbage siempre tenga tier correcto
        # y limpiar flags incorrectos en segmentos garbage
        for seg in evaluated_segments:
            if seg.get('is_garbage'):
                # Forzar tier a garbage
                seg['tier'] = 'garbage'
                seg['action'] = 'Descartar'
                # Limpiar flags que no deberían estar en garbage
                seg['is_key_moment'] = False
                seg['is_best_take'] = False
                seg['key_moment_type'] = None
                seg['key_moment_reason'] = None

        # Recalcular estadísticas después de consolidación
        if consolidated_count != original_count:
            # Recalcular durations por tier
            gold_dur = sum(s['end_time'] - s['start_time'] for s in evaluated_segments if s.get('tier') == 'gold')
            silver_dur = sum(s['end_time'] - s['start_time'] for s in evaluated_segments if s.get('tier') == 'silver')
            bronze_dur = sum(s['end_time'] - s['start_time'] for s in evaluated_segments if s.get('tier') == 'bronze')
            discard_dur = sum(s['end_time'] - s['start_time'] for s in evaluated_segments if s.get('tier') == 'discard')

            total_dur = metadata['duration']
            stats['gold_duration'] = gold_dur
            stats['silver_duration'] = silver_dur
            stats['bronze_duration'] = bronze_dur
            stats['discard_duration'] = discard_dur
            stats['gold_pct'] = (gold_dur / total_dur * 100) if total_dur > 0 else 0
            stats['silver_pct'] = (silver_dur / total_dur * 100) if total_dur > 0 else 0
            stats['bronze_pct'] = (bronze_dur / total_dur * 100) if total_dur > 0 else 0
            stats['discard_pct'] = (discard_dur / total_dur * 100) if total_dur > 0 else 0
            stats['segment_count'] = consolidated_count
            stats['segments_before_consolidation'] = original_count

        return {
            'success': True,
            'filename': video_path.name,
            'path': str(video_path),
            'duration': metadata['duration'],
            'fps': metadata['fps'],
            'width': metadata['width'],
            'height': metadata['height'],
            'segments': evaluated_segments,
            'stats': stats,
            'ranges': ranges,
            'tier_durations': {
                'gold': stats['gold_duration'],
                'silver': stats['silver_duration'],
                'bronze': stats['bronze_duration'],
                'discard': stats['discard_duration'],
            },
            'tier_percentages': {
                'gold': stats['gold_pct'],
                'silver': stats['silver_pct'],
                'bronze': stats['bronze_pct'],
                'discard': stats['discard_pct'],
            },
            # NUEVO: Información de basura
            'garbage': {
                'detections': [d.to_dict() for d in garbage_detections],
                'summary': garbage_summary,
                'total_garbage_duration': garbage_summary.get('total_garbage_duration', 0),
                'garbage_types_found': garbage_summary.get('types_found', []),
            },
            # NUEVO (Fase 4): Información de escenas/setups
            'scenes': {
                'groups': [g.to_dict() for g in scene_analysis.groups] if scene_analysis else [],
                'scene_changes': scene_analysis.scene_changes if scene_analysis else [],
                'summary': scene_summary,
                'total_groups': scene_summary.get('total_groups', 0),
            },
            # NUEVO (Fase 5): Información de takes repetidos
            'takes': {
                'groups': [g.to_dict() for g in take_analysis.take_groups] if take_analysis else [],
                'matches': [m.to_dict() for m in take_analysis.matches] if take_analysis else [],
                'summary': take_summary,
                'total_groups': take_summary.get('total_groups', 0),
                'total_repeated': take_summary.get('total_repeated_takes', 0),
                'potential_savings': take_summary.get('potential_savings_seconds', 0),
            },
            # NUEVO (Fase 6): Información de etiquetado contextual
            'tagging': {
                'segment_tags': [st.to_dict() for st in tagging_result.segment_tags] if tagging_result else [],
                'key_moments': [km.to_dict() for km in tagging_result.key_moments] if tagging_result else [],
                'all_tags': list(tagging_result.all_tags_used) if tagging_result else [],
                'tag_frequency': tagging_result.tag_frequency if tagging_result else {},
                'summary': tagging_summary,
                'total_key_moments': len(tagging_result.key_moments) if tagging_result else 0,
            }
        }

    def _get_video_metadata(self, video_path):
        """Obtiene metadata del video usando ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
            
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                return None
            
            # Calcular FPS
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den if den else 30
            else:
                fps = float(fps_str)
            
            duration = float(data.get('format', {}).get('duration', 0))
            
            return {
                'duration': duration,
                'fps': fps,
                'width': video_stream.get('width', 1920),
                'height': video_stream.get('height', 1080),
                'codec': video_stream.get('codec_name', 'unknown'),
            }
        except Exception as e:
            print(f"Error getting metadata: {e}")
            return None

    def _extract_and_analyze_frames(self, video_path, metadata):
        """Extrae frames y calcula métricas por frame"""
        
        analysis_fps = 10  # FPS para análisis (balance velocidad/precisión)
        target_width = 480  # Resolución de análisis
        target_height = int(480 * metadata['height'] / metadata['width'])
        
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', f'fps={analysis_fps},scale={target_width}:{target_height}',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'
        ]
        
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Error starting ffmpeg: {e}")
            return None
        
        frame_size = target_width * target_height * 3
        frames_data = []
        prev_gray = None
        prev_points = None
        frame_idx = 0
        
        # Buffer para análisis de frecuencia
        motion_history = deque(maxlen=int(analysis_fps * 2))  # 2 segundos
        
        while True:
            raw_frame = process.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                break
            
            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape(
                (target_height, target_width, 3)
            )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            timestamp = frame_idx / analysis_fps
            frame_data = {
                'timestamp': timestamp,
                'frame_idx': frame_idx,
            }
            
            if prev_gray is not None:
                # Optical flow
                flow_data = self._calculate_optical_flow(prev_gray, gray, prev_points)
                frame_data.update(flow_data)

                # Análisis de iluminación
                light_data = self._analyze_lighting(frame)
                frame_data.update(light_data)

                # Análisis de composición
                comp_data = self._analyze_composition(gray)
                frame_data.update(comp_data)

                # Análisis de enfoque/nitidez
                focus_data = self._analyze_focus(gray)
                frame_data.update(focus_data)

                # NUEVO: Análisis de basura por frame
                if self.detect_garbage:
                    garbage_data = self.garbage_detector.analyze_single_frame(frame, gray)
                    frame_data.update(garbage_data)

                # NUEVO: Análisis de rostros para clasificación de planos (cada 5 frames para performance)
                if self.classify_shots and frame_idx % 5 == 0:
                    face_data = self._analyze_faces_for_shot_classification(frame, gray)
                    frame_data.update(face_data)

                motion_history.append(flow_data.get('motion_magnitude', 0))

                # Análisis de frecuencia (si tenemos suficiente historial)
                if len(motion_history) >= analysis_fps:
                    freq_data = self._analyze_frequency(list(motion_history), analysis_fps)
                    frame_data.update(freq_data)
            
            # Preparar para siguiente frame
            prev_gray = gray.copy()
            prev_points = cv2.goodFeaturesToTrack(
                gray, maxCorners=100, qualityLevel=0.3, minDistance=7
            )
            
            frames_data.append(frame_data)
            frame_idx += 1
        
        process.wait()
        return frames_data

    def _calculate_optical_flow(self, prev_gray, gray, prev_points):
        """
        Calcula optical flow con separación de movimiento cámara vs objetos.

        MEJORA v2: Usa Dense Optical Flow (Farnebäck) + Homography estimation
        para distinguir entre:
        - Movimiento de cámara (pan, tilt, shake) - afecta todo el frame uniformemente
        - Movimiento de objetos (personas, autos) - movimiento localizado
        """

        result = {
            'motion_magnitude': 0,
            'motion_direction': 0,
            'direction_consistency': 0,
            'horizontal_component': 0,
            'vertical_component': 0,
            'acceleration': 0,
            # Nuevas métricas v2
            'camera_motion': 0,        # Movimiento estimado de cámara
            'object_motion': 0,        # Movimiento de objetos en escena
            'motion_uniformity': 0,    # Qué tan uniforme es el movimiento (1=todo igual, 0=caótico)
            'is_camera_shake': False,  # True si parece shake no intencional
        }

        # === PARTE 1: Sparse Flow (método original mejorado) ===
        if prev_points is None or len(prev_points) < 10:
            prev_points = cv2.goodFeaturesToTrack(
                prev_gray, maxCorners=100, qualityLevel=0.3, minDistance=7
            )

        if prev_points is None or len(prev_points) < 10:
            return result

        # Calcular optical flow sparse
        next_points, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, gray, prev_points, None
        )

        if next_points is None:
            return result

        # Filtrar puntos válidos
        good_old = prev_points[status == 1]
        good_new = next_points[status == 1]

        if len(good_old) < 5:
            return result

        # Calcular vectores de movimiento
        motion_vectors = good_new - good_old

        # Magnitud promedio
        magnitudes = np.sqrt(motion_vectors[:, 0]**2 + motion_vectors[:, 1]**2)
        result['motion_magnitude'] = float(np.mean(magnitudes))

        # Dirección promedio
        angles = np.arctan2(motion_vectors[:, 1], motion_vectors[:, 0])
        result['motion_direction'] = float(np.mean(angles))

        # Consistencia de dirección
        angle_std = np.std(angles)
        result['direction_consistency'] = float(max(0, 1 - angle_std / np.pi))

        # Componentes horizontal y vertical
        result['horizontal_component'] = float(np.mean(np.abs(motion_vectors[:, 0])))
        result['vertical_component'] = float(np.mean(np.abs(motion_vectors[:, 1])))

        # === PARTE 2: Separación Cámara vs Objeto (NUEVO) ===
        try:
            if len(good_old) >= 8:
                # Estimar homografía (transformación de cámara)
                # Si la cámara se mueve, todos los puntos se mueven de forma similar
                H, mask = cv2.findHomography(good_old, good_new, cv2.RANSAC, 3.0)

                if H is not None and mask is not None:
                    # Puntos que siguen la homografía = movimiento de cámara
                    inliers = mask.ravel() == 1
                    outliers = mask.ravel() == 0

                    inlier_count = np.sum(inliers)
                    outlier_count = np.sum(outliers)
                    total = len(mask)

                    # Uniformidad: qué porcentaje de puntos siguen el movimiento de cámara
                    result['motion_uniformity'] = float(inlier_count / total) if total > 0 else 0

                    # Movimiento de cámara: promedio de los inliers
                    if inlier_count > 0:
                        camera_magnitudes = magnitudes[inliers]
                        result['camera_motion'] = float(np.mean(camera_magnitudes))

                    # Movimiento de objetos: promedio de los outliers (movimiento diferente)
                    if outlier_count > 0:
                        object_magnitudes = magnitudes[outliers]
                        result['object_motion'] = float(np.mean(object_magnitudes))

                    # Detectar shake: movimiento alto + muy uniforme + no direccional
                    # (shake afecta todo el frame pero sin dirección consistente)
                    is_high_motion = result['camera_motion'] > 1.5
                    is_uniform = result['motion_uniformity'] > 0.7
                    is_random_direction = result['direction_consistency'] < 0.5
                    has_tremor_pattern = angle_std > 0.8  # Direcciones muy variadas

                    result['is_camera_shake'] = bool(
                        is_high_motion and is_uniform and (is_random_direction or has_tremor_pattern)
                    )
        except Exception as e:
            # Si falla la homografía, usar valores por defecto
            result['camera_motion'] = result['motion_magnitude']
            result['object_motion'] = 0
            result['motion_uniformity'] = result['direction_consistency']

        return result

    def _analyze_lighting(self, frame):
        """Analiza iluminación del frame"""
        
        # Convertir a HSV para análisis de luminosidad
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        
        mean_brightness = np.mean(v_channel) / 255.0
        std_brightness = np.std(v_channel) / 255.0
        
        # Detectar sobre/subexposición
        overexposed = np.sum(v_channel > 250) / v_channel.size
        underexposed = np.sum(v_channel < 5) / v_channel.size
        
        # Calcular contraste
        contrast = std_brightness / (mean_brightness + 0.001)
        
        return {
            'brightness': float(mean_brightness),
            'brightness_std': float(std_brightness),
            'contrast': float(contrast),
            'overexposed_pct': float(overexposed),
            'underexposed_pct': float(underexposed),
        }

    def _analyze_composition(self, gray):
        """Analiza composición del frame"""
        
        h, w = gray.shape
        
        # Dividir en tercios para regla de tercios
        third_h, third_w = h // 3, w // 3
        
        # Detectar bordes para encontrar puntos de interés
        edges = cv2.Canny(gray, 50, 150)
        
        # Calcular "peso" visual en cada tercio
        weights = np.zeros((3, 3))
        for i in range(3):
            for j in range(3):
                region = edges[i*third_h:(i+1)*third_h, j*third_w:(j+1)*third_w]
                weights[i, j] = np.mean(region)
        
        # Balance horizontal
        left_weight = np.sum(weights[:, 0])
        right_weight = np.sum(weights[:, 2])
        h_balance = 1 - abs(left_weight - right_weight) / (left_weight + right_weight + 0.001)
        
        # Balance vertical
        top_weight = np.sum(weights[0, :])
        bottom_weight = np.sum(weights[2, :])
        v_balance = 1 - abs(top_weight - bottom_weight) / (top_weight + bottom_weight + 0.001)
        
        # Interés en puntos de tercios (intersecciones)
        thirds_interest = (weights[1, 0] + weights[1, 2] + weights[0, 1] + weights[2, 1]) / 4
        
        return {
            'h_balance': float(h_balance),
            'v_balance': float(v_balance),
            'thirds_interest': float(thirds_interest),
            'edge_density': float(np.mean(edges) / 255),
        }

    def _analyze_focus(self, gray):
        """
        Analiza el enfoque/nitidez del frame usando varianza del Laplaciano.
        
        - Valores bajos (< 50): Borroso, fuera de foco
        - Valores medios (50-100): Enfoque aceptable
        - Valores altos (> 100): Bien enfocado
        - Valores muy altos (> 200): Muy nítido
        """
        
        # Aplicar filtro Laplaciano
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        
        # Calcular varianza (medida de nitidez)
        variance = laplacian.var()
        
        # También calcular en regiones para detectar enfoque selectivo
        h, w = gray.shape
        center_region = gray[h//4:3*h//4, w//4:3*w//4]
        center_laplacian = cv2.Laplacian(center_region, cv2.CV_64F)
        center_variance = center_laplacian.var()
        
        # Detectar si el centro está más enfocado que los bordes (enfoque selectivo)
        edge_regions = [
            gray[0:h//4, :],           # Top
            gray[3*h//4:, :],          # Bottom
            gray[:, 0:w//4],           # Left
            gray[:, 3*w//4:]           # Right
        ]
        edge_variances = []
        for region in edge_regions:
            if region.size > 0:
                lap = cv2.Laplacian(region, cv2.CV_64F)
                edge_variances.append(lap.var())
        
        edge_variance = np.mean(edge_variances) if edge_variances else variance
        
        # Ratio centro/bordes - si > 1, hay enfoque selectivo en el centro
        focus_ratio = center_variance / (edge_variance + 0.001)
        
        # Clasificación
        if variance < self.thresholds['focus_discard_threshold']:
            focus_quality = 'very_blurry'
        elif variance < self.thresholds['focus_min_sharp']:
            focus_quality = 'blurry'
        elif variance < self.thresholds['focus_good']:
            focus_quality = 'acceptable'
        elif variance < self.thresholds['focus_excellent']:
            focus_quality = 'good'
        else:
            focus_quality = 'excellent'
        
        return {
            'sharpness': float(variance),
            'center_sharpness': float(center_variance),
            'edge_sharpness': float(edge_variance),
            'focus_ratio': float(focus_ratio),
            'focus_quality': focus_quality,
            'is_blurry': variance < self.thresholds['focus_min_sharp'],
        }

    def _analyze_faces_for_shot_classification(self, frame, gray):
        """
        NUEVO (Fase 2+3): Analiza rostros en el frame para clasificación de planos.
        Usa FaceAnalyzer (Fase 3) para métricas detalladas.
        """
        # Usar FaceAnalyzer si está disponible y activo
        if self.analyze_faces and self.face_analyzer.cascades_loaded:
            # Usar versión rápida optimizada para análisis frame-by-frame
            metrics = self.face_analyzer.get_quick_face_metrics(frame, gray)

            return {
                'face_count': metrics.get('face_count', 0),
                'primary_face_coverage': metrics.get('primary_face_coverage', 0),
                'faces_in_focus': metrics.get('faces_in_focus', False),
                'all_faces_in_focus': metrics.get('all_faces_in_focus', False),
                'any_eyes_closed': metrics.get('any_eyes_closed', False),
                'framing_issues_count': metrics.get('framing_issues_count', 0),
                'primary_face_in_focus': metrics.get('primary_face_in_focus', False),
                'primary_eyes_visible': metrics.get('primary_eyes_visible', False),
            }

        # Fallback al shot_classifier si face_analyzer no está disponible
        if not self.shot_classifier.cascades_loaded:
            return {
                'face_count': 0,
                'primary_face_coverage': 0,
                'faces_in_focus': False,
                'all_faces_in_focus': False,
                'any_eyes_closed': False,
                'framing_issues_count': 0,
            }

        h, w = gray.shape
        frame_area = h * w

        # Detectar rostros usando el clasificador
        faces = self.shot_classifier._detect_faces(gray, frame)

        if not faces:
            return {
                'face_count': 0,
                'primary_face_coverage': 0,
                'faces_in_focus': False,
                'all_faces_in_focus': False,
                'any_eyes_closed': False,
                'framing_issues_count': 0,
            }

        primary_face = faces[0]

        return {
            'face_count': len(faces),
            'primary_face_coverage': primary_face.coverage,
            'faces_in_focus': any(f.in_focus for f in faces),
            'all_faces_in_focus': all(f.in_focus for f in faces),
            'face_positions': [f.position for f in faces],
            'primary_face_position': primary_face.position,
            'primary_face_sharpness': primary_face.sharpness,
            'eyes_detected': sum(f.eyes_detected for f in faces),
            'any_face_partial': any(f.is_partial for f in faces),
            'any_eyes_closed': False,  # No disponible sin FaceAnalyzer completo
            'framing_issues_count': sum(1 for f in faces if f.is_partial),
        }

    def _analyze_frequency(self, motion_history, fps):
        """Analiza frecuencia de movimiento para detectar temblor"""
        
        if len(motion_history) < fps:
            return {'dominant_frequency': 0, 'frequency_power': 0}
        
        # FFT del historial de movimiento
        signal = np.array(motion_history) - np.mean(motion_history)
        fft = np.fft.fft(signal)
        freqs = np.fft.fftfreq(len(signal), 1/fps)
        
        # Solo frecuencias positivas
        positive_mask = freqs > 0
        freqs = freqs[positive_mask]
        power = np.abs(fft[positive_mask])
        
        if len(power) == 0:
            return {'dominant_frequency': 0, 'frequency_power': 0}
        
        # Frecuencia dominante
        dominant_idx = np.argmax(power)
        dominant_freq = freqs[dominant_idx]
        
        # Potencia en frecuencias de temblor (5-15 Hz)
        tremor_mask = (freqs >= 5) & (freqs <= 15)
        tremor_power = np.sum(power[tremor_mask]) / (np.sum(power) + 0.001)
        
        return {
            'dominant_frequency': float(dominant_freq),
            'frequency_power': float(power[dominant_idx]),
            'tremor_power': float(tremor_power),
        }

    def _segment_video(self, frames_data, metadata):
        """Segmenta el video detectando cambios naturales"""
        
        if not frames_data:
            return []
        
        segments = []
        current_segment_start = 0
        current_segment_frames = []
        
        min_frames = int(self.thresholds['segment_min_duration'] * 10)  # 10 fps análisis
        
        for i, frame_data in enumerate(frames_data):
            current_segment_frames.append(frame_data)
            
            # Detectar si hay un cambio significativo
            is_change = False
            if i > 0 and len(current_segment_frames) >= min_frames:
                is_change = self._detect_segment_change(
                    current_segment_frames, frame_data, frames_data[i-1]
                )
            
            # Si hay cambio o es el último frame, cerrar segmento
            if is_change or i == len(frames_data) - 1:
                if len(current_segment_frames) >= min_frames:
                    segment = {
                        'start_time': frames_data[current_segment_start]['timestamp'],
                        'end_time': frame_data['timestamp'],
                        'start_frame': current_segment_start,
                        'end_frame': i,
                        'frames': current_segment_frames.copy(),
                    }
                    segments.append(segment)
                    
                    current_segment_start = i
                    current_segment_frames = [frame_data]
        
        return segments

    def _detect_segment_change(self, segment_frames, current_frame, prev_frame):
        """Detecta si hay un cambio significativo que amerite nuevo segmento"""
        
        # Calcular métricas promedio del segmento actual
        avg_motion = np.mean([f.get('motion_magnitude', 0) for f in segment_frames[:-1]])
        avg_direction = np.mean([f.get('motion_direction', 0) for f in segment_frames[:-1]])
        avg_brightness = np.mean([f.get('brightness', 0.5) for f in segment_frames[:-1]])
        
        # Métricas actuales
        curr_motion = current_frame.get('motion_magnitude', 0)
        curr_direction = current_frame.get('motion_direction', 0)
        curr_brightness = current_frame.get('brightness', 0.5)
        
        # Detectar cambios
        motion_change = abs(curr_motion - avg_motion) / (avg_motion + 0.1)
        direction_change = abs(curr_direction - avg_direction) / (np.pi + 0.1)
        brightness_change = abs(curr_brightness - avg_brightness)
        
        # Umbral combinado
        change_score = (motion_change * 0.4 + direction_change * 0.4 + brightness_change * 0.2)
        
        return change_score > self.thresholds['change_threshold']

    def _evaluate_segment(self, segment, metadata):
        """Evalúa un segmento: clasifica tipo y calcula puntuación"""

        frames = segment['frames']

        # Calcular métricas agregadas del segmento
        metrics = self._aggregate_segment_metrics(frames)

        # Clasificar tipo de toma (movimiento)
        shot_type = self._classify_shot_type(metrics)

        # NUEVO (Fase 2): Clasificar tipo de plano cinematográfico
        framing_classification = self._classify_framing_type(frames, metrics)

        # Evaluar calidad según tipo
        quality_eval = self._evaluate_quality_by_type(shot_type, metrics)

        # Calcular puntuación final
        final_score = quality_eval['score']

        # Verificar si está críticamente borroso
        is_blurry = quality_eval.get('is_critically_blurry', False)

        # Si está muy borroso, forzar a discard
        if is_blurry:
            tier = 'discard'
        else:
            tier = self._score_to_tier(final_score)

        # Generar explicación legible para humanos
        human_readable = self._generate_human_readable(shot_type, tier, metrics, quality_eval)

        # Construir expediente completo
        return {
            'start_time': segment['start_time'],
            'end_time': segment['end_time'],
            'duration': segment['end_time'] - segment['start_time'],
            'shot_type': shot_type,  # Tipo de movimiento (ESTATICA, PANEO, etc.)
            'tier': tier,
            'score': final_score,
            'metrics': metrics,
            'evaluation': quality_eval,
            'explanation': self._generate_explanation(shot_type, metrics, quality_eval, tier),
            'human_readable': human_readable,
            'is_blurry': is_blurry,
            # Campos para UI minimalista
            'action': human_readable.get('action', 'Revisar'),
            'has_issue': human_readable.get('has_issue', True),
            # Categorías activas en este análisis
            'analysis_categories': self.analysis_categories,
            # NUEVO (Fase 2): Información de tipo de plano
            'framing': framing_classification,
            'framing_type': framing_classification.get('shot_type', 'DESCONOCIDO'),
            'framing_type_short': framing_classification.get('shot_type_short', '?'),
            'framing_type_display': framing_classification.get('shot_type_display', 'Desconocido'),
            'face_count': framing_classification.get('face_count', 0),
            'faces_in_focus': framing_classification.get('faces_in_focus', False),
            # NUEVO (Fase 3): Información detallada de rostros
            'face_analysis': {
                'has_faces': metrics.get('avg_face_count', 0) > 0,
                'avg_face_count': metrics.get('avg_face_count', 0),
                'faces_in_focus_pct': metrics.get('faces_in_focus_pct', 0),
                'any_eyes_closed': metrics.get('any_eyes_closed_in_segment', False),
                'eyes_closed_frame_pct': metrics.get('eyes_closed_frame_pct', 0),
                'avg_framing_issues': metrics.get('avg_framing_issues', 0),
                'primary_face_coverage': metrics.get('avg_face_coverage', 0),
            },
            'any_eyes_closed': metrics.get('any_eyes_closed_in_segment', False),
        }

    def _classify_framing_type(self, frames, metrics):
        """
        NUEVO (Fase 2): Clasifica el tipo de plano cinematográfico del segmento.
        """
        if not self.classify_shots:
            return {
                'shot_type': 'DESCONOCIDO',
                'shot_type_short': '?',
                'shot_type_display': 'Desconocido',
                'confidence': 0,
                'face_count': 0,
                'faces_in_focus': False,
            }

        # Obtener métricas de rostros agregadas
        face_counts = [f.get('face_count', 0) for f in frames if 'face_count' in f]
        face_coverages = [f.get('primary_face_coverage', 0) for f in frames if 'primary_face_coverage' in f]
        faces_in_focus = [f.get('faces_in_focus', False) for f in frames if 'faces_in_focus' in f]

        avg_face_count = np.mean(face_counts) if face_counts else 0
        avg_face_coverage = np.mean(face_coverages) if face_coverages else 0
        any_faces_in_focus = any(faces_in_focus) if faces_in_focus else False

        # Usar edge_density de métricas agregadas
        edge_density = metrics.get('edge_density', 0.1)

        # Clasificar usando el clasificador
        classification = self.shot_classifier._classify_from_metrics(
            avg_face_count, avg_face_coverage, edge_density, frames
        )

        return {
            'shot_type': classification.shot_type.value,
            'shot_type_key': classification.shot_type.name.lower(),
            'shot_type_short': get_shot_type_short_name(classification.shot_type),
            'shot_type_display': get_shot_type_display_name(classification.shot_type),
            'confidence': classification.confidence,
            'face_count': int(round(avg_face_count)),
            'primary_face_coverage': avg_face_coverage,
            'faces_in_focus': any_faces_in_focus,
            'characteristics': classification.characteristics,
        }

    def _aggregate_segment_metrics(self, frames):
        """Agrega métricas de todos los frames del segmento"""
        
        if not frames:
            return {}
        
        # Movimiento
        motions = [f.get('motion_magnitude', 0) for f in frames if 'motion_magnitude' in f]
        directions = [f.get('motion_direction', 0) for f in frames if 'motion_direction' in f]
        consistencies = [f.get('direction_consistency', 0) for f in frames if 'direction_consistency' in f]
        h_components = [f.get('horizontal_component', 0) for f in frames if 'horizontal_component' in f]
        v_components = [f.get('vertical_component', 0) for f in frames if 'vertical_component' in f]
        
        # Iluminación
        brightnesses = [f.get('brightness', 0.5) for f in frames if 'brightness' in f]
        contrasts = [f.get('contrast', 0) for f in frames if 'contrast' in f]
        
        # Frecuencia
        frequencies = [f.get('dominant_frequency', 0) for f in frames if 'dominant_frequency' in f]
        tremor_powers = [f.get('tremor_power', 0) for f in frames if 'tremor_power' in f]
        
        # Enfoque/Nitidez
        sharpness_values = [f.get('sharpness', 0) for f in frames if 'sharpness' in f]
        blurry_frames = [f.get('is_blurry', False) for f in frames if 'is_blurry' in f]

        # Calcular porcentaje de frames borrosos
        blurry_pct = (sum(blurry_frames) / len(blurry_frames) * 100) if blurry_frames else 0

        # NUEVO (Fase 2): Composición y rostros
        edge_densities = [f.get('edge_density', 0) for f in frames if 'edge_density' in f]
        face_counts = [f.get('face_count', 0) for f in frames if 'face_count' in f]
        face_coverages = [f.get('primary_face_coverage', 0) for f in frames if 'primary_face_coverage' in f]

        # NUEVO (Fase 3): Métricas detalladas de rostros
        any_eyes_closed_list = [f.get('any_eyes_closed', False) for f in frames if 'any_eyes_closed' in f]
        framing_issues_list = [f.get('framing_issues_count', 0) for f in frames if 'framing_issues_count' in f]
        faces_in_focus_list = [f.get('faces_in_focus', False) for f in frames if 'faces_in_focus' in f]

        # NUEVO v2: Métricas de separación cámara/objeto
        camera_motions = [f.get('camera_motion', 0) for f in frames if 'camera_motion' in f]
        object_motions = [f.get('object_motion', 0) for f in frames if 'object_motion' in f]
        motion_uniformities = [f.get('motion_uniformity', 0) for f in frames if 'motion_uniformity' in f]
        is_camera_shakes = [f.get('is_camera_shake', False) for f in frames if 'is_camera_shake' in f]

        return {
            # Movimiento
            'motion_mean': float(np.mean(motions)) if motions else 0,
            'motion_std': float(np.std(motions)) if motions else 0,
            'motion_max': float(np.max(motions)) if motions else 0,
            'direction_mean': float(np.mean(directions)) if directions else 0,
            'direction_consistency': float(np.mean(consistencies)) if consistencies else 0,
            'horizontal_dominance': float(np.mean(h_components) / (np.mean(h_components) + np.mean(v_components) + 0.001)) if h_components else 0.5,
            'vertical_dominance': float(np.mean(v_components) / (np.mean(h_components) + np.mean(v_components) + 0.001)) if v_components else 0.5,
            
            # Velocidad y aceleración
            'speed_consistency': float(1 - np.std(motions) / (np.mean(motions) + 0.001)) if motions else 0,
            
            # Iluminación
            'brightness_mean': float(np.mean(brightnesses)) if brightnesses else 0.5,
            'brightness_std': float(np.std(brightnesses)) if brightnesses else 0,
            'contrast_mean': float(np.mean(contrasts)) if contrasts else 0,
            
            # Frecuencia/Temblor
            'dominant_frequency': float(np.mean(frequencies)) if frequencies else 0,
            'tremor_power': float(np.mean(tremor_powers)) if tremor_powers else 0,
            
            # Enfoque/Nitidez
            'sharpness_mean': float(np.mean(sharpness_values)) if sharpness_values else 0,
            'sharpness_min': float(np.min(sharpness_values)) if sharpness_values else 0,
            'sharpness_std': float(np.std(sharpness_values)) if sharpness_values else 0,
            'blurry_frame_pct': float(blurry_pct),
            'is_segment_blurry': blurry_pct > 50,  # Más del 50% de frames borrosos

            # NUEVO (Fase 2): Composición y rostros
            'edge_density': float(np.mean(edge_densities)) if edge_densities else 0.1,
            'avg_face_count': float(np.mean(face_counts)) if face_counts else 0,
            'avg_face_coverage': float(np.mean(face_coverages)) if face_coverages else 0,

            # NUEVO (Fase 3): Métricas detalladas de rostros
            'any_eyes_closed_in_segment': any(any_eyes_closed_list) if any_eyes_closed_list else False,
            'eyes_closed_frame_pct': (sum(any_eyes_closed_list) / len(any_eyes_closed_list) * 100) if any_eyes_closed_list else 0,
            'avg_framing_issues': float(np.mean(framing_issues_list)) if framing_issues_list else 0,
            'faces_in_focus_pct': (sum(faces_in_focus_list) / len(faces_in_focus_list) * 100) if faces_in_focus_list else 0,

            # NUEVO v2: Métricas de separación cámara/objeto
            'camera_motion_mean': float(np.mean(camera_motions)) if camera_motions else 0,
            'object_motion_mean': float(np.mean(object_motions)) if object_motions else 0,
            'motion_uniformity': float(np.mean(motion_uniformities)) if motion_uniformities else 0,
            'camera_shake_pct': (sum(is_camera_shakes) / len(is_camera_shakes) * 100) if is_camera_shakes else 0,
            'has_camera_shake': (sum(is_camera_shakes) / len(is_camera_shakes) > 0.3) if is_camera_shakes else False,
        }

    def _classify_shot_type(self, metrics):
        """
        Clasifica el tipo de toma basado en métricas.

        MEJORA v2: Usa métricas de separación cámara/objeto para mejor clasificación.
        """

        motion = metrics.get('motion_mean', 0)
        direction_consistency = metrics.get('direction_consistency', 0)
        h_dominance = metrics.get('horizontal_dominance', 0.5)
        v_dominance = metrics.get('vertical_dominance', 0.5)
        frequency = metrics.get('dominant_frequency', 0)
        tremor = metrics.get('tremor_power', 0)

        # NUEVO v2: Métricas de separación cámara/objeto
        camera_motion = metrics.get('camera_motion_mean', motion)
        object_motion = metrics.get('object_motion_mean', 0)
        motion_uniformity = metrics.get('motion_uniformity', 0)
        has_camera_shake = metrics.get('has_camera_shake', False)

        # 1. ¿Es estática? (bajo movimiento de cámara)
        # MEJORA: Usar camera_motion en lugar de motion total
        # Esto permite que haya movimiento de objetos sin penalizar
        effective_camera_motion = camera_motion if camera_motion > 0 else motion
        if effective_camera_motion < self.thresholds['static_max_motion']:
            return self.SHOT_STATIC

        # 2. ¿Es shaky (temblor de cámara)?
        # MEJORA: Usar detección de shake basada en homografía
        if has_camera_shake:
            return self.SHOT_SHAKY
        # Fallback al método anterior
        if tremor > 0.3 or frequency > self.thresholds['shaky_min_frequency']:
            return self.SHOT_SHAKY

        # 3. ¿Es paneo o tilt? (movimiento direccional consistente)
        # MEJORA: Solo contar como pan/tilt si es movimiento de CÁMARA, no de objetos
        is_mostly_camera = motion_uniformity > 0.6 or object_motion < camera_motion * 0.3
        if direction_consistency > self.thresholds['pan_direction_consistency'] and is_mostly_camera:
            if h_dominance > self.thresholds['pan_horizontal_dominance']:
                return self.SHOT_PAN
            elif v_dominance > self.thresholds['pan_horizontal_dominance']:
                return self.SHOT_TILT

        # 4. ¿Es movimiento fluido?
        if frequency < self.thresholds['fluid_max_frequency']:
            return self.SHOT_FLUID

        # 5. Por defecto, tracking o movimiento libre
        return self.SHOT_TRACKING

    def _evaluate_quality_by_type(self, shot_type, metrics):
        """Evalúa calidad según el tipo de toma y las categorías activas"""

        evaluations = []
        is_critically_blurry = False

        # Obtener categorías activas
        stability_active = self.analysis_categories.get('stability', True)
        focus_active = self.analysis_categories.get('focus', True)
        exposure_active = self.analysis_categories.get('exposure', True)
        composition_active = self.analysis_categories.get('composition', True)

        # Evaluar ESTABILIDAD (si está activa)
        if stability_active:
            if shot_type == self.SHOT_STATIC:
                evaluations.extend(self._evaluate_static(metrics))
            elif shot_type == self.SHOT_PAN:
                evaluations.extend(self._evaluate_pan(metrics))
            elif shot_type == self.SHOT_TILT:
                evaluations.extend(self._evaluate_tilt(metrics))
            elif shot_type == self.SHOT_FLUID:
                evaluations.extend(self._evaluate_fluid(metrics))
            elif shot_type == self.SHOT_SHAKY:
                evaluations.extend(self._evaluate_shaky(metrics))
            elif shot_type == self.SHOT_TRACKING:
                evaluations.extend(self._evaluate_tracking(metrics))
            else:
                evaluations.extend(self._evaluate_generic(metrics))

        # Evaluar ENFOQUE (si está activo)
        if focus_active:
            focus_eval = self._evaluate_focus_quality(metrics)
            evaluations.extend(focus_eval)
            is_critically_blurry = metrics.get('sharpness_mean', 100) < self.thresholds['focus_discard_threshold']

        # Evaluar ILUMINACIÓN/EXPOSICIÓN (si está activa)
        if exposure_active:
            evaluations.extend(self._evaluate_lighting_quality(metrics))

        # Evaluar COMPOSICIÓN (si está activa)
        if composition_active:
            evaluations.extend(self._evaluate_composition_quality(metrics))

        # NUEVO: Evaluar CALIDAD DE ROSTROS (si hay rostros detectados)
        # Esta evaluación es crítica porque rostros borrosos o con ojos cerrados
        # son generalmente inutilizables
        if metrics.get('avg_face_count', 0) > 0:
            evaluations.extend(self._evaluate_face_quality(metrics))

        # NUEVO: Evaluar CONTRASTE (afecta calidad visual general)
        if exposure_active:
            evaluations.extend(self._evaluate_contrast_quality(metrics))

        # Si no hay evaluaciones (todas las categorías desactivadas), dar puntuación neutral
        if not evaluations:
            return {
                'score': 7.0,  # Puntuación neutral
                'criteria': [],
                'is_critically_blurry': False,
                'active_categories': self.analysis_categories,
            }

        # Calcular puntuación ponderada
        total_weight = sum(e['weight'] for e in evaluations)
        weighted_score = sum(e['score'] * e['weight'] for e in evaluations)
        final_score = (weighted_score / total_weight) if total_weight > 0 else 5.0

        # Si está críticamente borroso Y el enfoque está activo, forzar puntuación baja
        if is_critically_blurry and focus_active:
            final_score = min(final_score, 3.0)

        return {
            'score': final_score,
            'criteria': evaluations,
            'is_critically_blurry': is_critically_blurry,
            'active_categories': self.analysis_categories,
        }

    def _evaluate_static(self, metrics):
        """
        Evalúa toma estática.

        MEJORA v2: Usa movimiento de CÁMARA en lugar de movimiento total.
        Esto permite que haya personas/objetos moviéndose sin penalizar la toma.
        """
        evaluations = []

        # MEJORA v2: Usar camera_motion en lugar de motion total
        # Si hay separación disponible, usar solo movimiento de cámara
        camera_motion = metrics.get('camera_motion_mean', 0)
        total_motion = metrics.get('motion_mean', 0)
        object_motion = metrics.get('object_motion_mean', 0)

        # Si tenemos datos de separación, usar camera_motion; sino, usar total
        motion = camera_motion if camera_motion > 0 else total_motion

        threshold = self.quality_thresholds[self.SHOT_STATIC]['micro_tremor_max']
        score = 10 * (1 - min(motion / threshold, 1)) if motion < threshold else 0
        evaluations.append({
            'name': 'Estabilidad de cámara',  # Renombrado para claridad
            'value': motion,
            'threshold': threshold,
            'score': score,
            'weight': 0.5,
            'passed': motion < threshold,
            'explanation': f'Movimiento cámara: {motion:.2f}px (máx {threshold}px)'
        })

        # Consistencia (también basada en movimiento de cámara)
        motion_std = metrics.get('motion_std', 0)
        score = 10 * max(0, 1 - motion_std / 0.5)
        evaluations.append({
            'name': 'Consistencia',
            'value': motion_std,
            'threshold': 0.5,
            'score': score,
            'weight': 0.3,
            'passed': motion_std < 0.5,
            'explanation': f'Variación: {motion_std:.2f}px'
        })

        # NUEVO v2: Bonus si hay movimiento de objetos sin movimiento de cámara
        # (toma estática con acción = bien)
        if object_motion > 0.5 and motion < threshold:
            evaluations.append({
                'name': 'Acción en escena',
                'value': object_motion,
                'threshold': 0.5,
                'score': 8.0,  # Bonus
                'weight': 0.1,
                'passed': True,
                'explanation': f'Movimiento de objetos detectado ({object_motion:.1f}px) con cámara estable'
            })

        return evaluations

    def _evaluate_pan(self, metrics):
        """Evalúa paneo"""
        evaluations = []
        
        # Consistencia de velocidad
        consistency = metrics.get('speed_consistency', 0)
        threshold = self.quality_thresholds[self.SHOT_PAN]['speed_consistency_min']
        score = 10 * (consistency / 1.0)
        evaluations.append({
            'name': 'Velocidad uniforme',
            'value': consistency,
            'threshold': threshold,
            'score': score,
            'weight': 0.4,
            'passed': consistency >= threshold,
            'explanation': f'Consistencia: {consistency*100:.0f}% (mín {threshold*100:.0f}%)'
        })
        
        # Estabilidad vertical (no debe haber movimiento vertical en paneo)
        v_component = metrics.get('vertical_dominance', 0) * metrics.get('motion_mean', 0)
        threshold = self.quality_thresholds[self.SHOT_PAN]['vertical_stability_max']
        score = 10 * max(0, 1 - v_component / threshold)
        evaluations.append({
            'name': 'Estabilidad vertical',
            'value': v_component,
            'threshold': threshold,
            'score': score,
            'weight': 0.4,
            'passed': v_component < threshold,
            'explanation': f'Variación vertical: {v_component:.2f}px (máx {threshold}px)'
        })
        
        return evaluations

    def _evaluate_tilt(self, metrics):
        """Evalúa tilt"""
        evaluations = []
        
        # Similar a paneo pero eje invertido
        consistency = metrics.get('speed_consistency', 0)
        threshold = self.quality_thresholds[self.SHOT_TILT]['speed_consistency_min']
        score = 10 * (consistency / 1.0)
        evaluations.append({
            'name': 'Velocidad uniforme',
            'value': consistency,
            'threshold': threshold,
            'score': score,
            'weight': 0.4,
            'passed': consistency >= threshold,
            'explanation': f'Consistencia: {consistency*100:.0f}%'
        })
        
        h_component = metrics.get('horizontal_dominance', 0) * metrics.get('motion_mean', 0)
        threshold = self.quality_thresholds[self.SHOT_TILT]['horizontal_stability_max']
        score = 10 * max(0, 1 - h_component / threshold)
        evaluations.append({
            'name': 'Estabilidad horizontal',
            'value': h_component,
            'threshold': threshold,
            'score': score,
            'weight': 0.4,
            'passed': h_component < threshold,
            'explanation': f'Variación horizontal: {h_component:.2f}px'
        })
        
        return evaluations

    def _evaluate_fluid(self, metrics):
        """Evalúa movimiento fluido"""
        evaluations = []
        
        # Suavidad (frecuencia baja = suave)
        frequency = metrics.get('dominant_frequency', 0)
        threshold = self.thresholds['fluid_max_frequency']
        score = 10 * max(0, 1 - frequency / threshold)
        evaluations.append({
            'name': 'Suavidad',
            'value': frequency,
            'threshold': threshold,
            'score': score,
            'weight': 0.5,
            'passed': frequency < threshold,
            'explanation': f'Frecuencia: {frequency:.1f}Hz (máx {threshold}Hz)'
        })
        
        # Ausencia de temblor
        tremor = metrics.get('tremor_power', 0)
        score = 10 * max(0, 1 - tremor / 0.2)
        evaluations.append({
            'name': 'Sin temblor',
            'value': tremor,
            'threshold': 0.2,
            'score': score,
            'weight': 0.3,
            'passed': tremor < 0.2,
            'explanation': f'Potencia temblor: {tremor*100:.0f}%'
        })
        
        return evaluations

    def _evaluate_shaky(self, metrics):
        """Evalúa toma shaky - generalmente penalizado"""
        evaluations = []
        
        tremor = metrics.get('tremor_power', 0)
        # Shaky siempre tiene puntuación baja
        score = max(0, 4 - tremor * 10)  # Máximo 4 puntos
        evaluations.append({
            'name': 'Nivel de temblor',
            'value': tremor,
            'threshold': 0.1,
            'score': score,
            'weight': 0.7,
            'passed': False,
            'explanation': f'Temblor detectado: {tremor*100:.0f}% - Considerar estabilización'
        })
        
        return evaluations

    def _evaluate_tracking(self, metrics):
        """Evalúa toma de tracking/seguimiento"""
        return self._evaluate_fluid(metrics)  # Similar a fluido

    def _evaluate_generic(self, metrics):
        """Evaluación genérica"""
        return self._evaluate_fluid(metrics)

    def _evaluate_focus_quality(self, metrics):
        """Evalúa calidad de enfoque/nitidez"""
        evaluations = []
        
        sharpness = metrics.get('sharpness_mean', 0)
        sharpness_min = metrics.get('sharpness_min', 0)
        blurry_pct = metrics.get('blurry_frame_pct', 0)
        
        # Evaluación principal de nitidez
        if sharpness < self.thresholds['focus_discard_threshold']:
            score = 0
            passed = False
            explanation = f'MUY BORROSO - Descarte automático (nitidez: {sharpness:.0f})'
        elif sharpness < self.thresholds['focus_min_sharp']:
            score = 3
            passed = False
            explanation = f'Borroso - Fuera de foco (nitidez: {sharpness:.0f})'
        elif sharpness < self.thresholds['focus_good']:
            score = 6
            passed = True
            explanation = f'Enfoque aceptable (nitidez: {sharpness:.0f})'
        elif sharpness < self.thresholds['focus_excellent']:
            score = 8
            passed = True
            explanation = f'Buen enfoque (nitidez: {sharpness:.0f})'
        else:
            score = 10
            passed = True
            explanation = f'Excelente enfoque (nitidez: {sharpness:.0f})'
        
        evaluations.append({
            'name': 'Enfoque',
            'value': sharpness,
            'threshold': self.thresholds['focus_min_sharp'],
            'score': score,
            'weight': 0.25,  # Peso importante - el enfoque es crítico
            'passed': passed,
            'explanation': explanation
        })
        
        # Consistencia de enfoque (¿hay frames borrosos intermitentes?)
        if blurry_pct > 0:
            if blurry_pct > 50:
                score = 2
                passed = False
                explanation = f'{blurry_pct:.0f}% de frames borrosos'
            elif blurry_pct > 20:
                score = 5
                passed = False
                explanation = f'{blurry_pct:.0f}% de frames borrosos'
            else:
                score = 8
                passed = True
                explanation = f'Enfoque estable ({blurry_pct:.0f}% borrosos)'
        else:
            score = 10
            passed = True
            explanation = 'Enfoque consistente'
        
        evaluations.append({
            'name': 'Consistencia enfoque',
            'value': blurry_pct,
            'threshold': 20,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        # NUEVO: Variación de nitidez (detecta rack focus o pérdida de foco)
        sharpness_std = metrics.get('sharpness_std', 0)
        sharpness_mean = metrics.get('sharpness_mean', 100)
        # Calcular coeficiente de variación (normalizado)
        variation_coef = sharpness_std / (sharpness_mean + 1) if sharpness_mean > 0 else 0

        if variation_coef < 0.1:
            score = 10
            passed = True
            explanation = 'Enfoque muy estable durante toda la toma'
        elif variation_coef < 0.2:
            score = 8
            passed = True
            explanation = 'Enfoque estable con variación mínima'
        elif variation_coef < 0.35:
            score = 5
            passed = False
            explanation = f'Variación de enfoque detectada (posible rack focus o pérdida)'
        else:
            score = 3
            passed = False
            explanation = f'Alta variación de enfoque - revisar manualmente'

        evaluations.append({
            'name': 'Estabilidad de enfoque',
            'value': variation_coef,
            'threshold': 0.2,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        return evaluations

    def _evaluate_lighting_quality(self, metrics):
        """Evalúa calidad de iluminación"""
        evaluations = []
        
        # Exposición
        brightness = metrics.get('brightness_mean', 0.5)
        # Óptimo entre 0.4 y 0.7
        if 0.4 <= brightness <= 0.7:
            score = 10
            passed = True
            explanation = f'Exposición correcta ({brightness:.0%})'
        elif brightness < 0.2:
            score = 3
            passed = False
            explanation = f'Subexpuesto ({brightness:.0%})'
        elif brightness > 0.85:
            score = 3
            passed = False
            explanation = f'Sobreexpuesto ({brightness:.0%})'
        else:
            score = 7
            passed = True
            explanation = f'Exposición aceptable ({brightness:.0%})'
        
        evaluations.append({
            'name': 'Exposición',
            'value': brightness,
            'threshold': '0.4-0.7',
            'score': score,
            'weight': 0.15,
            'passed': passed,
            'explanation': explanation
        })
        
        # Consistencia de iluminación
        brightness_std = metrics.get('brightness_std', 0)
        score = 10 * max(0, 1 - brightness_std / 0.1)
        evaluations.append({
            'name': 'Consistencia luz',
            'value': brightness_std,
            'threshold': 0.1,
            'score': score,
            'weight': 0.1,
            'passed': brightness_std < 0.1,
            'explanation': f'Variación: {brightness_std:.1%}'
        })

        return evaluations

    def _evaluate_composition_quality(self, metrics):
        """Evalúa calidad de composición/encuadre"""
        evaluations = []

        # Balance horizontal
        h_balance = metrics.get('h_balance', 0.5)
        if h_balance >= 0.7:
            score = 10
            passed = True
            explanation = f'Balance horizontal bueno ({h_balance:.0%})'
        elif h_balance >= 0.5:
            score = 7
            passed = True
            explanation = f'Balance horizontal aceptable ({h_balance:.0%})'
        else:
            score = 4
            passed = False
            explanation = f'Desbalanceado horizontalmente ({h_balance:.0%})'

        evaluations.append({
            'name': 'Balance horizontal',
            'value': h_balance,
            'threshold': 0.5,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        # Balance vertical
        v_balance = metrics.get('v_balance', 0.5)
        if v_balance >= 0.7:
            score = 10
            passed = True
            explanation = f'Balance vertical bueno ({v_balance:.0%})'
        elif v_balance >= 0.5:
            score = 7
            passed = True
            explanation = f'Balance vertical aceptable ({v_balance:.0%})'
        else:
            score = 4
            passed = False
            explanation = f'Desbalanceado verticalmente ({v_balance:.0%})'

        evaluations.append({
            'name': 'Balance vertical',
            'value': v_balance,
            'threshold': 0.5,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        return evaluations

    def _evaluate_face_quality(self, metrics):
        """
        NUEVO: Evalúa calidad específica de rostros detectados.

        Métricas evaluadas:
        - Rostros en foco (crítico)
        - Ojos cerrados (muy importante)
        - Cobertura del rostro principal
        - Problemas de encuadre de rostros
        """
        evaluations = []

        # 1. ROSTROS EN FOCO (crítico - rostro borroso = inútil)
        faces_in_focus_pct = metrics.get('faces_in_focus_pct', 100)
        if faces_in_focus_pct >= 80:
            score = 10
            passed = True
            explanation = f'Rostros enfocados ({faces_in_focus_pct:.0f}%)'
        elif faces_in_focus_pct >= 50:
            score = 6
            passed = True
            explanation = f'Algunos rostros desenfocados ({faces_in_focus_pct:.0f}% en foco)'
        elif faces_in_focus_pct >= 20:
            score = 3
            passed = False
            explanation = f'Mayoría de rostros desenfocados ({faces_in_focus_pct:.0f}% en foco)'
        else:
            score = 0
            passed = False
            explanation = f'Rostros muy desenfocados ({faces_in_focus_pct:.0f}% en foco)'

        evaluations.append({
            'name': 'Rostros en foco',
            'value': faces_in_focus_pct,
            'threshold': 50,
            'score': score,
            'weight': 0.25,  # Peso alto - rostros borrosos son críticos
            'passed': passed,
            'explanation': explanation
        })

        # 2. OJOS CERRADOS (muy importante - arruina la toma)
        eyes_closed_pct = metrics.get('eyes_closed_frame_pct', 0)
        if eyes_closed_pct == 0:
            score = 10
            passed = True
            explanation = 'Ojos abiertos en toda la toma'
        elif eyes_closed_pct < 10:
            score = 8
            passed = True
            explanation = f'Ojos cerrados en {eyes_closed_pct:.0f}% de frames (parpadeo normal)'
        elif eyes_closed_pct < 30:
            score = 5
            passed = False
            explanation = f'Ojos cerrados en {eyes_closed_pct:.0f}% de frames'
        else:
            score = 2
            passed = False
            explanation = f'Ojos cerrados frecuentemente ({eyes_closed_pct:.0f}%)'

        evaluations.append({
            'name': 'Ojos abiertos',
            'value': 100 - eyes_closed_pct,
            'threshold': 90,
            'score': score,
            'weight': 0.2,  # Peso significativo
            'passed': passed,
            'explanation': explanation
        })

        # 3. COBERTURA DEL ROSTRO (tamaño en frame)
        face_coverage = metrics.get('avg_face_coverage', 0)
        # Cobertura óptima: 5-40% del frame para planos medios/close-ups
        if 0.05 <= face_coverage <= 0.4:
            score = 10
            passed = True
            explanation = f'Tamaño de rostro óptimo ({face_coverage*100:.1f}% del frame)'
        elif face_coverage > 0.4:
            score = 7
            passed = True
            explanation = f'Rostro muy cercano/extreme close-up ({face_coverage*100:.1f}%)'
        elif face_coverage > 0.02:
            score = 6
            passed = True
            explanation = f'Rostro pequeño en frame ({face_coverage*100:.1f}%)'
        else:
            score = 4
            passed = False
            explanation = f'Rostro muy pequeño ({face_coverage*100:.1f}% - difícil ver expresión)'

        evaluations.append({
            'name': 'Tamaño de rostro',
            'value': face_coverage,
            'threshold': 0.05,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        # 4. PROBLEMAS DE ENCUADRE (rostro cortado, etc.)
        framing_issues = metrics.get('avg_framing_issues', 0)
        if framing_issues == 0:
            score = 10
            passed = True
            explanation = 'Encuadre de rostro correcto'
        elif framing_issues < 1:
            score = 7
            passed = True
            explanation = 'Encuadre de rostro aceptable'
        elif framing_issues < 2:
            score = 4
            passed = False
            explanation = f'Problemas de encuadre detectados ({framing_issues:.1f})'
        else:
            score = 2
            passed = False
            explanation = f'Múltiples problemas de encuadre ({framing_issues:.1f})'

        evaluations.append({
            'name': 'Encuadre de rostro',
            'value': framing_issues,
            'threshold': 1,
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        return evaluations

    def _evaluate_contrast_quality(self, metrics):
        """
        NUEVO: Evalúa el contraste de la imagen.

        Bajo contraste = imagen plana/lavada
        Contraste óptimo = imagen con rango dinámico
        Contraste excesivo = posible problema de iluminación
        """
        evaluations = []

        contrast = metrics.get('contrast_mean', 0.5)

        # Contraste óptimo: 0.3-0.7
        if 0.3 <= contrast <= 0.7:
            score = 10
            passed = True
            explanation = f'Contraste óptimo ({contrast:.2f})'
        elif 0.2 <= contrast < 0.3:
            score = 7
            passed = True
            explanation = f'Contraste bajo pero aceptable ({contrast:.2f})'
        elif 0.7 < contrast <= 0.85:
            score = 7
            passed = True
            explanation = f'Contraste alto pero aceptable ({contrast:.2f})'
        elif contrast < 0.2:
            score = 4
            passed = False
            explanation = f'Imagen plana/bajo contraste ({contrast:.2f})'
        else:
            score = 5
            passed = False
            explanation = f'Contraste excesivo ({contrast:.2f})'

        evaluations.append({
            'name': 'Contraste',
            'value': contrast,
            'threshold': '0.3-0.7',
            'score': score,
            'weight': 0.1,
            'passed': passed,
            'explanation': explanation
        })

        return evaluations

    def _score_to_tier(self, score):
        """Convierte puntuación a tier"""
        if score >= self.tier_thresholds['gold_min']:
            return 'gold'
        elif score >= self.tier_thresholds['silver_min']:
            return 'silver'
        elif score >= self.tier_thresholds['bronze_min']:
            return 'bronze'
        else:
            return 'discard'

    def _generate_explanation(self, shot_type, metrics, quality_eval, tier):
        """Genera explicación legible del resultado"""
        
        # Encabezado
        type_names = {
            self.SHOT_STATIC: 'Toma estática',
            self.SHOT_PAN: 'Paneo horizontal',
            self.SHOT_TILT: 'Tilt vertical',
            self.SHOT_FLUID: 'Movimiento fluido',
            self.SHOT_TRACKING: 'Seguimiento/Tracking',
            self.SHOT_SHAKY: 'Toma inestable',
            self.SHOT_TRANSITION: 'Transición',
        }
        
        tier_names = {
            'gold': 'GOLD - Excelente',
            'silver': 'SILVER - Bueno',
            'bronze': 'BRONZE - Aceptable',
            'discard': 'DESCARTAR - Problemas técnicos',
        }
        
        explanation = {
            'shot_type_name': type_names.get(shot_type, shot_type),
            'tier_name': tier_names.get(tier, tier),
            'summary': [],
            'details': [],
        }
        
        # Resumen de criterios pasados/fallados
        passed = [c for c in quality_eval['criteria'] if c.get('passed', False)]
        failed = [c for c in quality_eval['criteria'] if not c.get('passed', True)]
        
        if passed:
            explanation['summary'].append(f"✓ {len(passed)} criterios cumplidos")
        if failed:
            explanation['summary'].append(f"✗ {len(failed)} criterios no cumplidos")
        
        # Detalles de cada criterio
        for criterion in quality_eval['criteria']:
            explanation['details'].append({
                'name': criterion['name'],
                'passed': criterion.get('passed', False),
                'explanation': criterion.get('explanation', ''),
                'score': criterion.get('score', 0),
            })
        
        return explanation

    def _mark_garbage_segments(self, segment, garbage_detections):
        """
        NUEVO: Marca un segmento si coincide con basura detectada.
        Agrega campos 'is_garbage', 'garbage_type', 'garbage_info' al segmento.
        """
        segment['is_garbage'] = False
        segment['garbage_type'] = None
        segment['garbage_info'] = None

        if not garbage_detections:
            return segment

        seg_start = segment['start_time']
        seg_end = segment['end_time']
        seg_duration = seg_end - seg_start

        for detection in garbage_detections:
            # Calcular superposición
            overlap_start = max(seg_start, detection.start_time)
            overlap_end = min(seg_end, detection.end_time)

            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                overlap_ratio = overlap_duration / seg_duration

                # Si >50% del segmento es basura, marcarlo
                if overlap_ratio > 0.5:
                    segment['is_garbage'] = True
                    segment['garbage_type'] = detection.garbage_type.value
                    segment['garbage_info'] = {
                        'type': detection.garbage_type.value,
                        'confidence': detection.confidence,
                        'recoverable': detection.recoverable,
                        'overlap_ratio': overlap_ratio,
                        'details': detection.details
                    }

                    # CORREGIDO: SIEMPRE forzar tier a 'garbage' cuando is_garbage=True
                    # Antes solo lo hacía si recoverable=False, lo cual causaba
                    # que pre_roll/post_roll mantuvieran tier=gold/silver incorrectamente
                    segment['tier'] = 'garbage'
                    segment['action'] = 'Descartar'

                    garbage_names = {
                        'lens_cap': 'Tapa de lente',
                        'black_frame': 'Frame negro',
                        'whiteout': 'Sobreexposición total',
                        'sky_shot': 'Toma de cielo',
                        'ground_shot': 'Toma de piso',
                        'pre_roll': 'Pre-roll (antes de grabar)',
                        'post_roll': 'Post-roll (después de grabar)',
                        'exposure_flash': 'Ajuste de exposición',
                        'cut_at_start': 'Corte abrupto al inicio',
                        'cut_at_end': 'Corte abrupto al final',
                    }
                    if segment.get('human_readable'):
                        segment['human_readable']['summary'] = f"BASURA: {garbage_names.get(detection.garbage_type.value, detection.garbage_type.value)}"

                    break  # Solo marcar con la primera detección que coincida

        return segment

    def _calculate_stats(self, segments, total_duration, garbage_summary=None):
        """Calcula estadísticas globales (actualizado para incluir basura)"""

        gold_dur = sum(s['duration'] for s in segments if s['tier'] == 'gold')
        silver_dur = sum(s['duration'] for s in segments if s['tier'] == 'silver')
        bronze_dur = sum(s['duration'] for s in segments if s['tier'] == 'bronze')
        discard_dur = sum(s['duration'] for s in segments if s['tier'] == 'discard')

        # NUEVO: Calcular duración de basura específicamente
        garbage_dur = sum(s['duration'] for s in segments if s.get('is_garbage', False))

        total = gold_dur + silver_dur + bronze_dur + discard_dur

        stats = {
            'total_duration': total_duration,
            'analyzed_duration': total,
            'gold_duration': gold_dur,
            'silver_duration': silver_dur,
            'bronze_duration': bronze_dur,
            'discard_duration': discard_dur,
            'gold_pct': (gold_dur / total * 100) if total > 0 else 0,
            'silver_pct': (silver_dur / total * 100) if total > 0 else 0,
            'bronze_pct': (bronze_dur / total * 100) if total > 0 else 0,
            'discard_pct': (discard_dur / total * 100) if total > 0 else 0,
            'usable_pct': ((gold_dur + silver_dur) / total * 100) if total > 0 else 0,
            'segment_count': len(segments),
            'shot_types': self._count_shot_types(segments),
            # NUEVO: Estadísticas de basura
            'garbage_duration': garbage_dur,
            'garbage_pct': (garbage_dur / total * 100) if total > 0 else 0,
            'garbage_segment_count': sum(1 for s in segments if s.get('is_garbage', False)),
            'clean_usable_pct': (((gold_dur + silver_dur) - garbage_dur) / total * 100) if total > 0 else 0,
        }

        # Agregar resumen de basura si está disponible
        if garbage_summary:
            stats['garbage_types_found'] = garbage_summary.get('types_found', [])
            stats['garbage_recommendation'] = garbage_summary.get('recommendation', '')

        # NUEVO (Fase 3): Estadísticas de rostros
        segments_with_faces = [s for s in segments if s.get('face_analysis', {}).get('has_faces', False)]
        stats['face_stats'] = {
            'segments_with_faces': len(segments_with_faces),
            'segments_with_faces_pct': (len(segments_with_faces) / len(segments) * 100) if segments else 0,
            'segments_with_eyes_closed': sum(1 for s in segments if s.get('any_eyes_closed', False)),
            'avg_face_count': np.mean([s.get('face_count', 0) for s in segments]) if segments else 0,
        }

        return stats

    def _count_shot_types(self, segments):
        """Cuenta segmentos por tipo de toma"""
        counts = {}
        for s in segments:
            shot_type = s.get('shot_type', 'unknown')
            counts[shot_type] = counts.get(shot_type, 0) + 1
        return counts

    def _generate_ranges(self, segments):
        """Genera rangos por tier para XML de Premiere"""
        ranges = {
            'gold': [],
            'silver': [],
            'bronze': [],
            'discard': [],
        }

        for segment in segments:
            tier = segment.get('tier', 'discard')
            ranges[tier].append({
                'start': segment['start_time'],
                'end': segment['end_time'],
            })

        return ranges

    def _generate_human_readable(self, shot_type, tier, metrics, quality_eval):
        """
        Traduce métricas técnicas a frases comprensibles para editores.
        Devuelve un dict con summary, stability, image_quality, framing y main_issue.
        """

        # Extraer scores de los criterios de evaluación
        criteria = quality_eval.get('criteria', [])

        # Calcular scores por categoría
        stability_scores = []
        focus_scores = []
        exposure_scores = []
        composition_scores = []

        for c in criteria:
            name = c.get('name', '').lower()
            score = c.get('score', 5)

            # Estabilidad: micro-temblor, consistencia, velocidad uniforme, suavidad, temblor
            if any(x in name for x in ['temblor', 'consistencia', 'velocidad', 'suavidad', 'estabilidad']):
                stability_scores.append(score)
            # Enfoque
            elif 'enfoque' in name or 'focus' in name:
                focus_scores.append(score)
            # Exposición/Iluminación
            elif any(x in name for x in ['exposición', 'exposicion', 'luz', 'brillo']):
                exposure_scores.append(score)

        # Calcular promedios (con defaults razonables)
        stability_score = sum(stability_scores) / len(stability_scores) if stability_scores else 7.0
        focus_score = sum(focus_scores) / len(focus_scores) if focus_scores else 7.0
        exposure_score = sum(exposure_scores) / len(exposure_scores) if exposure_scores else 7.0

        # Calidad de imagen = 70% enfoque + 30% exposición
        image_quality_score = (focus_score * 0.7) + (exposure_score * 0.3)

        # Composición/Encuadre - derivar de métricas directamente
        h_balance = metrics.get('h_balance', 0.5)
        v_balance = metrics.get('v_balance', 0.5)
        # Si no hay datos de composición en metrics, usar un valor neutro
        framing_score = ((h_balance + v_balance) / 2) * 10 if h_balance > 0 else 7.0

        def get_status(score):
            if score >= 8: return 'good'
            if score >= 6: return 'warning'
            if score >= 4: return 'poor'
            return 'bad'

        # ============================================
        # FRASES DE ESTABILIDAD
        # ============================================
        stability_phrases = {
            'good': {
                self.SHOT_STATIC: 'Firme, sin temblor',
                self.SHOT_PAN: 'Paneo suave y controlado',
                self.SHOT_TILT: 'Tilt suave y controlado',
                self.SHOT_FLUID: 'Movimiento fluido y estable',
                self.SHOT_TRACKING: 'Seguimiento estable',
                self.SHOT_SHAKY: 'Movimiento intenso pero consistente',
                'default': 'Muy estable'
            },
            'warning': {
                self.SHOT_STATIC: 'Leve micro-temblor, estabilizable',
                self.SHOT_PAN: 'Paneo con ligera irregularidad',
                self.SHOT_TILT: 'Tilt con ligera irregularidad',
                self.SHOT_FLUID: 'Movimiento aceptable',
                self.SHOT_TRACKING: 'Seguimiento con variaciones',
                self.SHOT_SHAKY: 'Temblor moderado',
                'default': 'Estabilidad aceptable'
            },
            'poor': {
                self.SHOT_SHAKY: 'Temblor notable, requiere estabilización',
                'default': 'Inestable, considerar estabilizar'
            },
            'bad': {
                'default': 'Muy inestable, difícil de recuperar'
            }
        }

        # ============================================
        # FRASES DE CALIDAD DE IMAGEN
        # ============================================
        image_quality_phrases = {
            'good': 'Nítido y bien expuesto',
            'warning': {
                'focus_low': 'Ligeramente suave, exposición correcta',
                'exposure_low': 'Enfoque bueno, exposición ajustable',
                'default': 'Calidad aceptable'
            },
            'poor': {
                'focus_low': 'Borroso, difícil de recuperar',
                'exposure_low': 'Problemas de exposición',
                'default': 'Calidad comprometida'
            },
            'bad': {
                'focus_low': 'Fuera de foco, no recuperable',
                'exposure_low': 'Sobre/subexpuesto severamente',
                'default': 'Calidad muy pobre'
            }
        }

        # ============================================
        # FRASES DE ENCUADRE
        # ============================================
        framing_phrases = {
            'good': 'Bien compuesto y balanceado',
            'warning': 'Composición aceptable',
            'poor': 'Encuadre desbalanceado',
            'bad': 'Composición problemática'
        }

        # ============================================
        # OBTENER FRASES SEGÚN STATUS
        # ============================================

        # Estabilidad
        stability_status = get_status(stability_score)
        stability_phrase_dict = stability_phrases.get(stability_status, {})
        if isinstance(stability_phrase_dict, dict):
            stability_phrase = stability_phrase_dict.get(shot_type, stability_phrase_dict.get('default', 'N/A'))
        else:
            stability_phrase = stability_phrase_dict

        # Calidad de imagen
        iq_status = get_status(image_quality_score)
        iq_phrase_dict = image_quality_phrases.get(iq_status, 'N/A')
        if isinstance(iq_phrase_dict, dict):
            if focus_score < exposure_score:
                iq_phrase = iq_phrase_dict.get('focus_low', iq_phrase_dict.get('default', 'N/A'))
            elif exposure_score < focus_score:
                iq_phrase = iq_phrase_dict.get('exposure_low', iq_phrase_dict.get('default', 'N/A'))
            else:
                iq_phrase = iq_phrase_dict.get('default', 'N/A')
        else:
            iq_phrase = iq_phrase_dict

        # Encuadre
        framing_status = get_status(framing_score)
        framing_phrase = framing_phrases.get(framing_status, 'N/A')

        # ============================================
        # DETERMINAR PROBLEMA PRINCIPAL Y RESUMEN
        # ============================================
        scores_map = {
            'stability': stability_score,
            'image_quality': image_quality_score,
            'framing': framing_score
        }

        # Encontrar métrica con peor score
        worst_metric = min(scores_map, key=scores_map.get)
        worst_score = scores_map[worst_metric]

        # Determinar main_issue solo si hay un problema real
        main_issue = None
        main_issue_phrase = None
        if worst_score < 6:
            main_issue = worst_metric
            if worst_metric == 'stability':
                main_issue_phrase = stability_phrase
            elif worst_metric == 'image_quality':
                main_issue_phrase = iq_phrase
            else:
                main_issue_phrase = framing_phrase

        # Generar resumen según tier
        tier_summaries = {
            'gold': 'Toma lista para usar',
            'silver': 'Usable con ajustes menores',
            'bronze': f'Usar solo si es necesario' + (f' - {main_issue_phrase}' if main_issue_phrase else ''),
            'discard': f'Descartado por: {main_issue_phrase}' if main_issue_phrase else 'No usable'
        }

        summary = tier_summaries.get(tier, 'Sin clasificar')

        return {
            'summary': summary,
            'stability': {
                'status': stability_status,
                'phrase': stability_phrase,
                'score': round(stability_score, 1)
            },
            'image_quality': {
                'status': iq_status,
                'phrase': iq_phrase,
                'score': round(image_quality_score, 1)
            },
            'framing': {
                'status': framing_status,
                'phrase': framing_phrase,
                'score': round(framing_score, 1)
            },
            'main_issue': main_issue,
            # Campos para UI minimalista
            'action': self._get_action_text(tier, main_issue, stability_score, image_quality_score, framing_score),
            'has_issue': tier not in ['gold']
        }

    def _get_action_text(self, tier, main_issue, stability_score, image_quality_score, framing_score):
        """Determina qué acción mostrar para un segmento (UI minimalista)"""

        # Gold = listo para usar
        if tier == 'gold':
            return 'Usar'

        # Encontrar el problema principal para Silver/Bronze
        if tier in ['silver', 'bronze']:
            problems = []

            if stability_score < 7:
                problems.append((stability_score, 'Estabilizar'))
            if image_quality_score < 7:
                # Distinguir entre enfoque y exposición
                problems.append((image_quality_score, 'Corregir'))
            if framing_score < 7:
                problems.append((framing_score, 'Reencuadrar'))

            if problems:
                # Ordenar por score (menor = peor problema)
                problems.sort(key=lambda x: x[0])
                return problems[0][1]
            else:
                return 'Revisar'

        # Discard
        return 'Descartar'


# Compatibilidad con versiones anteriores
class VideoAnalyzerV4(VideoAnalyzerV5):
    """Alias para compatibilidad con v4"""
    pass


class VideoAnalyzer(VideoAnalyzerV5):
    """Alias principal para compatibilidad con la app web"""
    pass


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        analyzer = VideoAnalyzerV5()
        result = analyzer.analyze_video(sys.argv[1])
        print(json.dumps(result, indent=2, default=str))
