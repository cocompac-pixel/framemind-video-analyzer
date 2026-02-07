#!/usr/bin/env python3
"""
Video Analyzer Web Interface v6.0
Flask backend para la interfaz web
- Segmentación inteligente
- Clasificación de tipo de toma
- Explicabilidad completa
- 4 tracks: GOLD, SILVER, BRONZE, DISCARD
- Thumbnails automáticos
- Vista Best Takes
- Presets por tipo de proyecto
- Sistema de proyectos
- Exportación XML mejorada con bins y opciones
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os
import json
import threading
import time
import subprocess
from pathlib import Path
from datetime import datetime
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importar el analizador v4
from video_analyzer_engine import VideoAnalyzer
from report_generator import generate_detailed_report

# HOTFIX V5.1: Importar chunked upload
try:
    from chunked_upload import ChunkedUploadManager, UploadProgressTracker
    CHUNKED_UPLOAD_AVAILABLE = True
except ImportError:
    CHUNKED_UPLOAD_AVAILABLE = False
    print("[WARNING] chunked_upload.py no disponible, usando upload legacy")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB max

# Habilitar CORS para Electron
@app.after_request
def after_request(response):
    # Solo agregar headers si no existen ya (evita duplicados)
    if 'Access-Control-Allow-Origin' not in response.headers:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,PATCH,OPTIONS'
    return response

# Manejar peticiones OPTIONS (preflight) para CORS
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,PATCH,OPTIONS'
        return response

# Carpetas
# En producción (empaquetado), usar VIDEO_ANALYZER_DATA_PATH para datos persistentes
# En desarrollo, usar el directorio del script
_script_dir = Path(__file__).parent
_data_path_env = os.environ.get('VIDEO_ANALYZER_DATA_PATH')

if _data_path_env:
    # Producción: usar la carpeta de datos del usuario
    BASE_DIR = Path(_data_path_env)
    # Los módulos de Python están junto al ejecutable
    PYTHON_DIR = _script_dir
else:
    # Desarrollo: todo en el mismo lugar
    BASE_DIR = _script_dir
    PYTHON_DIR = _script_dir

UPLOAD_FOLDER = BASE_DIR / 'videos_raw'
VIDEOS_RAW_FOLDER = UPLOAD_FOLDER  # TASK-030: Fix - variable faltante
OUTPUT_FOLDER = BASE_DIR / 'videos_analyzed'
THUMBNAILS_FOLDER = BASE_DIR / 'thumbnails'
PROJECTS_FOLDER = BASE_DIR / 'projects'
CONFIG_FILE = BASE_DIR / 'config.json'
PROJECTS_FILE = BASE_DIR / 'projects.json'

# Crear carpetas necesarias
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
THUMBNAILS_FOLDER.mkdir(parents=True, exist_ok=True)
PROJECTS_FOLDER.mkdir(parents=True, exist_ok=True)

print(f"[VideoAnalyzer] BASE_DIR: {BASE_DIR}")
print(f"[VideoAnalyzer] PYTHON_DIR: {PYTHON_DIR}")

# HOTFIX V5.1: Inicializar ChunkedUploadManager si está disponible
upload_manager = None
if CHUNKED_UPLOAD_AVAILABLE:
    try:
        upload_manager = ChunkedUploadManager(UPLOAD_FOLDER)
        print(f"[VideoAnalyzer] Chunked upload habilitado (max concurrent: {upload_manager.MAX_CONCURRENT})")
    except Exception as e:
        print(f"[WARNING] Error inicializando ChunkedUploadManager: {e}")
        upload_manager = None

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mxf', 'mkv', 'm4v'}

# Estado global del análisis
analysis_state = {
    'running': False,
    'progress': 0,
    'current_video': '',
    'current_progress': 0,  # Progreso del video actual (0-100)
    'total_videos': 0,
    'completed': 0,
    'results': None,
    'xml_file': None,
    'log': [],
    'pending_videos': [],    # Videos pendientes de analizar
    'completed_videos': [],  # Videos ya analizados
    'video_results': {},     # Resultados por video {filename: {gold: X, silver: Y, ...}}
    'start_time': None,      # Tiempo de inicio del análisis
    'estimated_total': 0,    # Tiempo total estimado
    'elapsed': 0             # Tiempo transcurrido
}

# Estado de metadata de videos (procesamiento en background)
# {filename: {'status': 'processing'|'ready', 'duration': float, 'thumbnail_id': str, 'estimated_time': int}}
video_metadata_cache = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith('//')}
    return get_default_config()


def get_default_config():
    return {
        "analisis": {
            "movimiento": {"activado": True, "peso": 0.30},
            "estabilidad": {"activado": True, "peso": 0.25},
            "composicion": {"activado": True, "peso": 0.20},
            "iluminacion": {"activado": True, "peso": 0.15},
            "color": {"activado": True, "peso": 0.10}
        },
        "clasificacion": {
            "gold_percentile": 80,
            "silver_percentile": 55,
            "bronze_percentile": 30,
            "min_gold_score": 7.0,
            "min_silver_score": 5.5,
            "min_bronze_score": 4.0
        },
        "rendimiento": {
            "fps_analisis": 3,
            "resolucion_ancho": 320,
            "resolucion_alto": 180,
            "ventana_segundos": 0.5
        }
    }


# Presets por tipo de proyecto
PROJECT_PRESETS = {
    "boda": {
        "nombre": "Boda / Evento",
        "descripcion": "Prioriza estabilidad y buena iluminación. Tolera algo de movimiento en bailes.",
        "config": {
            "analisis": {
                "movimiento": {"activado": True, "peso": 0.20},
                "estabilidad": {"activado": True, "peso": 0.35},
                "composicion": {"activado": True, "peso": 0.15},
                "iluminacion": {"activado": True, "peso": 0.20},
                "color": {"activado": True, "peso": 0.10}
            },
            "clasificacion": {
                "min_gold_score": 7.5,
                "min_silver_score": 5.5,
                "min_bronze_score": 4.0
            }
        }
    },
    "documental": {
        "nombre": "Documental",
        "descripcion": "Flexible con el movimiento. Valora composición y momentos auténticos.",
        "config": {
            "analisis": {
                "movimiento": {"activado": True, "peso": 0.15},
                "estabilidad": {"activado": True, "peso": 0.20},
                "composicion": {"activado": True, "peso": 0.30},
                "iluminacion": {"activado": True, "peso": 0.20},
                "color": {"activado": True, "peso": 0.15}
            },
            "clasificacion": {
                "min_gold_score": 6.5,
                "min_silver_score": 5.0,
                "min_bronze_score": 3.5
            }
        }
    },
    "corporativo": {
        "nombre": "Corporativo",
        "descripcion": "Muy estricto con estabilidad y exposición. Todo debe verse profesional.",
        "config": {
            "analisis": {
                "movimiento": {"activado": True, "peso": 0.25},
                "estabilidad": {"activado": True, "peso": 0.40},
                "composicion": {"activado": True, "peso": 0.15},
                "iluminacion": {"activado": True, "peso": 0.15},
                "color": {"activado": True, "peso": 0.05}
            },
            "clasificacion": {
                "min_gold_score": 8.0,
                "min_silver_score": 6.5,
                "min_bronze_score": 5.0
            }
        }
    },
    "deportes": {
        "nombre": "Deportes / Acción",
        "descripcion": "Tolera movimiento rápido y algo de shake. Prioriza que se vea la acción.",
        "config": {
            "analisis": {
                "movimiento": {"activado": True, "peso": 0.10},
                "estabilidad": {"activado": True, "peso": 0.15},
                "composicion": {"activado": True, "peso": 0.25},
                "iluminacion": {"activado": True, "peso": 0.30},
                "color": {"activado": True, "peso": 0.20}
            },
            "clasificacion": {
                "min_gold_score": 6.0,
                "min_silver_score": 4.5,
                "min_bronze_score": 3.0
            }
        }
    },
    "cinematico": {
        "nombre": "Cinematográfico",
        "descripcion": "El más exigente. Solo acepta tomas técnicamente perfectas.",
        "config": {
            "analisis": {
                "movimiento": {"activado": True, "peso": 0.30},
                "estabilidad": {"activado": True, "peso": 0.30},
                "composicion": {"activado": True, "peso": 0.20},
                "iluminacion": {"activado": True, "peso": 0.15},
                "color": {"activado": True, "peso": 0.05}
            },
            "clasificacion": {
                "min_gold_score": 8.5,
                "min_silver_score": 7.0,
                "min_bronze_score": 5.5
            }
        }
    }
}


def generate_thumbnail(video_path, timestamp, output_path):
    """Genera un thumbnail de un frame específico del video"""
    try:
        cmd = [
            'ffmpeg', '-y', '-ss', str(timestamp),
            '-i', str(video_path),
            '-vframes', '1',
            '-vf', 'scale=320:-1',
            '-q:v', '3',
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
        return output_path.exists()
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return False


def get_segment_thumbnail_id(filename, start_time):
    """Genera un ID único para el thumbnail de un segmento"""
    key = f"{filename}_{start_time:.2f}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ============================================================================
# SISTEMA DE PROYECTOS
# ============================================================================

def load_projects():
    """Carga la lista de proyectos"""
    if PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_projects(projects):
    """Guarda la lista de proyectos"""
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)


def get_project(project_id):
    """Obtiene un proyecto por ID"""
    projects = load_projects()
    return projects.get(project_id)


def create_project(name, preset=None, notes=""):
    """Crea un nuevo proyecto"""
    projects = load_projects()
    project_id = str(uuid.uuid4())[:8]

    project = {
        'id': project_id,
        'name': name,
        'preset': preset,
        'notes': notes,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'analyses': [],  # Lista de IDs de análisis
        'stats': {
            'total_videos': 0,
            'total_duration': 0,
            'gold_duration': 0,
            'silver_duration': 0
        }
    }

    # Crear carpeta del proyecto
    project_folder = PROJECTS_FOLDER / project_id
    project_folder.mkdir(exist_ok=True)

    projects[project_id] = project
    save_projects(projects)

    return project


def update_project(project_id, updates):
    """Actualiza un proyecto existente"""
    projects = load_projects()
    if project_id not in projects:
        return None

    projects[project_id].update(updates)
    projects[project_id]['updated_at'] = datetime.now().isoformat()
    save_projects(projects)

    return projects[project_id]


def delete_project(project_id):
    """Elimina un proyecto"""
    projects = load_projects()
    if project_id not in projects:
        return False

    del projects[project_id]
    save_projects(projects)

    # Eliminar carpeta del proyecto
    project_folder = PROJECTS_FOLDER / project_id
    if project_folder.exists():
        import shutil
        shutil.rmtree(project_folder)

    return True


def add_analysis_to_project(project_id, analysis_id, stats):
    """Agrega un análisis a un proyecto y actualiza sus stats"""
    projects = load_projects()
    if project_id not in projects:
        return False

    project = projects[project_id]
    if analysis_id not in project['analyses']:
        project['analyses'].append(analysis_id)

    # Actualizar stats del proyecto
    project['stats']['total_videos'] += stats.get('total_videos', 0)
    project['stats']['total_duration'] += stats.get('total_duration', 0)
    project['stats']['gold_duration'] += stats.get('gold_duration', 0)
    project['stats']['silver_duration'] += stats.get('silver_duration', 0)
    project['updated_at'] = datetime.now().isoformat()

    save_projects(projects)
    return True


def get_video_resolution(filepath):
    """Obtiene resolución real del video usando ffprobe"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
               '-show_streams', str(filepath)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                return {
                    'width': stream.get('width', 1920),
                    'height': stream.get('height', 1080)
                }
    except:
        pass
    return {'width': 1920, 'height': 1080}


def get_video_duration(filepath):
    """Obtiene la duración del video usando ffprobe"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
               '-show_format', str(filepath)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        duration = float(data.get('format', {}).get('duration', 0))
        return duration
    except:
        pass
    return 0


def get_video_fps(filepath):
    """Obtiene el FPS del video usando ffprobe
    HOTFIX V5.1: Necesario para exportación XML correcta"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
               '-show_streams', str(filepath)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        
        # Buscar en streams de video
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                # Intentar obtener avg_frame_rate primero
                fps_str = stream.get('avg_frame_rate', stream.get('r_frame_rate', '30/1'))
                
                # Calcular FPS desde fracción (ej: "30000/1001" -> 29.97)
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    fps = float(num) / float(den)
                else:
                    fps = float(fps_str)
                
                # Redondear valores comunes
                fps_rounded = round(fps, 2)
                
                # Normalizar valores estándar
                fps_map = {
                    23.98: 23.976,
                    29.97: 29.97,
                    59.94: 59.94,
                }
                
                for std_fps in [24, 25, 30, 48, 50, 60]:
                    if abs(fps_rounded - std_fps) < 0.1:
                        return std_fps
                
                return fps_rounded
    except Exception as e:
        print(f"[WARNING] Error obteniendo FPS: {e}")
    
    return 30  # Default fallback


def generate_upload_thumbnail(video_path, output_path):
    """Genera thumbnail de preview para un video subido (frame del segundo 1)"""
    try:
        cmd = [
            'ffmpeg', '-y', '-ss', '1',
            '-i', str(video_path),
            '-vframes', '1',
            '-vf', 'scale=120:-1',
            '-q:v', '5',
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        return output_path.exists()
    except:
        return False


def get_upload_thumbnail_id(filename):
    """Genera ID único para thumbnail de upload"""
    return 'upload_' + hashlib.md5(filename.encode()).hexdigest()[:10]


def process_video_metadata_background(filepath, filename):
    """Procesa metadata de video en background (duración, FPS y thumbnail)
    HOTFIX V5.1: Ahora incluye FPS para exportación XML correcta
    """
    global video_metadata_cache

    try:
        # Obtener duración
        duration = get_video_duration(filepath)
        
        # HOTFIX V5.1: Obtener FPS para exportación correcta
        fps = get_video_fps(filepath)

        # Generar thumbnail
        thumb_id = get_upload_thumbnail_id(filename)
        thumb_path = THUMBNAILS_FOLDER / f"{thumb_id}.jpg"
        generate_upload_thumbnail(filepath, thumb_path)

        # Estimar tiempo de análisis
        estimated_time = estimate_analysis_time(duration)

        # Actualizar cache
        video_metadata_cache[filename] = {
            'status': 'ready',
            'duration': duration,
            'fps': fps,  # HOTFIX V5.1
            'thumbnail_id': thumb_id if thumb_path.exists() else None,
            'estimated_time': estimated_time
        }
        
        print(f"[Metadata] {filename}: {duration:.1f}s @ {fps}fps")
    except Exception as e:
        print(f"Error processing metadata for {filename}: {e}")
        video_metadata_cache[filename] = {
            'status': 'error',
            'duration': 0,
            'fps': 30,  # HOTFIX V5.1
            'thumbnail_id': None,
            'estimated_time': 5,
            'error': str(e)
        }


def estimate_analysis_time(duration):
    """Estima tiempo de análisis basado en duración del video.

    El análisis procesa el video a fps_analisis (default 3fps) y realiza:
    - Cálculo de optical flow para motion
    - Histogramas de color e iluminación
    - Análisis de estabilidad
    - Detección de tipo de toma

    En pruebas reales, el tiempo de análisis es aproximadamente igual
    a la duración del video (ratio 1:1) con variaciones según el hardware.
    """
    if duration <= 0:
        return 5

    # Base: el análisis tarda aproximadamente lo mismo que dura el video
    # debido al procesamiento intensivo frame a frame
    base_time = duration * 0.85  # ~85% de la duración como base

    # Agregar overhead fijo por inicialización (abrir video, cargar config, etc)
    overhead = 2

    # Videos muy cortos (<10s) tienen mayor overhead relativo
    if duration < 10:
        estimated = max(5, int(duration * 1.2) + overhead)
    # Videos medianos (10-60s)
    elif duration < 60:
        estimated = int(base_time + overhead)
    # Videos largos (>60s) son más eficientes proporcionalmente
    else:
        estimated = int(duration * 0.75 + overhead)

    return max(3, estimated)


# ============================================================================
# RUTAS
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())


@app.route('/api/config', methods=['POST'])
def update_config():
    config = request.json
    save_config(config)
    return jsonify({'status': 'ok'})


@app.route('/api/presets', methods=['GET'])
def get_presets():
    """Retorna los presets de proyecto disponibles"""
    return jsonify(PROJECT_PRESETS)


@app.route('/api/presets/<preset_id>', methods=['GET'])
def get_preset(preset_id):
    """Retorna un preset específico"""
    if preset_id in PROJECT_PRESETS:
        return jsonify(PROJECT_PRESETS[preset_id])
    return jsonify({'error': 'Preset not found'}), 404


# ============================================================================
# API DE PROYECTOS
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """Lista todos los proyectos"""
    projects = load_projects()

    # Agregar info adicional a cada proyecto
    result = []
    for pid, project in projects.items():
        # Calcular tiempo relativo
        created = datetime.fromisoformat(project['created_at'])
        diff = datetime.now() - created

        if diff.days == 0:
            if diff.seconds < 3600:
                time_ago = f"Hace {max(1, diff.seconds // 60)} min"
            else:
                time_ago = f"Hace {diff.seconds // 3600}h"
        elif diff.days == 1:
            time_ago = "Ayer"
        elif diff.days < 7:
            time_ago = f"Hace {diff.days} días"
        else:
            time_ago = created.strftime("%d %b")

        # Obtener thumbnail del primer análisis
        thumbnail_id = None
        if project['analyses']:
            first_analysis = project['analyses'][0]
            json_file = OUTPUT_FOLDER / f"{first_analysis}.json"
            if json_file.exists():
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    for video in data.get('analyses', []):
                        if video.get('success') and video.get('segments'):
                            thumbnail_id = get_segment_thumbnail_id(
                                video['filename'], video['segments'][0]['start_time']
                            )
                            break
                except:
                    pass

        result.append({
            **project,
            'time_ago': time_ago,
            'thumbnail_id': thumbnail_id,
            'analysis_count': len(project['analyses'])
        })

    # Ordenar por más reciente
    result.sort(key=lambda x: x['updated_at'], reverse=True)
    return jsonify({'projects': result})


@app.route('/api/projects', methods=['POST'])
def api_create_project():
    """Crea un nuevo proyecto"""
    data = request.json
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'El nombre es requerido'}), 400

    # Limpiar videos pendientes de proyectos anteriores
    # (los videos en uploads no están asociados a ningún proyecto específico)
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and f.suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS:
            try:
                f.unlink()
            except Exception as e:
                print(f"Error eliminando {f}: {e}")

    project = create_project(
        name=name,
        preset=data.get('preset'),
        notes=data.get('notes', '')
    )

    return jsonify(project)


@app.route('/api/projects/<project_id>', methods=['GET'])
def api_get_project(project_id):
    """Obtiene un proyecto con sus análisis"""
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    # Cargar análisis del proyecto
    analyses = []
    for analysis_id in project['analyses']:
        json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
        if json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                # Obtener thumbnail y lista de videos
                thumbnail_id = None
                videos_summary = []
                for video in data.get('analyses', []):
                    if video.get('success'):
                        # Thumbnail del primer segmento
                        if not thumbnail_id and video.get('segments'):
                            thumbnail_id = get_segment_thumbnail_id(
                                video['filename'], video['segments'][0]['start_time']
                            )
                        # Resumen del video
                        tier_dur = video.get('tier_durations', {})
                        tier_pct = video.get('tier_percentages', {})
                        usable = (tier_pct.get('gold', 0) + tier_pct.get('silver', 0))
                        videos_summary.append({
                            'filename': video['filename'],
                            'duration': video.get('duration', 0),
                            'segments': len(video.get('segments', [])),
                            'gold': tier_dur.get('gold', 0),
                            'silver': tier_dur.get('silver', 0),
                            'usable_pct': usable
                        })

                analyses.append({
                    'id': analysis_id,
                    'timestamp': data.get('timestamp', ''),
                    'stats': data.get('stats', {}),
                    'thumbnail_id': thumbnail_id,
                    'video_count': len(data.get('analyses', [])),
                    'videos': videos_summary
                })
            except:
                continue

    return jsonify({
        **project,
        'analyses_data': analyses
    })


@app.route('/api/projects/<project_id>', methods=['PUT', 'PATCH'])
def api_update_project(project_id):
    """Actualiza un proyecto"""
    data = request.json
    project = update_project(project_id, data)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404
    return jsonify(project)


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    """Elimina un proyecto"""
    if delete_project(project_id):
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Proyecto no encontrado'}), 404


@app.route('/api/projects/<project_id>/videos', methods=['GET'])
def get_project_analyzed_videos(project_id):
    """Obtiene todos los videos analizados de un proyecto CON sus segmentos"""
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    all_videos = []
    for analysis_id in project.get('analyses', []):
        json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
        if json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                for video in data.get('analyses', []):
                    if video.get('success'):
                        # Obtener thumbnail del video - intentar segmento primero, luego upload
                        thumbnail_id = None
                        if video.get('segments'):
                            seg_thumb_id = get_segment_thumbnail_id(
                                video['filename'], video['segments'][0]['start_time']
                            )
                            # Verificar si existe el thumbnail de segmento
                            if (THUMBNAILS_FOLDER / f"{seg_thumb_id}.jpg").exists():
                                thumbnail_id = seg_thumb_id

                        # Fallback a thumbnail de upload si no hay de segmento
                        if not thumbnail_id:
                            upload_thumb_id = get_upload_thumbnail_id(video['filename'])
                            if (THUMBNAILS_FOLDER / f"{upload_thumb_id}.jpg").exists():
                                thumbnail_id = upload_thumb_id

                        all_videos.append({
                            'id': f"{analysis_id}_{video['filename']}",
                            'filename': video['filename'],
                            'path': video.get('path', ''),
                            'duration': video.get('duration', 0),
                            'segments': video.get('segments', []),
                            'tier_durations': video.get('tier_durations', {}),
                            'tier_percentages': video.get('tier_percentages', {}),
                            'thumbnail_id': thumbnail_id,
                            'analysis_id': analysis_id
                        })
            except Exception as e:
                print(f"Error loading analysis {analysis_id}: {e}")
                continue

    return jsonify({'videos': all_videos})


@app.route('/api/projects/<project_id>/pending', methods=['GET'])
def get_project_pending_videos(project_id):
    """Obtiene videos pendientes de análisis para un proyecto"""
    global video_metadata_cache

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    # Por ahora retornamos los videos en UPLOAD_FOLDER que no han sido analizados
    # En el futuro se puede filtrar por proyecto específico
    videos = []
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and f.suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS:
            filename = f.name

            # Verificar si ya fue analizado en este proyecto
            is_analyzed = False
            for analysis_id in project.get('analyses', []):
                json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
                if json_file.exists():
                    try:
                        with open(json_file, 'r') as jf:
                            data = json.load(jf)
                            for v in data.get('analyses', []):
                                if v.get('filename') == filename:
                                    is_analyzed = True
                                    break
                    except:
                        pass
                if is_analyzed:
                    break

            if not is_analyzed:
                # Usar cache si está disponible
                if filename in video_metadata_cache:
                    cached = video_metadata_cache[filename]
                    duration = cached.get('duration', 0)
                    metadata_status = cached.get('status', 'processing')
                else:
                    duration = 0
                    metadata_status = 'processing'

                # Estado del análisis
                status = 'pending'
                progress = 0
                if analysis_state['running']:
                    if analysis_state.get('current_video') == filename:
                        status = 'analyzing'
                        progress = analysis_state.get('current_progress', 0)
                    elif filename in analysis_state.get('completed_videos', []):
                        status = 'completed'
                    elif filename in analysis_state.get('pending_videos', []):
                        status = 'queued'

                videos.append({
                    'name': filename,
                    'size_mb': round(f.stat().st_size / (1024 * 1024), 1),
                    'duration': duration,
                    'status': status,
                    'progress': progress,
                    'metadata_status': metadata_status
                })

    return jsonify({'videos': sorted(videos, key=lambda x: x['name'])})


@app.route('/api/projects/<project_id>/best-takes', methods=['GET'])
def get_project_best_takes(project_id):
    """Retorna los mejores segmentos de un proyecto específico"""
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    limit = request.args.get('limit', 50, type=int)
    tier_filter = request.args.get('tier', None)
    shot_type_filter = request.args.get('shot_type', None)

    all_segments = []

    for analysis_id in project['analyses']:
        json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
        if not json_file.exists():
            continue

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            for video in data.get('analyses', []):
                if not video.get('success'):
                    continue
                for seg in video.get('segments', []):
                    seg_data = {
                        'filename': video['filename'],
                        'path': video.get('path', ''),
                        'start_time': seg['start_time'],
                        'end_time': seg['end_time'],
                        'duration': seg['duration'],
                        'score': seg.get('score', 0),
                        'tier': seg.get('tier', 'discard'),
                        'shot_type': seg.get('shot_type', 'DESCONOCIDO'),
                        'thumbnail_id': get_segment_thumbnail_id(video['filename'], seg['start_time']),
                        'timecode': format_timecode(seg['start_time']),
                        'analysis_id': analysis_id
                    }
                    all_segments.append(seg_data)
        except:
            continue

    # Aplicar filtros
    if tier_filter:
        all_segments = [s for s in all_segments if s['tier'] == tier_filter]
    if shot_type_filter:
        all_segments = [s for s in all_segments if s['shot_type'] == shot_type_filter]

    # Ordenar por score
    all_segments.sort(key=lambda x: x['score'], reverse=True)

    return jsonify({
        'project_id': project_id,
        'project_name': project['name'],
        'total': len(all_segments),
        'showing': min(limit, len(all_segments)),
        'segments': all_segments[:limit]
    })


@app.route('/thumbnails/<filename>')
def serve_thumbnail(filename):
    """Sirve los thumbnails generados, generándolos on-demand si no existen"""
    thumb_path = THUMBNAILS_FOLDER / filename

    # Si ya existe, servirlo
    if thumb_path.exists():
        return send_from_directory(str(THUMBNAILS_FOLDER), filename)

    # Intentar generar on-demand
    # El filename es algo como "6c3737f31812.jpg" - necesitamos encontrar el video y timestamp
    thumb_id = filename.replace('.jpg', '')

    # Cargar config para obtener media_folder
    config = load_config()
    media_folder = config.get('media_folder', '')

    # Buscar en todos los análisis el segmento que corresponde a este thumbnail_id
    for json_file in OUTPUT_FOLDER.glob('analisis_completo_*.json'):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            for video in data.get('analyses', []):
                if not video.get('success'):
                    continue

                video_filename = video.get('filename', '')
                video_path = video.get('path', '')

                for seg in video.get('segments', []):
                    seg_thumb_id = get_segment_thumbnail_id(video_filename, seg['start_time'])
                    if seg_thumb_id == thumb_id:
                        # Encontramos el segmento, buscar el video en varios lugares
                        actual_path = None

                        # 1. Path original
                        if video_path and Path(video_path).exists():
                            actual_path = video_path
                        # 2. En media_folder
                        elif media_folder:
                            possible = Path(media_folder) / video_filename
                            if possible.exists():
                                actual_path = str(possible)
                        # 3. En videos_raw
                        if not actual_path:
                            possible = VIDEOS_RAW_FOLDER / video_filename
                            if possible.exists():
                                actual_path = str(possible)
                        # 4. Buscar en /Users/danielazpe/Movies (común en Mac)
                        if not actual_path:
                            possible = Path('/Users/danielazpe/Movies') / video_filename
                            if possible.exists():
                                actual_path = str(possible)

                        if actual_path:
                            print(f"[THUMB] Generating from: {actual_path}")
                            generate_thumbnail(actual_path, seg['start_time'], thumb_path)
                            if thumb_path.exists():
                                return send_from_directory(str(THUMBNAILS_FOLDER), filename)
                        else:
                            print(f"[THUMB] Video not found: {video_filename}")
        except Exception as e:
            print(f"Error searching for thumbnail: {e}")
            continue

    # No encontrado
    return "Thumbnail not found", 404


@app.route('/api/best-takes', methods=['GET'])
def get_best_takes():
    """Retorna los mejores segmentos ordenados por score"""
    limit = request.args.get('limit', 20, type=int)
    tier_filter = request.args.get('tier', None)  # gold, silver, etc.
    shot_type_filter = request.args.get('shot_type', None)

    results_files = list(OUTPUT_FOLDER.glob('analisis_completo_*.json'))
    if not results_files:
        return jsonify({'error': 'No results found', 'segments': []}), 404

    latest = max(results_files, key=lambda x: x.stat().st_mtime)
    with open(latest, 'r') as f:
        data = json.load(f)

    # Recolectar todos los segmentos
    all_segments = []
    for video in data.get('analyses', []):
        if not video.get('success'):
            continue
        for seg in video.get('segments', []):
            seg_data = {
                'filename': video['filename'],
                'path': video.get('path', ''),
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'duration': seg['duration'],
                'score': seg.get('score', 0),
                'tier': seg.get('tier', 'discard'),
                'shot_type': seg.get('shot_type', 'DESCONOCIDO'),
                'thumbnail_id': get_segment_thumbnail_id(video['filename'], seg['start_time']),
                'timecode': format_timecode(seg['start_time']),
                'explanation': seg.get('explanation', {})
            }
            all_segments.append(seg_data)

    # Filtrar por tier si se especificó
    if tier_filter:
        all_segments = [s for s in all_segments if s['tier'] == tier_filter]

    # Filtrar por tipo de toma si se especificó
    if shot_type_filter:
        all_segments = [s for s in all_segments if s['shot_type'] == shot_type_filter]

    # Ordenar por score descendente
    all_segments.sort(key=lambda x: x['score'], reverse=True)

    # Limitar resultados
    best = all_segments[:limit]

    return jsonify({
        'total': len(all_segments),
        'showing': len(best),
        'segments': best
    })


def format_timecode(seconds):
    """Convierte segundos a formato timecode HH:MM:SS:FF"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    f = int((seconds % 1) * 30)  # Asumiendo 30fps
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


@app.route('/api/videos', methods=['GET'])
def list_videos():
    """Lista videos con metadata desde cache (sin bloquear)"""
    global video_metadata_cache

    videos = []
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and f.suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS:
            filename = f.name

            # Usar cache si está disponible
            if filename in video_metadata_cache:
                cached = video_metadata_cache[filename]
                duration = cached.get('duration', 0)
                thumb_id = cached.get('thumbnail_id')
                estimated_time = cached.get('estimated_time', 5)
                metadata_status = cached.get('status', 'processing')
            else:
                # No está en cache - verificar si ya tiene thumbnail (de sesión anterior)
                thumb_id = get_upload_thumbnail_id(filename)
                thumb_path = THUMBNAILS_FOLDER / f"{thumb_id}.jpg"

                if thumb_path.exists():
                    # Ya procesado anteriormente, obtener duración (rápido con cache de OS)
                    duration = get_video_duration(f)
                    estimated_time = estimate_analysis_time(duration)
                    metadata_status = 'ready'
                    # Guardar en cache
                    video_metadata_cache[filename] = {
                        'status': 'ready',
                        'duration': duration,
                        'thumbnail_id': thumb_id,
                        'estimated_time': estimated_time
                    }
                else:
                    # Necesita procesamiento - iniciar en background
                    duration = 0
                    thumb_id = None
                    estimated_time = 5
                    metadata_status = 'processing'
                    video_metadata_cache[filename] = {'status': 'processing'}
                    thread = threading.Thread(
                        target=process_video_metadata_background,
                        args=(f, filename)
                    )
                    thread.start()

            # Obtener estado del análisis si está en progreso
            status = 'ready'
            progress = 0
            if analysis_state['running']:
                if analysis_state.get('current_video') == filename:
                    status = 'analyzing'
                    progress = analysis_state.get('current_progress', 0)
                elif filename in analysis_state.get('completed_videos', []):
                    status = 'completed'
                elif filename in analysis_state.get('pending_videos', []):
                    status = 'pending'

            videos.append({
                'name': filename,
                'size': f.stat().st_size,
                'size_mb': round(f.stat().st_size / (1024 * 1024), 1),
                'duration': duration,
                'thumbnail_id': thumb_id,
                'estimated_time': estimated_time,
                'status': status,
                'progress': progress,
                'metadata_status': metadata_status
            })
    return jsonify(sorted(videos, key=lambda x: x['name']))


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload instantáneo - metadata se procesa en background
    HOTFIX V5.1: Usa chunked upload para archivos grandes
    """
    global video_metadata_cache, upload_manager

    # Soportar múltiples formatos: 'file', 'files', 'videos'
    files = []
    if 'file' in request.files:
        files = [request.files['file']]
    elif 'files' in request.files:
        files = request.files.getlist('files')
    elif 'videos' in request.files:
        files = request.files.getlist('videos')

    if not files:
        return jsonify({'error': 'No file provided. Use key: file, files, or videos'}), 400

    uploaded = []
    errors = []
    
    for file in files:
        if file.filename == '':
            continue

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # HOTFIX V5.1: Usar chunked upload si está disponible
            if upload_manager and CHUNKED_UPLOAD_AVAILABLE:
                try:
                    # Obtener tamaño del archivo si está disponible
                    file.seek(0, 2)  # Ir al final
                    file_size = file.tell()
                    file.seek(0)  # Regresar al inicio
                    
                    # Usar chunked upload
                    filepath = upload_manager.handle_upload_sync(
                        file.stream, 
                        filename,
                        progress_callback=None  # Podemos agregar progress vía WebSocket en el futuro
                    )
                    
                    print(f"[Upload] Chunked upload exitoso: {filename} ({file_size / 1024 / 1024:.1f}MB)")
                    
                except Exception as e:
                    print(f"[ERROR] Chunked upload falló para {filename}: {e}")
                    errors.append(f"{filename}: {str(e)}")
                    continue
            else:
                # Fallback a método legacy
                filepath = UPLOAD_FOLDER / filename
                try:
                    file.save(str(filepath))
                except Exception as e:
                    print(f"[ERROR] Upload legacy falló para {filename}: {e}")
                    errors.append(f"{filename}: {str(e)}")
                    continue

            # Marcar como procesando en cache
            video_metadata_cache[filename] = {
                'status': 'processing',
                'duration': 0,
                'thumbnail_id': None,
                'estimated_time': 5
            }

            # Procesar metadata en background
            thread = threading.Thread(
                target=process_video_metadata_background,
                args=(filepath, filename)
            )
            thread.start()

            uploaded.append(filename)

    if not uploaded:
        return jsonify({
            'error': 'No valid video files uploaded',
            'details': errors
        }), 400

    # Responder con lista de archivos subidos
    response = {
        'status': 'ok',
        'uploaded': uploaded,
        'count': len(uploaded)
    }
    
    if errors:
        response['warnings'] = errors
    
    return jsonify(response)


@app.route('/api/video-metadata/<filename>', methods=['GET'])
def get_video_metadata(filename):
    """Retorna el estado de procesamiento de metadata de un video"""
    filename = secure_filename(filename)

    # Primero revisar cache
    if filename in video_metadata_cache:
        return jsonify(video_metadata_cache[filename])

    # Si no está en cache, verificar si existe y generar metadata
    filepath = UPLOAD_FOLDER / filename
    if not filepath.exists():
        return jsonify({'error': 'Video not found'}), 404

    # Video existe pero no está en cache - procesar síncronamente (fallback)
    thumb_id = get_upload_thumbnail_id(filename)
    thumb_path = THUMBNAILS_FOLDER / f"{thumb_id}.jpg"

    # Si ya tiene thumbnail, solo obtener duración
    if thumb_path.exists():
        duration = get_video_duration(filepath)
        return jsonify({
            'status': 'ready',
            'duration': duration,
            'thumbnail_id': thumb_id,
            'estimated_time': estimate_analysis_time(duration)
        })

    # Si no, iniciar procesamiento en background
    video_metadata_cache[filename] = {'status': 'processing'}
    thread = threading.Thread(
        target=process_video_metadata_background,
        args=(filepath, filename)
    )
    thread.start()

    return jsonify({'status': 'processing'})


@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    filepath = UPLOAD_FOLDER / secure_filename(filename)
    if filepath.exists():
        filepath.unlink()
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/videos/clear', methods=['POST'])
def clear_pending_videos():
    """Elimina todos los videos de la carpeta de uploads (pendientes)"""
    if analysis_state['running']:
        return jsonify({'error': 'No se puede limpiar mientras hay un análisis en curso'}), 400

    deleted = 0
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and f.suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS:
            f.unlink()
            deleted += 1

    return jsonify({'status': 'ok', 'deleted': deleted})


@app.route('/api/analyze', methods=['POST'])
def start_analysis():
    global analysis_state

    if analysis_state['running']:
        return jsonify({'error': 'Analysis already running'}), 400

    data = request.json or {}
    config = data.get('config', load_config())
    project_id = data.get('project_id')

    # Obtener configuración de categorías del frontend
    analysis_categories = data.get('analysis_categories', {
        'stability': True,
        'focus': True,
        'exposure': True,
        'composition': True,
    })
    analysis_profile = data.get('analysis_profile', 'documental')

    # Obtener configuración de análisis inteligente del frontend
    intelligent_analysis = data.get('intelligent_analysis', {
        'garbage_detection': True,
        'shot_classification': True,
        'face_analysis': True,
        'scene_grouping': True,
        'take_detection': True,
        'key_moments': True,
    })

    # Si no hay project_id, crear uno temporal
    if not project_id:
        project_id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # Crear proyecto temporal
        create_project(project_id, preset=None, notes="Análisis rápido")

    # Verificar que el proyecto existe
    project = get_project(project_id)
    if not project:
        # Crear si no existe
        create_project(project_id, preset=None, notes="Análisis rápido")

    thread = threading.Thread(target=run_analysis, args=(config, project_id, analysis_categories, intelligent_analysis))
    thread.start()

    # Esperar hasta que el hilo de análisis haya iniciado (max 3 segundos)
    for _ in range(30):
        if analysis_state['running']:
            break
        time.sleep(0.1)

    return jsonify({'status': 'started', 'project_id': project_id, 'running': analysis_state['running']})


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(analysis_state)


@app.route('/api/results', methods=['GET'])
def get_results():
    results_files = list(OUTPUT_FOLDER.glob('analisis_completo_*.json'))
    if not results_files:
        return jsonify({'error': 'No results found'}), 404

    latest = max(results_files, key=lambda x: x.stat().st_mtime)
    with open(latest, 'r') as f:
        return jsonify(json.load(f))


@app.route('/api/analysis/<analysis_id>', methods=['GET'])
def get_analysis_detail(analysis_id):
    """Retorna el análisis detallado completo con todos los segmentos y métricas"""
    json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
    if not json_file.exists():
        return jsonify({'error': 'Análisis no encontrado'}), 404

    with open(json_file, 'r') as f:
        data = json.load(f)

    # Procesar cada video para agregar thumbnail del video principal
    for video in data.get('analyses', []):
        if video.get('success'):
            # Agregar thumbnail del video (generado durante upload)
            video['thumbnail_id'] = get_upload_thumbnail_id(video['filename'])

    return jsonify(data)


@app.route('/api/analysis/<analysis_id>/video/<path:filename>', methods=['GET'])
def get_video_analysis_detail(analysis_id, filename):
    """Retorna el análisis detallado de un video específico"""
    json_file = OUTPUT_FOLDER / f"{analysis_id}.json"
    if not json_file.exists():
        return jsonify({'error': 'Análisis no encontrado'}), 404

    with open(json_file, 'r') as f:
        data = json.load(f)

    # Buscar el video específico
    for video in data.get('analyses', []):
        if video.get('filename') == filename:
            if video.get('success'):
                # Agregar thumbnails a segmentos
                for seg in video.get('segments', []):
                    seg['thumbnail_id'] = get_segment_thumbnail_id(
                        video['filename'], seg['start_time']
                    )
            return jsonify(video)

    return jsonify({'error': 'Video no encontrado en este análisis'}), 404


@app.route('/api/reports', methods=['GET'])
def list_reports():
    reports = []
    for f in OUTPUT_FOLDER.glob('analisis_completo_*.html'):
        reports.append({
            'name': f.name,
            'date': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        })
    return jsonify(sorted(reports, key=lambda x: x['date'], reverse=True))


@app.route('/api/history', methods=['GET'])
def get_history():
    """Retorna el historial de análisis con thumbnails y stats"""
    history = []

    for json_file in sorted(OUTPUT_FOLDER.glob('analisis_completo_*.json'),
                            key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            stats = data.get('stats', {})
            analyses = data.get('analyses', [])

            # Obtener primer thumbnail disponible
            first_thumb = None
            for video in analyses:
                if video.get('success') and video.get('segments'):
                    first_seg = video['segments'][0]
                    first_thumb = get_segment_thumbnail_id(video['filename'], first_seg['start_time'])
                    break

            # Calcular tiempo relativo
            file_time = datetime.fromtimestamp(json_file.stat().st_mtime)
            now = datetime.now()
            diff = now - file_time

            if diff.days == 0:
                if diff.seconds < 3600:
                    time_ago = f"Hace {diff.seconds // 60} min"
                else:
                    time_ago = f"Hace {diff.seconds // 3600}h"
            elif diff.days == 1:
                time_ago = "Ayer"
            elif diff.days < 7:
                time_ago = f"Hace {diff.days} días"
            else:
                time_ago = file_time.strftime("%d %b")

            history.append({
                'id': json_file.stem,
                'timestamp': data.get('timestamp', ''),
                'video_count': stats.get('total_videos', 0),
                'total_duration': stats.get('total_duration', 0),
                'usable_pct': stats.get('usable_pct', 0),
                'gold_duration': stats.get('gold_duration', 0),
                'silver_duration': stats.get('silver_duration', 0),
                'thumbnail_id': first_thumb,
                'time_ago': time_ago,
                'html_report': f"analisis_completo_{data.get('timestamp', '')}.html",
                'xml_file': f"premiere_export_{data.get('timestamp', '')}.xml"
            })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            continue

    return jsonify(history)


@app.route('/reports/<filename>')
def serve_report(filename):
    return send_from_directory(str(OUTPUT_FOLDER), filename)


@app.route('/api/xml-files', methods=['GET'])
def list_xml_files():
    xml_files = []
    for f in OUTPUT_FOLDER.glob('premiere_export_*.xml'):
        xml_files.append({
            'name': f.name,
            'date': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        })
    return jsonify(sorted(xml_files, key=lambda x: x['date'], reverse=True))


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(str(OUTPUT_FOLDER), filename, as_attachment=True)


@app.route('/api/export', methods=['POST'])
def export_xml():
    """
    Exporta XML con opciones avanzadas:
    - tiers: lista de tiers a incluir ['gold', 'silver', 'bronze', 'discard']
    - track_mode: 'single' (un track) | 'multi' (un track por tier)
    - handles: segundos a agregar antes/después de cada clip
    - organization: 'sequence' | 'by_tier' | 'tracks' | 'original'
    - sort_by: 'time' | 'quality' | 'shot_type'
    - filename: nombre personalizado para el archivo
    - selected_clips: clips específicos seleccionados por el frontend
    - media_folder: carpeta donde están los archivos originales
    """
    data = request.json or {}

    # Obtener track_mode del frontend (default: multi)
    track_mode = data.get('track_mode', 'multi')

    # Mapear track_mode a organization para compatibilidad
    # 'single' -> 'sequence' (un track)
    # 'multi' -> 'by_tier' (un track por tier)
    if track_mode == 'single':
        organization = 'sequence'
    else:  # multi
        organization = 'by_tier'

    options = {
        'tiers': data.get('tiers', ['gold', 'silver']),
        'handles': data.get('handles', 0),
        'organization': organization,
        'track_mode': track_mode,
        'sort_by': data.get('sort_by', 'time'),
        'media_folder': data.get('media_folder', '').strip()
    }

    custom_filename = data.get('filename', '').strip()
    selected_clips = data.get('selected_clips', [])

    # DEBUG: Log options received
    print(f"[EXPORT] Options received: {options}")
    print(f"[EXPORT] Custom filename: {custom_filename}")
    print(f"[EXPORT] Selected clips count: {len(selected_clips)}")
    print(f"[EXPORT] Organization mode: {options['organization']}")

    if not selected_clips:
        return jsonify({'error': 'No hay clips seleccionados para exportar'}), 400

    # Generar nombre de archivo
    if custom_filename:
        # Sanitizar nombre: solo alfanuméricos, guiones y underscores
        safe_name = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in custom_filename)
        safe_name = safe_name.strip().replace(' ', '_')
        xml_filename = f'{safe_name}.xml'
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xml_filename = f'export_{timestamp}.xml'

    xml_path = OUTPUT_FOLDER / xml_filename

    # Usar la nueva función que trabaja directamente con clips
    generate_premiere_xml_from_clips(selected_clips, xml_path, options)

    return jsonify({
        'status': 'ok',
        'filename': xml_filename,
        'download_url': f'/download/{xml_filename}'
    })


# ============================================================
# NUEVOS ENDPOINTS - DETECCIÓN DE BASURA (Fase 1 v5.0)
# ============================================================

@app.route('/api/projects/<project_id>/garbage', methods=['GET'])
def get_project_garbage(project_id):
    """
    Obtiene resumen de basura detectada en todo el proyecto.

    Returns:
        {
            'total_garbage_duration': float,
            'garbage_by_type': {'lens_cap': 2.5, 'pre_roll': 1.2, ...},
            'garbage_by_video': {'video1.mp4': {...}, ...},
            'recommendation': str
        }
    """
    analysis_folder = ANALYZED_FOLDER

    # Buscar análisis del proyecto
    garbage_by_type = {}
    garbage_by_video = {}
    total_garbage_duration = 0

    for analysis_file in analysis_folder.glob('*.json'):
        try:
            with open(analysis_file, 'r') as f:
                data = json.load(f)

            # Verificar si pertenece a este proyecto
            if data.get('project_id') != project_id:
                continue

            filename = data.get('filename', analysis_file.stem)
            garbage_info = data.get('garbage', {})

            if garbage_info:
                video_garbage_duration = garbage_info.get('total_garbage_duration', 0)
                total_garbage_duration += video_garbage_duration

                # Por tipo
                for detection in garbage_info.get('detections', []):
                    gtype = detection.get('garbage_type', 'unknown')
                    duration = detection.get('end_time', 0) - detection.get('start_time', 0)
                    garbage_by_type[gtype] = garbage_by_type.get(gtype, 0) + duration

                # Por video
                garbage_by_video[filename] = {
                    'duration': video_garbage_duration,
                    'types': garbage_info.get('garbage_types_found', []),
                    'detections': garbage_info.get('detections', [])
                }

        except Exception as e:
            print(f"Error reading garbage from {analysis_file}: {e}")
            continue

    # Generar recomendación
    if total_garbage_duration > 10:
        recommendation = f'Se detectaron {total_garbage_duration:.1f}s de basura. Considera filtrar antes de editar.'
    elif total_garbage_duration > 0:
        recommendation = f'Basura menor detectada ({total_garbage_duration:.1f}s). Material mayormente limpio.'
    else:
        recommendation = 'No se detectó basura significativa en el proyecto.'

    return jsonify({
        'total_garbage_duration': total_garbage_duration,
        'garbage_by_type': garbage_by_type,
        'garbage_by_video': garbage_by_video,
        'recommendation': recommendation
    })


@app.route('/api/projects/<project_id>/segments/filter', methods=['POST'])
def filter_project_segments(project_id):
    """
    Filtra segmentos del proyecto según criterios.

    Body:
        {
            'exclude_garbage': true/false,
            'min_tier': 'gold'|'silver'|'bronze'|'discard',
            'garbage_types_to_exclude': ['lens_cap', 'black_frame', ...]
        }

    Returns:
        Lista de segmentos filtrados con su video de origen
    """
    data = request.json or {}

    exclude_garbage = data.get('exclude_garbage', True)
    min_tier = data.get('min_tier', 'discard')
    garbage_types_to_exclude = data.get('garbage_types_to_exclude', [])

    tier_order = {'gold': 4, 'silver': 3, 'bronze': 2, 'discard': 1}
    min_tier_value = tier_order.get(min_tier, 1)

    filtered_segments = []

    for analysis_file in ANALYZED_FOLDER.glob('*.json'):
        try:
            with open(analysis_file, 'r') as f:
                analysis_data = json.load(f)

            if analysis_data.get('project_id') != project_id:
                continue

            filename = analysis_data.get('filename', analysis_file.stem)

            for segment in analysis_data.get('segments', []):
                # Filtrar por basura
                if exclude_garbage and segment.get('is_garbage', False):
                    garbage_type = segment.get('garbage_type')
                    if not garbage_types_to_exclude or garbage_type in garbage_types_to_exclude:
                        continue

                # Filtrar por tier
                segment_tier = segment.get('tier', 'discard')
                if tier_order.get(segment_tier, 1) < min_tier_value:
                    continue

                # Agregar información del video
                segment_copy = segment.copy()
                segment_copy['video_filename'] = filename
                segment_copy['video_path'] = analysis_data.get('path', '')
                filtered_segments.append(segment_copy)

        except Exception as e:
            print(f"Error filtering segments from {analysis_file}: {e}")
            continue

    # Ordenar por tier (mejor primero) y luego por tiempo
    filtered_segments.sort(key=lambda s: (-tier_order.get(s.get('tier', 'discard'), 1), s.get('start_time', 0)))

    return jsonify({
        'segments': filtered_segments,
        'total_count': len(filtered_segments),
        'filter_applied': {
            'exclude_garbage': exclude_garbage,
            'min_tier': min_tier,
            'garbage_types_excluded': garbage_types_to_exclude
        }
    })


@app.route('/api/analysis/<analysis_id>/garbage', methods=['GET'])
def get_analysis_garbage(analysis_id):
    """
    Obtiene detalles de basura para un análisis específico.
    """
    analysis_file = ANALYZED_FOLDER / f'{analysis_id}.json'

    if not analysis_file.exists():
        return jsonify({'error': 'Análisis no encontrado'}), 404

    try:
        with open(analysis_file, 'r') as f:
            data = json.load(f)

        garbage_info = data.get('garbage', {})

        return jsonify({
            'filename': data.get('filename'),
            'garbage': garbage_info,
            'garbage_segments': [
                s for s in data.get('segments', [])
                if s.get('is_garbage', False)
            ]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# FIN ENDPOINTS DE BASURA
# ============================================================


# ============================================================
# NUEVOS ENDPOINTS - CLASIFICACIÓN DE PLANOS (Fase 2 v5.0)
# ============================================================

@app.route('/api/projects/<project_id>/framing-stats', methods=['GET'])
def get_project_framing_stats(project_id):
    """
    Obtiene estadísticas de tipos de plano en el proyecto.

    Returns:
        {
            'framing_types': {'PLANO_MEDIO': 12, 'PRIMER_PLANO': 8, ...},
            'total_by_type': {'PLANO_MEDIO': 45.2, ...},  # duración en segundos
            'faces_detected_total': 25,
            'segments_with_faces': 18
        }
    """
    framing_types_count = {}
    framing_types_duration = {}
    total_faces = 0
    segments_with_faces = 0

    for analysis_file in ANALYZED_FOLDER.glob('*.json'):
        try:
            with open(analysis_file, 'r') as f:
                data = json.load(f)

            if data.get('project_id') != project_id:
                continue

            for segment in data.get('segments', []):
                framing_type = segment.get('framing_type', 'DESCONOCIDO')
                duration = segment.get('duration', 0)
                face_count = segment.get('face_count', 0)

                framing_types_count[framing_type] = framing_types_count.get(framing_type, 0) + 1
                framing_types_duration[framing_type] = framing_types_duration.get(framing_type, 0) + duration

                if face_count > 0:
                    total_faces += face_count
                    segments_with_faces += 1

        except Exception as e:
            print(f"Error reading framing stats from {analysis_file}: {e}")
            continue

    return jsonify({
        'framing_types_count': framing_types_count,
        'framing_types_duration': framing_types_duration,
        'total_faces_detected': total_faces,
        'segments_with_faces': segments_with_faces
    })


@app.route('/api/projects/<project_id>/segments/by-framing', methods=['GET'])
def get_segments_by_framing(project_id):
    """
    Obtiene segmentos agrupados por tipo de plano.

    Query params:
        - framing_type: filtrar por tipo específico (ej: 'PRIMER_PLANO')
        - min_tier: tier mínimo ('gold', 'silver', 'bronze', 'discard')
        - with_faces: 'true' para solo segmentos con rostros

    Returns:
        Lista de segmentos con información del video de origen
    """
    framing_type_filter = request.args.get('framing_type')
    min_tier = request.args.get('min_tier', 'discard')
    with_faces = request.args.get('with_faces', 'false').lower() == 'true'

    tier_order = {'gold': 4, 'silver': 3, 'bronze': 2, 'discard': 1}
    min_tier_value = tier_order.get(min_tier, 1)

    segments_by_type = {}

    for analysis_file in ANALYZED_FOLDER.glob('*.json'):
        try:
            with open(analysis_file, 'r') as f:
                data = json.load(f)

            if data.get('project_id') != project_id:
                continue

            filename = data.get('filename', analysis_file.stem)

            for segment in data.get('segments', []):
                framing_type = segment.get('framing_type', 'DESCONOCIDO')
                segment_tier = segment.get('tier', 'discard')
                face_count = segment.get('face_count', 0)

                # Aplicar filtros
                if framing_type_filter and framing_type != framing_type_filter:
                    continue

                if tier_order.get(segment_tier, 1) < min_tier_value:
                    continue

                if with_faces and face_count == 0:
                    continue

                # Agregar info del video
                segment_copy = segment.copy()
                segment_copy['video_filename'] = filename
                segment_copy['video_path'] = data.get('path', '')

                if framing_type not in segments_by_type:
                    segments_by_type[framing_type] = []
                segments_by_type[framing_type].append(segment_copy)

        except Exception as e:
            print(f"Error reading segments from {analysis_file}: {e}")
            continue

    # Ordenar cada grupo por score
    for framing_type in segments_by_type:
        segments_by_type[framing_type].sort(key=lambda s: s.get('score', 0), reverse=True)

    return jsonify({
        'segments_by_type': segments_by_type,
        'types_found': list(segments_by_type.keys()),
        'total_segments': sum(len(segs) for segs in segments_by_type.values())
    })


@app.route('/api/projects/<project_id>/best-by-framing/<framing_type>', methods=['GET'])
def get_best_by_framing(project_id, framing_type):
    """
    Obtiene los mejores N segmentos de un tipo de plano específico.

    Query params:
        - limit: número máximo de resultados (default: 10)
        - min_tier: tier mínimo ('gold', 'silver', 'bronze')

    Returns:
        Lista de los mejores segmentos de ese tipo de plano
    """
    limit = int(request.args.get('limit', 10))
    min_tier = request.args.get('min_tier', 'bronze')

    tier_order = {'gold': 4, 'silver': 3, 'bronze': 2, 'discard': 1}
    min_tier_value = tier_order.get(min_tier, 2)

    all_segments = []

    for analysis_file in ANALYZED_FOLDER.glob('*.json'):
        try:
            with open(analysis_file, 'r') as f:
                data = json.load(f)

            if data.get('project_id') != project_id:
                continue

            filename = data.get('filename', analysis_file.stem)

            for segment in data.get('segments', []):
                seg_framing = segment.get('framing_type', 'DESCONOCIDO')
                segment_tier = segment.get('tier', 'discard')

                if seg_framing != framing_type:
                    continue

                if tier_order.get(segment_tier, 1) < min_tier_value:
                    continue

                segment_copy = segment.copy()
                segment_copy['video_filename'] = filename
                segment_copy['video_path'] = data.get('path', '')
                all_segments.append(segment_copy)

        except Exception as e:
            continue

    # Ordenar por score y limitar
    all_segments.sort(key=lambda s: s.get('score', 0), reverse=True)
    best_segments = all_segments[:limit]

    return jsonify({
        'framing_type': framing_type,
        'segments': best_segments,
        'total_found': len(all_segments),
        'returned': len(best_segments)
    })


@app.route('/api/framing-types', methods=['GET'])
def get_framing_types():
    """
    Retorna lista de todos los tipos de plano disponibles con sus nombres.
    """
    framing_types = {
        'PLANO_GENERAL_EXTREMO': {'short': 'EWS', 'display': 'Plano General Extremo'},
        'PLANO_GENERAL': {'short': 'WS', 'display': 'Plano General'},
        'PLANO_AMERICANO': {'short': 'MWS', 'display': 'Plano Americano'},
        'PLANO_MEDIO': {'short': 'MS', 'display': 'Plano Medio'},
        'PLANO_MEDIO_CORTO': {'short': 'MCU', 'display': 'Plano Medio Corto'},
        'PRIMER_PLANO': {'short': 'CU', 'display': 'Primer Plano'},
        'PRIMERÍSIMO_PLANO': {'short': 'ECU', 'display': 'Primerísimo Plano'},
        'PLANO_DETALLE': {'short': 'DET', 'display': 'Plano Detalle'},
        'OVER_THE_SHOULDER': {'short': 'OTS', 'display': 'Over the Shoulder'},
        'PUNTO_DE_VISTA': {'short': 'POV', 'display': 'Punto de Vista'},
        'PLANO_DOS': {'short': '2S', 'display': 'Plano Dos'},
        'PLANO_GRUPO': {'short': 'GRP', 'display': 'Plano Grupo'},
        'INSERT': {'short': 'INS', 'display': 'Insert'},
        'DESCONOCIDO': {'short': '?', 'display': 'Desconocido'},
    }

    return jsonify(framing_types)


# ============================================================
# FIN ENDPOINTS DE CLASIFICACIÓN DE PLANOS
# ============================================================


# ============================================================
# ENDPOINTS DE ANÁLISIS DE ROSTROS (FASE 3)
# ============================================================

@app.route('/api/projects/<project_id>/face-stats', methods=['GET'])
def get_project_face_stats(project_id):
    """
    Obtiene estadísticas de rostros en el proyecto.
    Retorna: segmentos con rostros, ojos cerrados, etc.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    if not segments:
        return jsonify({
            'project_id': project_id,
            'total_segments': 0,
            'segments_with_faces': 0,
            'segments_with_faces_pct': 0,
            'segments_with_eyes_closed': 0,
            'avg_face_count': 0,
            'face_coverage_distribution': {},
        })

    # Calcular estadísticas
    segments_with_faces = [s for s in segments if s.get('face_analysis', {}).get('has_faces', False)]
    segments_with_eyes_closed = [s for s in segments if s.get('any_eyes_closed', False)]

    # Distribución por número de rostros
    face_count_dist = {}
    for s in segments:
        face_count = s.get('face_count', 0)
        face_count_dist[face_count] = face_count_dist.get(face_count, 0) + 1

    # Distribución por cobertura de rostro principal
    coverage_ranges = {'tiny': 0, 'small': 0, 'medium': 0, 'large': 0, 'very_large': 0}
    for s in segments_with_faces:
        coverage = s.get('face_analysis', {}).get('primary_face_coverage', 0)
        if coverage < 0.02:
            coverage_ranges['tiny'] += 1
        elif coverage < 0.05:
            coverage_ranges['small'] += 1
        elif coverage < 0.15:
            coverage_ranges['medium'] += 1
        elif coverage < 0.30:
            coverage_ranges['large'] += 1
        else:
            coverage_ranges['very_large'] += 1

    return jsonify({
        'project_id': project_id,
        'total_segments': len(segments),
        'segments_with_faces': len(segments_with_faces),
        'segments_with_faces_pct': round(len(segments_with_faces) / len(segments) * 100, 1) if segments else 0,
        'segments_with_eyes_closed': len(segments_with_eyes_closed),
        'eyes_closed_pct': round(len(segments_with_eyes_closed) / len(segments) * 100, 1) if segments else 0,
        'avg_face_count': round(sum(s.get('face_count', 0) for s in segments) / len(segments), 2) if segments else 0,
        'face_count_distribution': face_count_dist,
        'coverage_distribution': coverage_ranges,
    })


@app.route('/api/projects/<project_id>/segments/with-faces', methods=['GET'])
def get_segments_with_faces(project_id):
    """
    Obtiene todos los segmentos que contienen rostros detectados.
    Query params:
      - min_faces: número mínimo de rostros (default: 1)
      - eyes_open_only: si true, excluye segmentos con ojos cerrados
      - in_focus_only: si true, solo rostros en foco
      - tier: filtrar por tier
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Parámetros de filtro
    min_faces = request.args.get('min_faces', 1, type=int)
    eyes_open_only = request.args.get('eyes_open_only', 'false').lower() == 'true'
    in_focus_only = request.args.get('in_focus_only', 'false').lower() == 'true'
    tier_filter = request.args.get('tier')

    # Filtrar
    filtered = []
    for s in segments:
        face_count = s.get('face_count', 0)
        if face_count < min_faces:
            continue

        if eyes_open_only and s.get('any_eyes_closed', False):
            continue

        if in_focus_only and not s.get('faces_in_focus', False):
            continue

        if tier_filter and s.get('tier') != tier_filter:
            continue

        filtered.append(s)

    # Ordenar por número de rostros y luego por score
    filtered.sort(key=lambda x: (-x.get('face_count', 0), -x.get('score', 0)))

    return jsonify({
        'project_id': project_id,
        'total_with_faces': len(filtered),
        'filters_applied': {
            'min_faces': min_faces,
            'eyes_open_only': eyes_open_only,
            'in_focus_only': in_focus_only,
            'tier': tier_filter,
        },
        'segments': filtered
    })


@app.route('/api/projects/<project_id>/segments/eyes-closed', methods=['GET'])
def get_segments_eyes_closed(project_id):
    """
    Obtiene segmentos donde se detectaron ojos cerrados.
    Útil para identificar blinks o tomas problemáticas.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Filtrar solo los que tienen ojos cerrados
    eyes_closed = [s for s in segments if s.get('any_eyes_closed', False)]

    # Ordenar por porcentaje de frames con ojos cerrados (si disponible)
    eyes_closed.sort(
        key=lambda x: x.get('face_analysis', {}).get('eyes_closed_frame_pct', 0),
        reverse=True
    )

    return jsonify({
        'project_id': project_id,
        'total_segments': len(segments),
        'segments_with_eyes_closed': len(eyes_closed),
        'segments': eyes_closed
    })


@app.route('/api/projects/<project_id>/best-faces', methods=['GET'])
def get_best_face_segments(project_id):
    """
    Obtiene los mejores segmentos con rostros (en foco, ojos abiertos, bien encuadrados).
    Query params:
      - limit: número máximo de segmentos (default: 10)
      - face_count: número específico de rostros (1, 2, etc.)
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    limit = request.args.get('limit', 10, type=int)
    face_count_filter = request.args.get('face_count', type=int)

    # Filtrar segmentos con rostros
    with_faces = [s for s in segments if s.get('face_count', 0) > 0]

    # Filtrar por número de rostros si se especifica
    if face_count_filter:
        with_faces = [s for s in with_faces if s.get('face_count', 0) == face_count_filter]

    # Scoring personalizado para "mejores rostros"
    def face_quality_score(segment):
        score = 0

        # Base: tier score
        tier_scores = {'gold': 40, 'silver': 30, 'bronze': 20, 'discard': 0}
        score += tier_scores.get(segment.get('tier', 'discard'), 0)

        # Bonus por rostros en foco
        if segment.get('faces_in_focus', False):
            score += 25

        # Penalización por ojos cerrados
        if segment.get('any_eyes_closed', False):
            score -= 30

        # Bonus por cobertura (rostro más grande = más útil para close-ups)
        coverage = segment.get('face_analysis', {}).get('primary_face_coverage', 0)
        score += coverage * 50

        # Penalización por problemas de encuadre
        framing_issues = segment.get('face_analysis', {}).get('avg_framing_issues', 0)
        score -= framing_issues * 10

        return score

    # Ordenar por quality score
    with_faces.sort(key=face_quality_score, reverse=True)

    return jsonify({
        'project_id': project_id,
        'total_with_faces': len(with_faces),
        'returned': min(limit, len(with_faces)),
        'filter_face_count': face_count_filter,
        'segments': with_faces[:limit]
    })


# ============================================================
# FIN ENDPOINTS DE ANÁLISIS DE ROSTROS
# ============================================================


# ============================================================
# ENDPOINTS DE AGRUPACIÓN POR ESCENAS (FASE 4)
# ============================================================

@app.route('/api/projects/<project_id>/scene-groups', methods=['GET'])
def get_project_scene_groups(project_id):
    """
    Obtiene los grupos de escenas/setups del proyecto.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    scenes_data = project.get('scenes', {})

    return jsonify({
        'project_id': project_id,
        'groups': scenes_data.get('groups', []),
        'total_groups': scenes_data.get('total_groups', 0),
        'summary': scenes_data.get('summary', {}),
    })


@app.route('/api/projects/<project_id>/scene-changes', methods=['GET'])
def get_project_scene_changes(project_id):
    """
    Obtiene los cambios de escena detectados en el proyecto.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    scenes_data = project.get('scenes', {})

    return jsonify({
        'project_id': project_id,
        'scene_changes': scenes_data.get('scene_changes', []),
        'total_changes': len(scenes_data.get('scene_changes', [])),
    })


@app.route('/api/projects/<project_id>/segments/by-scene/<int:group_id>', methods=['GET'])
def get_segments_by_scene(project_id, group_id):
    """
    Obtiene todos los segmentos de un grupo/escena específico.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Filtrar por grupo
    group_segments = [s for s in segments if s.get('scene_group_id') == group_id]

    # Obtener info del grupo
    scenes_data = project.get('scenes', {})
    group_info = None
    for g in scenes_data.get('groups', []):
        if g.get('group_id') == group_id:
            group_info = g
            break

    return jsonify({
        'project_id': project_id,
        'group_id': group_id,
        'group_info': group_info,
        'segment_count': len(group_segments),
        'segments': group_segments
    })


@app.route('/api/projects/<project_id>/best-by-scene/<int:group_id>', methods=['GET'])
def get_best_by_scene(project_id, group_id):
    """
    Obtiene los mejores N segmentos de un grupo/escena específico.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    limit = request.args.get('limit', 5, type=int)

    # Filtrar por grupo
    group_segments = [s for s in segments if s.get('scene_group_id') == group_id]

    # Ordenar por score
    group_segments.sort(key=lambda x: x.get('score', 0), reverse=True)

    return jsonify({
        'project_id': project_id,
        'group_id': group_id,
        'total_in_group': len(group_segments),
        'returned': min(limit, len(group_segments)),
        'segments': group_segments[:limit]
    })


@app.route('/api/projects/<project_id>/similar-segments/<int:segment_idx>', methods=['GET'])
def get_similar_segments(project_id, segment_idx):
    """
    Encuentra segmentos visualmente similares a uno dado.
    """
    from scene_grouper import SceneGrouper

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    limit = request.args.get('limit', 5, type=int)

    if segment_idx >= len(segments):
        return jsonify({'error': 'Índice de segmento inválido'}), 400

    # Usar el grouper para encontrar similares
    grouper = SceneGrouper()
    similar = grouper.get_similar_segments(segments, segment_idx, limit)

    # Construir respuesta con datos de segmentos
    similar_segments = []
    for idx, similarity in similar:
        seg = segments[idx].copy()
        seg['similarity_score'] = round(similarity, 3)
        similar_segments.append(seg)

    return jsonify({
        'project_id': project_id,
        'reference_segment': segment_idx,
        'similar_count': len(similar_segments),
        'segments': similar_segments
    })


# ============================================================
# FIN ENDPOINTS DE AGRUPACIÓN POR ESCENAS
# ============================================================


# ============================================================
# ENDPOINTS DE TAKES REPETIDOS (FASE 5)
# ============================================================

@app.route('/api/projects/<project_id>/take-groups', methods=['GET'])
def get_project_take_groups(project_id):
    """
    Obtiene los grupos de takes repetidos del proyecto.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    takes_data = project.get('takes', {})

    return jsonify({
        'project_id': project_id,
        'groups': takes_data.get('groups', []),
        'total_groups': takes_data.get('total_groups', 0),
        'total_repeated': takes_data.get('total_repeated', 0),
        'potential_savings': takes_data.get('potential_savings', 0),
        'summary': takes_data.get('summary', {}),
    })


@app.route('/api/projects/<project_id>/repeated-takes', methods=['GET'])
def get_repeated_takes(project_id):
    """
    Obtiene todos los segmentos que son takes repetidos (no los mejores).
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Filtrar solo los que son takes repetidos (no los mejores)
    repeated = [s for s in segments if s.get('is_repeated_take', False)]

    # Calcular duración total a ahorrar
    total_duration = sum(s.get('duration', 0) for s in repeated)

    return jsonify({
        'project_id': project_id,
        'repeated_count': len(repeated),
        'total_duration_savings': round(total_duration, 2),
        'segments': repeated
    })


@app.route('/api/projects/<project_id>/take-group/<int:group_id>', methods=['GET'])
def get_take_group_detail(project_id, group_id):
    """
    Obtiene detalle de un grupo de takes específico.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    takes_data = project.get('takes', {})
    groups = takes_data.get('groups', [])

    # Buscar el grupo
    group = None
    for g in groups:
        if g.get('group_id') == group_id:
            group = g
            break

    if not group:
        return jsonify({'error': 'Grupo no encontrado'}), 404

    # Obtener segmentos del grupo
    segments = project.get('segments', [])
    group_segments = [segments[i] for i in group.get('takes', []) if i < len(segments)]

    return jsonify({
        'project_id': project_id,
        'group': group,
        'segments': group_segments,
        'best_take_segment': segments[group['best_take']] if group['best_take'] < len(segments) else None
    })


@app.route('/api/projects/<project_id>/take-recommendations', methods=['GET'])
def get_take_recommendations(project_id):
    """
    Obtiene recomendaciones de qué takes usar/descartar.
    """
    from take_detector import TakeDetector

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    takes_data = project.get('takes', {})

    # Reconstruir resultado para obtener recomendaciones
    from take_detector import TakeDetectionResult, TakeGroup

    groups = []
    for g_dict in takes_data.get('groups', []):
        group = TakeGroup(
            group_id=g_dict['group_id'],
            takes=g_dict['takes'],
            best_take=g_dict['best_take'],
            take_count=g_dict['take_count'],
            avg_score=g_dict['avg_score'],
            best_score=g_dict['best_score'],
            worst_score=g_dict['worst_score'],
            recommended_takes=g_dict['recommended_takes'],
            discard_takes=g_dict['discard_takes']
        )
        groups.append(group)

    result = TakeDetectionResult(
        take_groups=groups,
        matches=[],  # No necesitamos los matches para recomendaciones
        segment_to_group={i: g.group_id for g in groups for i in g.takes},
        total_groups=len(groups),
        total_repeated_takes=sum(g.take_count - 1 for g in groups),
        potential_savings_duration=takes_data.get('potential_savings', 0)
    )

    detector = TakeDetector()
    recommendations = detector.get_take_recommendations(result, segments)

    return jsonify({
        'project_id': project_id,
        'recommendations': recommendations,
        'summary': {
            'use_count': len(recommendations['use']),
            'consider_count': len(recommendations['consider']),
            'skip_count': len(recommendations['skip']),
        }
    })


# ============================================================
# FIN ENDPOINTS DE TAKES REPETIDOS
# ============================================================


# ============================================================
# ENDPOINTS DE ETIQUETADO CONTEXTUAL (Fase 6)
# ============================================================

@app.route('/api/projects/<project_id>/tags', methods=['GET'])
def get_project_tags(project_id):
    """
    Obtiene todos los tags del proyecto.
    Query params:
    - category: Filtrar por categoría (content, context, quality, composition)
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    tagging_data = project.get('tagging', {})
    category_filter = request.args.get('category')

    segment_tags = tagging_data.get('segment_tags', [])

    # Filtrar por categoría si se especifica
    if category_filter and segment_tags:
        filtered_tags = []
        for st in segment_tags:
            filtered = {
                'segment_idx': st['segment_idx'],
                'tags': [t for t in st.get('tags', []) if t.get('category') == category_filter],
                'auto_description': st.get('auto_description', ''),
            }
            if filtered['tags']:
                filtered_tags.append(filtered)
        segment_tags = filtered_tags

    return jsonify({
        'project_id': project_id,
        'segment_tags': segment_tags,
        'all_tags': tagging_data.get('all_tags', []),
        'tag_frequency': tagging_data.get('tag_frequency', {}),
        'summary': tagging_data.get('summary', {}),
    })


@app.route('/api/projects/<project_id>/key-moments', methods=['GET'])
def get_key_moments(project_id):
    """
    Obtiene los momentos clave detectados en el proyecto.
    Query params:
    - type: Filtrar por tipo (best_quality, best_of_scene, unique_content, opening, closing)
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    tagging_data = project.get('tagging', {})
    key_moments = tagging_data.get('key_moments', [])
    segments = project.get('segments', [])

    type_filter = request.args.get('type')
    if type_filter:
        key_moments = [km for km in key_moments if km.get('moment_type') == type_filter]

    # Enriquecer con información del segmento
    enriched_moments = []
    for km in key_moments:
        idx = km.get('segment_idx', 0)
        seg = segments[idx] if idx < len(segments) else {}

        enriched_moments.append({
            **km,
            'segment_info': {
                'score': seg.get('score', 0),
                'tier': seg.get('tier', ''),
                'duration': seg.get('duration', 0),
                'start_time': seg.get('start_time', 0),
                'framing_type': seg.get('framing_type', ''),
                'thumbnail_time': seg.get('start_time', 0) + seg.get('duration', 0) / 2,
            }
        })

    return jsonify({
        'project_id': project_id,
        'key_moments': enriched_moments,
        'total': len(enriched_moments),
    })


@app.route('/api/projects/<project_id>/segments-by-tag/<tag_name>', methods=['GET'])
def get_segments_by_tag(project_id, tag_name):
    """
    Obtiene todos los segmentos que tienen un tag específico.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Filtrar segmentos que tienen el tag
    matching_segments = []
    for i, seg in enumerate(segments):
        seg_tags = seg.get('tags', [])
        if tag_name in seg_tags:
            matching_segments.append({
                'index': i,
                'score': seg.get('score', 0),
                'tier': seg.get('tier', ''),
                'duration': seg.get('duration', 0),
                'start_time': seg.get('start_time', 0),
                'framing_type': seg.get('framing_type', ''),
                'tags': seg_tags,
                'auto_description': seg.get('auto_description', ''),
            })

    return jsonify({
        'project_id': project_id,
        'tag': tag_name,
        'segments': matching_segments,
        'count': len(matching_segments),
    })


@app.route('/api/projects/<project_id>/tag-statistics', methods=['GET'])
def get_tag_statistics(project_id):
    """
    Obtiene estadísticas de etiquetado del proyecto.
    """
    from context_tagger import ContextTagger, TaggingResult, SegmentTags, Tag, TagCategory

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    tagging_data = project.get('tagging', {})

    # Calcular estadísticas
    segment_tags_data = tagging_data.get('segment_tags', [])
    tag_frequency = tagging_data.get('tag_frequency', {})
    all_tags = tagging_data.get('all_tags', [])

    total_tags = sum(len(st.get('tags', [])) for st in segment_tags_data)
    total_segments = len(segment_tags_data)

    # Agrupar por categoría
    by_category = {}
    for st in segment_tags_data:
        for tag in st.get('tags', []):
            cat = tag.get('category', 'unknown')
            if cat not in by_category:
                by_category[cat] = {}
            name = tag.get('name', '')
            by_category[cat][name] = by_category[cat].get(name, 0) + 1

    # Tags más comunes
    most_common = sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)[:15]

    return jsonify({
        'project_id': project_id,
        'statistics': {
            'total_tags': total_tags,
            'unique_tags': len(all_tags),
            'total_segments': total_segments,
            'avg_tags_per_segment': round(total_tags / total_segments, 2) if total_segments > 0 else 0,
            'key_moments_count': len(tagging_data.get('key_moments', [])),
        },
        'most_common_tags': [{'tag': t, 'count': c} for t, c in most_common],
        'tags_by_category': by_category,
    })


@app.route('/api/projects/<project_id>/segment/<int:segment_idx>/tags', methods=['GET'])
def get_segment_tags(project_id, segment_idx):
    """
    Obtiene los tags de un segmento específico.
    """
    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    if segment_idx < 0 or segment_idx >= len(segments):
        return jsonify({'error': 'Índice de segmento inválido'}), 400

    segment = segments[segment_idx]
    tagging_data = project.get('tagging', {})
    segment_tags_list = tagging_data.get('segment_tags', [])

    # Buscar tags de este segmento
    seg_tags = next(
        (st for st in segment_tags_list if st.get('segment_idx') == segment_idx),
        {'tags': [], 'auto_description': ''}
    )

    return jsonify({
        'project_id': project_id,
        'segment_idx': segment_idx,
        'tags': seg_tags.get('tags', []),
        'tag_names': seg_tags.get('tag_names', segment.get('tags', [])),
        'auto_description': seg_tags.get('auto_description', segment.get('auto_description', '')),
        'is_key_moment': segment.get('is_key_moment', False),
        'key_moment_type': segment.get('key_moment_type'),
        'key_moment_reason': segment.get('key_moment_reason'),
    })


# ============================================================
# FIN ENDPOINTS DE ETIQUETADO CONTEXTUAL
# ============================================================


# ============================================================
# ENDPOINTS DE BÚSQUEDA TRANSVERSAL (Fase 7)
# ============================================================

@app.route('/api/projects/<project_id>/search', methods=['POST'])
def search_segments(project_id):
    """
    Búsqueda avanzada de segmentos con múltiples criterios.

    Body JSON:
    {
        "filters": {
            "operator": "and",  // "and" | "or"
            "filters": [
                {"field": "tier", "operator": "eq", "value": "GOLD"},
                {"field": "score", "operator": "gte", "value": 7.0},
                {"field": "tags", "operator": "contains", "value": "persona"}
            ]
        },
        "sort_by": "score",
        "sort_order": "desc",
        "page": 1,
        "page_size": 20
    }

    Operadores disponibles:
    - eq, neq: igual, no igual
    - gt, gte, lt, lte: mayor/menor que
    - in, not_in: en lista
    - contains, not_contains: contiene (para strings/arrays)
    - between: entre dos valores [min, max]
    - exists, is_true, is_false: existencia y booleanos
    """
    from search_engine import SearchEngine, build_query_from_dict, get_search_summary

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])
    query_dict = request.get_json() or {}

    try:
        engine = SearchEngine()
        query = build_query_from_dict(query_dict)
        result = engine.search(segments, query)

        return jsonify({
            'project_id': project_id,
            'results': result.to_dict(),
            'summary': get_search_summary(result),
        })
    except Exception as e:
        return jsonify({'error': f'Error en búsqueda: {str(e)}'}), 400


@app.route('/api/projects/<project_id>/quick-search', methods=['GET'])
def quick_search_segments(project_id):
    """
    Búsqueda rápida con parámetros de URL.

    Query params:
    - tier: GOLD, SILVER, BRONZE, DISCARD
    - score_min, score_max: rango de puntuación
    - duration_min, duration_max: rango de duración
    - has_faces: true/false
    - shot_type: ESTATICA, PANEO, TILT, TRACKING
    - framing_type: CLOSE_UP, MEDIUM, WIDE, etc.
    - tag: buscar por tag específico
    - scene_group: ID de grupo de escena
    - is_key_moment: true/false
    - is_best_take: true/false
    - exclude_repeated: true/false
    - sort_by: campo para ordenar
    - sort_desc: true para orden descendente
    """
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    segments = project.get('segments', [])

    # Construir kwargs desde query params
    kwargs = {}

    if request.args.get('tier'):
        kwargs['tier'] = request.args.get('tier')

    if request.args.get('score_min'):
        kwargs['score_min'] = float(request.args.get('score_min'))

    if request.args.get('score_max'):
        kwargs['score_max'] = float(request.args.get('score_max'))

    if request.args.get('duration_min'):
        kwargs['duration_min'] = float(request.args.get('duration_min'))

    if request.args.get('duration_max'):
        kwargs['duration_max'] = float(request.args.get('duration_max'))

    if request.args.get('has_faces'):
        kwargs['has_faces'] = request.args.get('has_faces').lower() == 'true'

    if request.args.get('shot_type'):
        kwargs['shot_type'] = request.args.get('shot_type')

    if request.args.get('framing_type'):
        kwargs['framing_type'] = request.args.get('framing_type')

    if request.args.get('tag'):
        kwargs['has_tag'] = request.args.get('tag')

    if request.args.get('scene_group'):
        kwargs['scene_group'] = int(request.args.get('scene_group'))

    if request.args.get('is_key_moment'):
        kwargs['is_key_moment'] = request.args.get('is_key_moment').lower() == 'true'

    if request.args.get('is_best_take'):
        kwargs['is_best_take'] = request.args.get('is_best_take').lower() == 'true'

    if request.args.get('exclude_repeated'):
        kwargs['exclude_repeated'] = request.args.get('exclude_repeated').lower() == 'true'

    if request.args.get('sort_by'):
        kwargs['sort_by'] = request.args.get('sort_by')

    if request.args.get('sort_desc'):
        kwargs['sort_desc'] = request.args.get('sort_desc').lower() == 'true'

    engine = SearchEngine()
    results = engine.quick_search(segments, **kwargs)

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
        'filters_applied': kwargs,
    })


@app.route('/api/projects/<project_id>/find/gold', methods=['GET'])
def find_gold_segments(project_id):
    """Encuentra todos los segmentos GOLD ordenados por score."""
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    engine = SearchEngine()
    results = engine.find_gold_segments(project.get('segments', []))

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
    })


@app.route('/api/projects/<project_id>/find/usable', methods=['GET'])
def find_usable_segments(project_id):
    """Encuentra segmentos usables (GOLD + SILVER, sin repetidos)."""
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    engine = SearchEngine()
    results = engine.find_usable_segments(project.get('segments', []))

    total_duration = sum(s.get('duration', 0) for s in results)

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
        'total_duration': round(total_duration, 2),
    })


@app.route('/api/projects/<project_id>/find/faces', methods=['GET'])
def find_segments_with_faces(project_id):
    """Encuentra segmentos con rostros detectados."""
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    engine = SearchEngine()
    results = engine.find_segments_with_faces(project.get('segments', []))

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
    })


@app.route('/api/projects/<project_id>/find/interviews', methods=['GET'])
def find_interview_candidates(project_id):
    """Encuentra segmentos candidatos a entrevista."""
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    engine = SearchEngine()
    results = engine.find_interview_candidates(project.get('segments', []))

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
    })


@app.route('/api/projects/<project_id>/find/static', methods=['GET'])
def find_static_shots(project_id):
    """Encuentra tomas estáticas."""
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    engine = SearchEngine()
    results = engine.find_static_shots(project.get('segments', []))

    return jsonify({
        'project_id': project_id,
        'segments': results,
        'count': len(results),
    })


@app.route('/api/projects/<project_id>/find/time-range', methods=['GET'])
def find_segments_in_time_range(project_id):
    """
    Encuentra segmentos en un rango temporal.

    Query params:
    - start: tiempo inicial en segundos
    - end: tiempo final en segundos
    """
    from search_engine import SearchEngine

    project = get_project(project_id)
    if not project:
        return jsonify({'error': 'Proyecto no encontrado'}), 404

    start_time = float(request.args.get('start', 0))
    end_time = float(request.args.get('end', float('inf')))

    if end_time == float('inf'):
        # Si no se especifica end, usar duración del proyecto
        end_time = project.get('duration', 0)

    engine = SearchEngine()
    results = engine.find_segments_in_range(
        project.get('segments', []),
        start_time,
        end_time
    )

    return jsonify({
        'project_id': project_id,
        'time_range': {'start': start_time, 'end': end_time},
        'segments': results,
        'count': len(results),
    })


@app.route('/api/search/filters', methods=['GET'])
def get_available_search_filters():
    """Retorna información sobre los filtros de búsqueda disponibles."""
    from search_engine import get_available_filters

    return jsonify(get_available_filters())


# ============================================================
# FIN ENDPOINTS DE BÚSQUEDA TRANSVERSAL
# ============================================================


def run_analysis(config, project_id, analysis_categories=None, intelligent_analysis=None):
    """Ejecuta el análisis en background. Requiere project_id."""
    global analysis_state

    # Configuración por defecto de categorías técnicas
    if analysis_categories is None:
        analysis_categories = {
            'stability': True,
            'focus': True,
            'exposure': True,
            'composition': True,
        }

    # Configuración por defecto de análisis inteligente
    if intelligent_analysis is None:
        intelligent_analysis = {
            'garbage_detection': True,
            'shot_classification': True,
            'face_analysis': True,
            'scene_grouping': True,
            'take_detection': True,
            'key_moments': True,
        }

    videos = [f for f in UPLOAD_FOLDER.iterdir()
              if f.is_file() and f.suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS]

    if not videos:
        return

    # project_id es obligatorio
    if not project_id:
        analysis_state['log'].append('Error: Se requiere un proyecto para analizar')
        return

    # Calcular tiempo estimado total
    total_estimated = sum(estimate_analysis_time(get_video_duration(v)) for v in videos)
    video_names = [v.name for v in sorted(videos)]

    analysis_state = {
        'running': True,
        'progress': 0,
        'current_video': '',
        'current_progress': 0,
        'total_videos': len(videos),
        'completed': 0,
        'results': None,
        'xml_file': None,
        'project_id': project_id,
        'log': ['Iniciando análisis...'],
        'pending_videos': video_names.copy(),
        'completed_videos': [],
        'video_results': {},
        'start_time': time.time(),
        'estimated_total': total_estimated,
        'elapsed': 0
    }

    project = get_project(project_id)
    if project:
        analysis_state['log'].append(f'Proyecto: {project["name"]}')

    try:
        analysis_state['log'].append(f'Encontrados {len(videos)} videos')

        # Pasar las categorías activas y opciones inteligentes al analizador
        analyzer_config = {
            'analysis_categories': analysis_categories,
            'intelligent_analysis': intelligent_analysis
        }
        analyzer = VideoAnalyzer(analyzer_config)
        
        results = []
        timeline_offset = 0  # Offset acumulado para múltiples videos
        
        for i, video_path in enumerate(sorted(videos)):
            video_name = video_path.name

            # Actualizar estado: este video está siendo analizado
            analysis_state['current_video'] = video_name
            analysis_state['current_progress'] = 0
            video_start_time = time.time()  # Tiempo de inicio de este video
            video_duration = get_video_duration(video_path)
            video_estimated = estimate_analysis_time(video_duration)
            if video_name in analysis_state['pending_videos']:
                analysis_state['pending_videos'].remove(video_name)
            analysis_state['log'].append(f'Analizando: {video_name}')

            # Actualizar tiempo transcurrido
            analysis_state['elapsed'] = int(time.time() - analysis_state['start_time'])

            # Hilo para actualizar progreso del video actual
            progress_stop = threading.Event()
            def update_video_progress():
                while not progress_stop.is_set():
                    elapsed = time.time() - video_start_time
                    # Calcular progreso basado en tiempo estimado (máx 95% hasta que termine)
                    progress = min(95, int((elapsed / max(1, video_estimated)) * 100))
                    analysis_state['current_progress'] = progress
                    analysis_state['elapsed'] = int(time.time() - analysis_state['start_time'])
                    time.sleep(0.5)

            progress_thread = threading.Thread(target=update_video_progress, daemon=True)
            progress_thread.start()

            result = analyzer.analyze_video(str(video_path))

            # Detener hilo de progreso
            progress_stop.set()
            progress_thread.join(timeout=1)

            # Calcular tiempo real de análisis de este video
            video_analysis_duration = int(time.time() - video_start_time)

            # Obtener resolución real del video
            resolution = get_video_resolution(video_path)
            result['width'] = resolution['width']
            result['height'] = resolution['height']
            result['timeline_offset'] = timeline_offset  # Guardar offset para el XML

            results.append(result)

            # Actualizar offset para el siguiente video
            if result['success']:
                timeline_offset += result.get('duration', 0)

            # Marcar como completado
            analysis_state['completed'] = i + 1
            analysis_state['progress'] = int((i + 1) / len(videos) * 100)
            analysis_state['current_progress'] = 100
            analysis_state['completed_videos'].append(video_name)
            analysis_state['elapsed'] = int(time.time() - analysis_state['start_time'])

            if result['success']:
                gold = result['tier_durations']['gold']
                silver = result['tier_durations']['silver']
                bronze = result['tier_durations'].get('bronze', 0)
                segments = len(result.get('segments', []))

                # Guardar resultados por video incluyendo tiempo de análisis
                analysis_state['video_results'][video_name] = {
                    'gold': gold,
                    'silver': silver,
                    'bronze': bronze,
                    'segments': segments,
                    'success': True,
                    'analysis_duration': video_analysis_duration  # Tiempo real que tardó
                }
                analysis_state['log'].append(f'  ✓ {segments} segmentos | Gold: {gold:.1f}s, Silver: {silver:.1f}s | Analizado en {video_analysis_duration}s')
            else:
                analysis_state['video_results'][video_name] = {
                    'success': False,
                    'error': result.get('error', 'Error desconocido'),
                    'analysis_duration': video_analysis_duration
                }
                analysis_state['log'].append(f'  ❌ {result.get("error", "Error")}')
        
        # Thumbnails se generan on-demand (lazy loading) para acelerar el análisis

        analysis_state['log'].append('Generando reportes...')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Agregar stats de todos los videos
        successful_results = [r for r in results if r['success']]
        
        # Contar tipos de toma
        all_shot_types = {}
        total_segments = 0
        for r in successful_results:
            for seg in r.get('segments', []):
                shot_type = seg.get('shot_type', 'unknown')
                all_shot_types[shot_type] = all_shot_types.get(shot_type, 0) + 1
                total_segments += 1
        
        stats = {
            'total_videos': len(successful_results),
            'total_duration': sum(r.get('duration', 0) for r in successful_results),
            'gold_duration': sum(r.get('tier_durations', {}).get('gold', 0) for r in successful_results),
            'silver_duration': sum(r.get('tier_durations', {}).get('silver', 0) for r in successful_results),
            'bronze_duration': sum(r.get('tier_durations', {}).get('bronze', 0) for r in successful_results),
            'discard_duration': sum(r.get('tier_durations', {}).get('discard', 0) for r in successful_results),
            'segment_count': total_segments,
            'shot_types': all_shot_types,
        }
        
        # Calcular porcentajes
        total = stats['gold_duration'] + stats['silver_duration'] + stats['bronze_duration'] + stats['discard_duration']
        stats['gold_pct'] = (stats['gold_duration'] / total * 100) if total > 0 else 0
        stats['silver_pct'] = (stats['silver_duration'] / total * 100) if total > 0 else 0
        stats['bronze_pct'] = (stats['bronze_duration'] / total * 100) if total > 0 else 0
        stats['discard_pct'] = (stats['discard_duration'] / total * 100) if total > 0 else 0
        stats['usable_pct'] = stats['gold_pct'] + stats['silver_pct']
        
        # Para compatibilidad
        stats['total_gold'] = stats['gold_duration']
        stats['total_silver'] = stats['silver_duration']
        stats['total_bronze'] = stats['bronze_duration']
        stats['total_discard'] = stats['discard_duration']
        
        # JSON con datos completos incluyendo segmentos
        analysis_id = f'analisis_completo_{timestamp}'
        json_path = OUTPUT_FOLDER / f'{analysis_id}.json'
        json_data = {
            'timestamp': timestamp,
            'version': '6.0-web',
            'config': config,
            'stats': stats,
            'project_id': project_id,
            'analyses': successful_results
        }
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)

        # Asociar al proyecto si se especificó
        if project_id:
            add_analysis_to_project(project_id, analysis_id, stats)
            analysis_state['log'].append(f'Agregado al proyecto')

        # HTML con reporte detallado
        html_path = OUTPUT_FOLDER / f'analisis_completo_{timestamp}.html'
        generate_detailed_report(successful_results, stats, config, html_path)

        # XML para Premiere
        xml_path = OUTPUT_FOLDER / f'premiere_export_{timestamp}.xml'
        generate_premiere_xml(successful_results, xml_path)
        analysis_state['log'].append(f'XML Premiere: {xml_path.name}')

        analysis_state['results'] = stats
        analysis_state['xml_file'] = xml_path.name
        analysis_state['analysis_id'] = analysis_id
        analysis_state['log'].append('✅ Análisis completado!')
        analysis_state['log'].append(f'📊 Reporte: {html_path.name}')

        # Limpiar videos procesados de la carpeta de uploads
        # Esto evita que aparezcan como "pendientes" después de analizar
        cleaned = 0
        for video_name in analysis_state.get('completed_videos', []):
            video_path = UPLOAD_FOLDER / video_name
            if video_path.exists():
                try:
                    video_path.unlink()
                    # También limpiar del cache de metadata
                    if video_name in video_metadata_cache:
                        del video_metadata_cache[video_name]
                    cleaned += 1
                except Exception as e:
                    print(f"Error removing {video_name}: {e}")

        if cleaned > 0:
            analysis_state['log'].append(f'🗑️ {cleaned} videos limpiados de pendientes')

    except Exception as e:
        analysis_state['log'].append(f'❌ Error: {str(e)}')

    finally:
        analysis_state['running'] = False


def generate_premiere_xml(results, output_path):
    """
    Genera XML compatible con Premiere Pro (FCP7 XML)
    4 tracks con clips en su posición temporal original:
    - V4: GOLD
    - V3: SILVER
    - V2: BRONZE
    - V1: DISCARD
    """
    
    if not results:
        return
    
    # Detectar resolución del primer video
    first_result = results[0]
    seq_width = first_result.get('width', 3840)
    seq_height = first_result.get('height', 2160)
    
    fps = 30
    timebase = 30
    
    def frames(seconds):
        return int(seconds * fps)
    
    # Recolectar clips por tier con su posición original
    gold_clips = []
    silver_clips = []
    bronze_clips = []
    discard_clips = []
    
    file_registry = {}
    total_duration = 0
    
    for r in results:
        filename = r.get('filename', 'unknown')
        filepath = r.get('path', str(UPLOAD_FOLDER / filename))
        duration = r.get('duration', 0)
        width = r.get('width', seq_width)
        height = r.get('height', seq_height)
        ranges = r.get('ranges', {})
        timeline_offset = r.get('timeline_offset', 0)
        
        file_id = filename.replace('.', '_').replace(' ', '_').replace('-', '_')
        
        if file_id not in file_registry:
            file_registry[file_id] = {
                'filename': filename,
                'filepath': filepath,
                'duration': duration,
                'width': width,
                'height': height
            }
        
        # GOLD clips - posición original + offset del timeline
        for rng in ranges.get('gold', []):
            gold_clips.append({
                'file_id': file_id,
                'filename': filename,
                'in_point': rng['start'],      # Punto de entrada en el video original
                'out_point': rng['end'],       # Punto de salida en el video original
                'timeline_start': timeline_offset + rng['start'],  # Posición en el timeline
                'duration': rng['end'] - rng['start']
            })
        
        # SILVER clips
        for rng in ranges.get('silver', []):
            silver_clips.append({
                'file_id': file_id,
                'filename': filename,
                'in_point': rng['start'],
                'out_point': rng['end'],
                'timeline_start': timeline_offset + rng['start'],
                'duration': rng['end'] - rng['start']
            })
        
        # BRONZE clips
        for rng in ranges.get('bronze', []):
            bronze_clips.append({
                'file_id': file_id,
                'filename': filename,
                'in_point': rng['start'],
                'out_point': rng['end'],
                'timeline_start': timeline_offset + rng['start'],
                'duration': rng['end'] - rng['start']
            })
        
        # DISCARD clips
        for rng in ranges.get('discard', []):
            discard_clips.append({
                'file_id': file_id,
                'filename': filename,
                'in_point': rng['start'],
                'out_point': rng['end'],
                'timeline_start': timeline_offset + rng['start'],
                'duration': rng['end'] - rng['start']
            })
        
        total_duration = max(total_duration, timeline_offset + duration)
    
    # Construir XML
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence id="sequence-1">
    <n>Video Analysis Export</n>
    <duration>{frames(total_duration)}</duration>
    <rate>
      <timebase>{timebase}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <timecode>
      <rate>
        <timebase>{timebase}</timebase>
        <ntsc>FALSE</ntsc>
      </rate>
      <string>00:00:00:00</string>
      <frame>0</frame>
      <displayformat>NDF</displayformat>
    </timecode>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <width>{seq_width}</width>
            <height>{seq_height}</height>
            <pixelaspectratio>square</pixelaspectratio>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
          </samplecharacteristics>
        </format>
'''
    
    clip_id = 1
    defined_files = set()
    
    def generate_track(clips, label_name, label_color):
        nonlocal clip_id, defined_files
        
        track_xml = '''        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
'''
        
        for clip in sorted(clips, key=lambda x: x['timeline_start']):
            file_id = clip['file_id']
            file_info = file_registry[file_id]
            
            if file_id not in defined_files:
                defined_files.add(file_id)
                file_xml = f'''
              <file id="file-{file_id}">
                <n>{file_info['filename']}</n>
                <pathurl>file://{file_info['filepath']}</pathurl>
                <rate>
                  <timebase>{timebase}</timebase>
                  <ntsc>FALSE</ntsc>
                </rate>
                <duration>{frames(file_info['duration'])}</duration>
                <media>
                  <video>
                    <samplecharacteristics>
                      <width>{file_info['width']}</width>
                      <height>{file_info['height']}</height>
                    </samplecharacteristics>
                  </video>
                </media>
              </file>'''
            else:
                file_xml = f'''
              <file id="file-{file_id}"/>'''
            
            short_name = clip['filename'][:20]
            track_xml += f'''          <clipitem id="clipitem-{clip_id}">
            <n>{short_name} {label_name}</n>
            <duration>{frames(clip['duration'])}</duration>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <start>{frames(clip['timeline_start'])}</start>
            <end>{frames(clip['timeline_start'] + clip['duration'])}</end>
            <in>{frames(clip['in_point'])}</in>
            <out>{frames(clip['out_point'])}</out>{file_xml}
            <labels>
              <label2>{label_color}</label2>
            </labels>
          </clipitem>
'''
            clip_id += 1
        
        track_xml += '''        </track>
'''
        return track_xml
    
    # V4 - GOLD (arriba)
    xml += generate_track(gold_clips, 'GOLD', 'Forest')
    
    # V3 - SILVER
    xml += generate_track(silver_clips, 'SILVER', 'Iris')
    
    # V2 - BRONZE
    xml += generate_track(bronze_clips, 'BRONZE', 'Mango')
    
    # V1 - DISCARD (abajo)
    xml += generate_track(discard_clips, 'DISCARD', 'Rose')
    
    xml += '''      </video>
    </media>
  </sequence>
</xmeml>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)


def path_to_file_url(filepath):
    """Convierte una ruta de archivo a formato file:// URL para Premiere Pro en macOS."""
    from urllib.parse import quote
    # Asegurar que es una ruta absoluta
    path = str(filepath)
    if not path.startswith('/'):
        path = '/' + path
    # Codificar caracteres especiales pero mantener las barras
    encoded_path = quote(path, safe='/:')
    # Formato correcto para macOS: file://localhost/path
    return f'file://localhost{encoded_path}'


# ============================================================================
# FUNCIONES HELPER PARA CAPA DE TEXTO
# ============================================================================

def get_movement_level(px):
    """Traduce píxeles de movimiento a nivel legible"""
    if px < 0.5:
        return "Mínimo", px
    elif px < 2.0:
        return "Bajo", px
    elif px < 5.0:
        return "Medio", px
    elif px < 10.0:
        return "Alto", px
    else:
        return "Muy alto", px


def get_vibration_level(tremor_pct):
    """Traduce porcentaje de temblor a nivel legible"""
    if tremor_pct < 5:
        return "Ninguna", tremor_pct
    elif tremor_pct < 15:
        return "Leve", tremor_pct
    elif tremor_pct < 40:
        return "Moderada", tremor_pct
    else:
        return "Fuerte", tremor_pct


def get_focus_status(sharpness, blurry_pct):
    """Retorna estado de enfoque con ícono"""
    if sharpness >= 100:
        icon = "✓"
    elif sharpness >= 50:
        icon = "⚠"
    else:
        icon = "✗"
    return sharpness, icon, blurry_pct


def get_exposure_status(brightness, brightness_std):
    """Retorna estado de exposición"""
    # Determinar si es estable o variable
    stability = "estable" if brightness_std < 0.05 else f"±{brightness_std*100:.0f}%"

    # Determinar nivel de exposición
    if brightness < 0.2:
        level = "muy oscuro"
    elif brightness < 0.35:
        level = "subexp."
    elif brightness < 0.65:
        level = ""  # Normal, no necesita etiqueta
    elif brightness < 0.8:
        level = "sobreexp."
    else:
        level = "muy claro"

    return brightness * 100, level, stability


def get_framing_position(h_balance, v_balance):
    """Traduce balance H/V a posición de encuadre"""
    h_pct = h_balance * 100 if h_balance else 50
    v_pct = v_balance * 100 if v_balance else 50

    # Determinar posición
    h_diff = abs(h_pct - 50)
    v_diff = abs(v_pct - 50)

    if h_diff < 8 and v_diff < 8:
        position = "Centrado"
    elif h_diff > v_diff:
        position = "Cargado izq." if h_pct > 50 else "Cargado der."
    else:
        position = "Cargado arriba" if v_pct > 50 else "Cargado abajo"

    return position, int(h_pct), int(v_pct)


def get_action_text(tier):
    """Retorna texto de acción según tier"""
    actions = {
        'gold': ("✓", "Usar directamente"),
        'silver': ("⚠", "Revisar/Estabilizar"),
        'bronze': ("⚠", "Requiere corrección"),
        'discard': ("✗", "No usar"),
    }
    return actions.get(tier, ("?", "Revisar"))


def generate_clip_text_info(clip):
    """Genera las 4 líneas de texto informativo para un clip"""
    metrics = clip.get('metrics', {})
    score = clip.get('score', 0)
    tier = clip.get('tier', 'discard').upper()
    shot_type = clip.get('shot_type', 'DESCONOCIDO')

    # Extraer métricas
    motion_px = metrics.get('motion_mean', 0)
    tremor_pct = metrics.get('tremor_power', 0) * 100
    sharpness = metrics.get('sharpness_mean', 0)
    blurry_pct = metrics.get('blurry_frame_pct', 0)
    brightness = metrics.get('brightness_mean', 0.5)
    brightness_std = metrics.get('brightness_std', 0)
    h_balance = metrics.get('h_balance', 0.5)
    v_balance = metrics.get('v_balance', 0.5)

    # Línea 1: Clasificación
    line1 = f"{tier} {score:.1f} · {shot_type}"

    # Línea 2: Movimiento y Vibración
    mov_level, mov_px = get_movement_level(motion_px)
    vib_level, vib_pct = get_vibration_level(tremor_pct)
    line2 = f"Movimiento: {mov_level} ({mov_px:.1f}px) · Vibración: {vib_level} ({vib_pct:.0f}%)"

    # Línea 3: Enfoque y Exposición
    sharp_val, sharp_icon, blur_pct = get_focus_status(sharpness, blurry_pct)
    exp_val, exp_level, exp_stability = get_exposure_status(brightness, brightness_std)
    exp_text = f"{exp_val:.0f}% {exp_level} ({exp_stability})".replace("  ", " ").strip()
    line3 = f"Enfoque: {sharp_val:.0f} {sharp_icon} ({blur_pct:.0f}% borrosos) · Exposición: {exp_text}"

    # Línea 4: Encuadre y Acción
    frame_pos, h_pct, v_pct = get_framing_position(h_balance, v_balance)
    action_icon, action_text = get_action_text(clip.get('tier', 'discard'))
    line4 = f"Encuadre: {frame_pos} ({h_pct}/{v_pct}) · {action_icon} {action_text}"

    return [line1, line2, line3, line4]


def consolidate_segments(clips):
    """
    Consolida segmentos consecutivos del mismo archivo y tier en un solo clip.
    Esto evita tener micro-segmentos de 0.4s y los combina en clips más largos.
    """
    if not clips:
        return []

    # Ordenar por archivo y tiempo
    sorted_clips = sorted(clips, key=lambda x: (x.get('filename', ''), x.get('start_time', 0)))

    consolidated = []
    current = None

    for clip in sorted_clips:
        if current is None:
            current = dict(clip)
        elif (clip.get('filename') == current.get('filename') and
              clip.get('tier') == current.get('tier') and
              abs(clip.get('start_time', 0) - current.get('end_time', 0)) < 0.1):  # Consecutivos (tolerancia 0.1s)
            # Extender el clip actual
            current['end_time'] = clip.get('end_time', 0)
        else:
            # Guardar el actual y empezar uno nuevo
            consolidated.append(current)
            current = dict(clip)

    # No olvidar el último
    if current:
        consolidated.append(current)

    return consolidated


def generate_premiere_xml_from_clips(clips, output_path, options):
    """
    Genera XML compatible con Premiere Pro directamente desde clips del frontend.

    clips: Lista de clips con formato:
        {filename, path, start_time, end_time, tier, shot_type, duration}

    options:
        - handles: segundos a agregar antes/después de cada clip
        - organization: 'sequence' | 'tracks' | 'original'
        - sort_by: 'time' | 'quality' | 'shot_type'
        - media_folder: carpeta donde están los archivos originales
    """
    if not clips:
        return

    handles = options.get('handles', 0)
    organization = options.get('organization', 'sequence')
    sort_by = options.get('sort_by', 'time')
    media_folder = options.get('media_folder', '').rstrip('/')

    # PASO 1: Consolidar segmentos consecutivos del mismo tier
    print(f"[XML] Input clips: {len(clips)}")
    consolidated_clips = consolidate_segments(clips)
    print(f"[XML] After consolidation: {len(consolidated_clips)} clips")
    print(f"[XML] Organization: {organization}, Sort by: {sort_by}, Handles: {handles}")

    # HOTFIX V5.1: Detectar FPS de los clips o usar metadata
    fps = _detect_clips_fps(clips)
    timebase = int(fps) if fps == int(fps) else fps
    
    print(f"[XML] Using FPS: {fps}, timebase: {timebase}")

    def frames(seconds):
        return int(seconds * fps)

    # Configuración de secuencia (usar valores por defecto)
    seq_width = 3840
    seq_height = 2160

    # Procesar clips consolidados y crear registro de archivos
    all_clips = []
    file_registry = {}

    for clip in consolidated_clips:
        filename = clip.get('filename', 'unknown')
        source_duration = clip.get('duration', 0)

        # Crear file_id único
        file_id = filename.replace('.', '_').replace(' ', '_').replace('-', '_')

        # Registrar archivo si no existe
        if file_id not in file_registry:
            if media_folder:
                filepath = f"{media_folder}/{filename}"
            else:
                filepath = clip.get('path', str(UPLOAD_FOLDER / filename))

            file_registry[file_id] = {
                'filename': filename,
                'filepath': filepath,
                'duration': source_duration,
                'width': seq_width,
                'height': seq_height
            }

        # Aplicar handles
        in_point = max(0, clip['start_time'] - handles)
        out_point = min(source_duration, clip['end_time'] + handles) if source_duration > 0 else clip['end_time'] + handles

        all_clips.append({
            'file_id': file_id,
            'filename': filename,
            'in_point': in_point,
            'out_point': out_point,
            'original_start': clip['start_time'],
            'original_end': clip['end_time'],
            'clip_duration': out_point - in_point,
            'shot_type': clip.get('shot_type', ''),
            'tier': clip.get('tier', 'discard'),
            'score': 0
        })

    if not all_clips:
        return

    # Ordenar clips según sort_by
    tier_order = {'gold': 0, 'silver': 1, 'bronze': 2, 'discard': 3}

    if sort_by == 'quality':
        all_clips.sort(key=lambda x: (tier_order.get(x['tier'], 99), x['filename'], x['original_start']))
    elif sort_by == 'shot_type':
        all_clips.sort(key=lambda x: (x['shot_type'], x['filename'], x['original_start']))
    else:  # time (default)
        all_clips.sort(key=lambda x: (x['filename'], x['original_start']))

    clips_info = [(c['filename'], c['tier'], f"{c['original_start']:.1f}-{c['original_end']:.1f}") for c in all_clips]
    print(f"[XML] Clips to export: {clips_info}")

    # Calcular posiciones en timeline según organization
    if organization == 'sequence':
        # Todos los clips en UN solo track, secuencialmente
        timeline_pos = 0
        for clip in all_clips:
            clip['timeline_start'] = timeline_pos
            clip['timeline_end'] = timeline_pos + clip['clip_duration']
            timeline_pos = clip['timeline_end']
        total_duration = timeline_pos

        # Un solo track con todos los clips
        tracks_data = [{'name': 'All Clips', 'clips': all_clips}]
        print(f"[XML] SEQUENCE mode: 1 track, {len(all_clips)} clips, total duration: {total_duration:.2f}s")

    elif organization == 'by_tier':
        # MULTITRACK: Cada tier en su propio track
        # Clips en SECUENCIA dentro de cada track (sin huecos)

        # Paso 1: Agrupar clips por tier
        clips_by_tier = {}
        for clip in all_clips:
            tier = clip['tier']
            if tier not in clips_by_tier:
                clips_by_tier[tier] = []
            clips_by_tier[tier].append(clip)

        # Paso 2: Ordenar clips dentro de cada tier por archivo y tiempo original
        for tier in clips_by_tier:
            clips_by_tier[tier].sort(key=lambda c: (c['filename'], c['original_start']))

        # Paso 3: Asignar posiciones SECUENCIALES dentro de cada track
        tracks_data = []
        max_duration = 0

        for tier in ['gold', 'silver', 'bronze', 'discard']:
            if tier in clips_by_tier:
                tier_clips = clips_by_tier[tier]
                timeline_pos = 0
                for clip in tier_clips:
                    clip['timeline_start'] = timeline_pos
                    clip['timeline_end'] = timeline_pos + clip['clip_duration']
                    timeline_pos = clip['timeline_end']

                max_duration = max(max_duration, timeline_pos)

                tracks_data.append({
                    'name': tier.upper(),
                    'tier': tier,
                    'clips': tier_clips
                })

        total_duration = max_duration
        print(f"[XML] BY_TIER mode (multitrack): {len(tracks_data)} tracks, max duration: {total_duration:.2f}s")

    elif organization == 'tracks':
        # Legacy mode: Cada tier en su propio track, TODOS secuenciales en el timeline
        # Gold primero, luego Silver, etc. - cada track continúa donde termina el anterior
        clips_by_tier = {}
        for clip in all_clips:
            tier = clip['tier']
            if tier not in clips_by_tier:
                clips_by_tier[tier] = []
            clips_by_tier[tier].append(clip)

        # Calcular posiciones secuenciales GLOBALES (no por track)
        timeline_pos = 0
        tracks_data = []

        for tier in ['gold', 'silver', 'bronze', 'discard']:
            if tier in clips_by_tier:
                tier_clips = clips_by_tier[tier]
                for clip in tier_clips:
                    clip['timeline_start'] = timeline_pos
                    clip['timeline_end'] = timeline_pos + clip['clip_duration']
                    timeline_pos = clip['timeline_end']

                tracks_data.append({
                    'name': tier.upper(),
                    'tier': tier,
                    'clips': tier_clips
                })

        total_duration = timeline_pos
        print(f"[XML] TRACKS mode: {len(tracks_data)} tracks, total duration: {total_duration:.2f}s")

    else:  # original
        # Mantener posición original en timeline
        clips_by_tier = {}
        max_duration = 0
        for clip in all_clips:
            tier = clip['tier']
            if tier not in clips_by_tier:
                clips_by_tier[tier] = []
            clip['timeline_start'] = clip['original_start']
            clip['timeline_end'] = clip['original_end']
            clips_by_tier[tier].append(clip)
            max_duration = max(max_duration, clip['original_end'])

        total_duration = max_duration

        tracks_data = []
        for tier in ['gold', 'silver', 'bronze', 'discard']:
            if tier in clips_by_tier:
                tracks_data.append({
                    'name': tier.upper(),
                    'tier': tier,
                    'clips': sorted(clips_by_tier[tier], key=lambda x: x['timeline_start'])
                })
        print(f"[XML] ORIGINAL mode: {len(tracks_data)} tracks, preserving positions")

    tier_colors = {'gold': 'Forest', 'silver': 'Iris', 'bronze': 'Mango', 'discard': 'Rose'}

    # Track de archivos ya definidos (para no duplicar en XML)
    defined_files = set()

    # Generar XML
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence id="sequence-1">
    <name>Video Analysis Export</name>
    <duration>{frames(total_duration)}</duration>
    <rate>
      <timebase>{timebase}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <timecode>
      <rate>
        <timebase>{timebase}</timebase>
        <ntsc>FALSE</ntsc>
      </rate>
      <string>00:00:00:00</string>
      <frame>0</frame>
      <displayformat>NDF</displayformat>
    </timecode>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <width>{seq_width}</width>
            <height>{seq_height}</height>
            <pixelaspectratio>square</pixelaspectratio>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
          </samplecharacteristics>
        </format>
'''

    # Generar tracks de video
    for track_idx, track in enumerate(tracks_data):
        track_name = track['name']
        track_clips = track['clips']
        track_tier = track.get('tier', 'gold')

        xml += f'''        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
'''

        for clip_idx, clip in enumerate(track_clips):
            file_id = clip['file_id']
            file_info = file_registry[file_id]
            filepath = file_info['filepath']
            file_url = path_to_file_url(filepath)
            source_duration = file_info['duration']

            clip_id = f"clip-{track_idx}-{clip_idx}"
            clip_name = f"{clip['filename']} [{clip['tier'].upper()}]"
            tier_color = tier_colors.get(clip['tier'], 'Iris')

            # Primera vez: definición completa del archivo
            # Siguientes veces: solo referencia
            if file_id not in defined_files:
                defined_files.add(file_id)
                file_xml = f'''
            <file id="{file_id}">
              <name>{file_info['filename']}</name>
              <pathurl>{file_url}</pathurl>
              <duration>{frames(source_duration) if source_duration > 0 else frames(clip['out_point'])}</duration>
              <rate>
                <timebase>{timebase}</timebase>
                <ntsc>FALSE</ntsc>
              </rate>
              <media>
                <video>
                  <duration>{frames(source_duration) if source_duration > 0 else frames(clip['out_point'])}</duration>
                  <samplecharacteristics>
                    <width>{file_info['width']}</width>
                    <height>{file_info['height']}</height>
                  </samplecharacteristics>
                </video>
              </media>
            </file>'''
            else:
                file_xml = f'''
            <file id="{file_id}"/>'''

            xml += f'''          <clipitem id="{clip_id}">
            <name>{clip_name}</name>
            <duration>{frames(source_duration) if source_duration > 0 else frames(clip['out_point'])}</duration>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <start>{frames(clip['timeline_start'])}</start>
            <end>{frames(clip['timeline_end'])}</end>
            <in>{frames(clip['in_point'])}</in>
            <out>{frames(clip['out_point'])}</out>{file_xml}
            <labels>
              <label2>{tier_color}</label2>
            </labels>
          </clipitem>
'''

        xml += '''        </track>
'''

    # =========================================================================
    # MARCADORES con info técnica (compatible con Premiere Pro)
    # =========================================================================
    all_clips_for_markers = []
    for track in tracks_data:
        all_clips_for_markers.extend(track['clips'])
    all_clips_for_markers.sort(key=lambda c: c['timeline_start'])

    markers_xml = ''
    for clip in all_clips_for_markers:
        text_lines = generate_clip_text_info(clip)
        marker_comment = " | ".join(text_lines)
        # Escapar caracteres XML
        marker_comment = marker_comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        marker_name = f"{clip.get('tier', 'clip').upper()} - {clip.get('shot_type', '')}"

        markers_xml += f'''    <marker>
      <comment>{marker_comment}</comment>
      <name>{marker_name}</name>
      <in>{frames(clip['timeline_start'])}</in>
      <out>{frames(clip['timeline_end'])}</out>
    </marker>
'''

    xml += '''      </video>
      <audio>
        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
        </track>
      </audio>
    </media>
'''
    xml += markers_xml
    xml += '''  </sequence>
</xmeml>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"[XML] Saved to {output_path} (with markers)")


def generate_premiere_xml_advanced(results, output_path, options):
    """
    Genera XML compatible con Premiere Pro (FCP7 XML format).
    (Función legacy - ahora se usa generate_premiere_xml_from_clips)

    Opciones:
    - tiers: lista de tiers a incluir ['gold', 'silver', 'bronze', 'discard']
    - handles: segundos a agregar antes/después de cada clip
    - organization: 'sequence' | 'tracks' | 'original'
    - sort_by: 'time' | 'quality' | 'shot_type'
    """
    if not results:
        return

    tiers_to_include = options.get('tiers', ['gold', 'silver', 'bronze'])
    handles = options.get('handles', 0)
    min_duration = options.get('min_duration', 0)
    shot_types_filter = options.get('shot_types')
    organization = options.get('organization', 'sequence')
    sort_by = options.get('sort_by', 'time')
    media_folder = options.get('media_folder', '').rstrip('/')

    first_result = results[0]
    seq_width = first_result.get('width', 3840)
    seq_height = first_result.get('height', 2160)
    fps = 30
    timebase = 30

    def frames(seconds):
        return int(seconds * fps)

    # Recolectar todos los clips
    all_clips = []
    file_registry = {}
    max_source_duration = 0

    for r in results:
        filename = r.get('filename', 'unknown')
        # Usar media_folder si está especificado, sino la ruta original
        if media_folder:
            filepath = f"{media_folder}/{filename}"
        else:
            filepath = r.get('path', str(UPLOAD_FOLDER / filename))
        duration = r.get('duration', 0)
        width = r.get('width', seq_width)
        height = r.get('height', seq_height)
        segments = r.get('segments', [])

        file_id = filename.replace('.', '_').replace(' ', '_').replace('-', '_')

        if file_id not in file_registry:
            file_registry[file_id] = {
                'filename': filename,
                'filepath': filepath,
                'duration': duration,
                'width': width,
                'height': height
            }

        for seg in segments:
            tier = seg.get('tier', 'discard')
            seg_duration = seg.get('duration', 0)
            shot_type = seg.get('shot_type', '')

            # Aplicar filtros
            if tier not in tiers_to_include:
                continue
            if seg_duration < min_duration:
                continue
            if shot_types_filter and shot_type not in shot_types_filter:
                continue

            # Aplicar handles
            in_point = max(0, seg['start_time'] - handles)
            out_point = min(duration, seg['end_time'] + handles)

            all_clips.append({
                'file_id': file_id,
                'filename': filename,
                'in_point': in_point,
                'out_point': out_point,
                'original_start': seg['start_time'],
                'original_end': seg['end_time'],
                'clip_duration': out_point - in_point,
                'shot_type': shot_type,
                'tier': tier,
                'score': seg.get('score', 0)
            })

        max_source_duration = max(max_source_duration, duration)

    if not all_clips:
        return

    # Ordenar clips según sort_by
    tier_order = {'gold': 0, 'silver': 1, 'bronze': 2, 'discard': 3}

    if sort_by == 'quality':
        all_clips.sort(key=lambda x: (tier_order.get(x['tier'], 99), x['original_start']))
    elif sort_by == 'shot_type':
        all_clips.sort(key=lambda x: (x['shot_type'], x['original_start']))
    else:  # time (default)
        all_clips.sort(key=lambda x: x['original_start'])

    # Calcular posiciones en timeline según organization
    if organization == 'sequence':
        # Todos los clips en secuencia, uno tras otro
        timeline_pos = 0
        for clip in all_clips:
            clip['timeline_start'] = timeline_pos
            clip['timeline_end'] = timeline_pos + clip['clip_duration']
            timeline_pos = clip['timeline_end']
        total_duration = timeline_pos

        # Todos en un solo track
        tracks_data = [{'name': 'All Clips', 'clips': all_clips}]

    elif organization == 'tracks':
        # Cada tier en su propio track, pero secuencial dentro de cada track
        clips_by_tier = {}
        for clip in all_clips:
            tier = clip['tier']
            if tier not in clips_by_tier:
                clips_by_tier[tier] = []
            clips_by_tier[tier].append(clip)

        # Calcular posiciones secuenciales por track
        total_duration = 0
        for tier in tiers_to_include:
            if tier in clips_by_tier:
                timeline_pos = 0
                for clip in clips_by_tier[tier]:
                    clip['timeline_start'] = timeline_pos
                    clip['timeline_end'] = timeline_pos + clip['clip_duration']
                    timeline_pos = clip['timeline_end']
                total_duration = max(total_duration, timeline_pos)

        # Crear tracks en orden: gold arriba, discard abajo
        tracks_data = []
        for tier in ['gold', 'silver', 'bronze', 'discard']:
            if tier in clips_by_tier and tier in tiers_to_include:
                tracks_data.append({
                    'name': tier.upper(),
                    'tier': tier,
                    'clips': clips_by_tier[tier]
                })

    else:  # original
        # Mantener posición original, cada tier en su track
        clips_by_tier = {}
        for clip in all_clips:
            tier = clip['tier']
            if tier not in clips_by_tier:
                clips_by_tier[tier] = []
            clip['timeline_start'] = clip['original_start']
            clip['timeline_end'] = clip['original_end']
            clips_by_tier[tier].append(clip)

        total_duration = max_source_duration

        # Crear tracks
        tracks_data = []
        for tier in ['gold', 'silver', 'bronze', 'discard']:
            if tier in clips_by_tier and tier in tiers_to_include:
                tracks_data.append({
                    'name': tier.upper(),
                    'tier': tier,
                    'clips': sorted(clips_by_tier[tier], key=lambda x: x['timeline_start'])
                })

    tier_colors = {'gold': 'Forest', 'silver': 'Iris', 'bronze': 'Mango', 'discard': 'Rose'}
    tier_names = {'gold': 'GOLD', 'silver': 'SILVER', 'bronze': 'BRONZE', 'discard': 'DISCARD'}

    # Generar XML
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence id="sequence-1">
    <name>Video Analysis Export</name>
    <duration>{frames(total_duration)}</duration>
    <rate>
      <timebase>{timebase}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <timecode>
      <rate>
        <timebase>{timebase}</timebase>
        <ntsc>FALSE</ntsc>
      </rate>
      <string>00:00:00:00</string>
      <frame>0</frame>
      <displayformat>NDF</displayformat>
    </timecode>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <width>{seq_width}</width>
            <height>{seq_height}</height>
            <pixelaspectratio>square</pixelaspectratio>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
          </samplecharacteristics>
        </format>
'''

    clip_id = 1
    defined_files = set()

    # Generar tracks
    for track_data in tracks_data:
        clips = track_data['clips']
        track_tier = track_data.get('tier', 'gold')

        if not clips:
            continue

        xml += '''        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
'''
        for clip in clips:
            file_id = clip['file_id']
            file_info = file_registry[file_id]
            clip_tier = clip.get('tier', track_tier)

            # Definir archivo completo la primera vez
            if file_id not in defined_files:
                defined_files.add(file_id)
                file_url = path_to_file_url(file_info['filepath'])
                file_xml = f'''
            <file id="file-{file_id}">
              <name>{file_info['filename']}</name>
              <pathurl>{file_url}</pathurl>
              <rate>
                <timebase>{timebase}</timebase>
                <ntsc>FALSE</ntsc>
              </rate>
              <duration>{frames(file_info['duration'])}</duration>
              <media>
                <video>
                  <samplecharacteristics>
                    <width>{file_info['width']}</width>
                    <height>{file_info['height']}</height>
                  </samplecharacteristics>
                </video>
              </media>
            </file>'''
            else:
                file_xml = f'''
            <file id="file-{file_id}"/>'''

            xml += f'''          <clipitem id="clipitem-{clip_id}">
            <name>{clip['filename'][:25]} {tier_names.get(clip_tier, '')}</name>
            <duration>{frames(clip['clip_duration'])}</duration>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <start>{frames(clip['timeline_start'])}</start>
            <end>{frames(clip['timeline_end'])}</end>
            <in>{frames(clip['in_point'])}</in>
            <out>{frames(clip['out_point'])}</out>{file_xml}
            <labels>
              <label2>{tier_colors.get(clip_tier, 'Iris')}</label2>
            </labels>
          </clipitem>
'''
            clip_id += 1

        xml += '''        </track>
'''

    xml += '''      </video>
    </media>
  </sequence>
</xmeml>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)


if __name__ == '__main__':
    import os

    # Puerto configurable (5050 para Electron, 5000 para desarrollo web)
    port = int(os.environ.get('FLASK_PORT', 5050))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'

    print("="*60)
    print("   VIDEO ANALYZER PRO")
    print("="*60)
    print()
    print(f"   Servidor iniciado en puerto {port}")
    print()
    print("="*60)
    app.run(debug=debug, host='127.0.0.1', port=port, threaded=True)
