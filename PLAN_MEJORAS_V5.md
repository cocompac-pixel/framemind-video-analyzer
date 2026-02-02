# Plan de Implementación - Video Analyzer V5

## Resumen Ejecutivo

Este plan transforma el analizador de un "calificador de calidad técnica" a un **asistente de primer pase inteligente** que piensa como un editor.

---

## Arquitectura Propuesta

```
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 1: FILTRADO DE BASURA                   │
│  Detectar y marcar automáticamente contenido no usable          │
│  - Tapa de lente / negro total                                  │
│  - Tomas accidentales (piso/cielo uniforme)                     │
│  - Pre-roll / Post-roll                                         │
│  - Flashes de exposición                                        │
│  - Tomas cortadas abruptamente                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 2: CLASIFICACIÓN DE PLANOS              │
│  Identificar tipo de encuadre                                   │
│  - Plano general / Establecimiento                              │
│  - Plano medio                                                  │
│  - Close-up                                                     │
│  - Extreme close-up / Detalle                                   │
│  - POV / Subjetiva                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 3: DETECCIÓN DE ROSTROS                 │
│  Análisis de personas en frame                                  │
│  - Cantidad de rostros                                          │
│  - Rostros en foco vs fuera de foco                             │
│  - Ojos abiertos/cerrados                                       │
│  - Encuadre de rostro (headroom)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 4: AGRUPACIÓN POR SETUP                 │
│  Clustering visual para detectar cambios de escena              │
│  - Histograma de color dominante                                │
│  - Distribución de elementos                                    │
│  - Tipo de plano + paleta = setup_id                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 5: DETECCIÓN DE TAKES                   │
│  Encontrar tomas repetidas del mismo momento                    │
│  - Comparar composición entre segmentos cercanos                │
│  - Agrupar takes similares                                      │
│  - Sugerir mejor take técnicamente                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 6: ETIQUETADO CONTEXTUAL                │
│  Reemplazar tiers absolutos con etiquetas descriptivas          │
│  - "shaky-pero-en-foco"                                         │
│  - "subexpuesta-recuperable"                                    │
│  - "soft-focus-intencional"                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 7: BÚSQUEDA TRANSVERSAL                 │
│  Consultas a través de todo el proyecto                         │
│  - "Mejores close-ups del proyecto"                             │
│  - "Todos los planos generales"                                 │
│  - "Tomas con rostros en foco"                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## FASE 1: Detección de Basura (Garbage Detection)

### 1.1 Nuevos Detectores a Implementar

#### A. Detector de Tapa/Negro (`detect_lens_cap`)
```python
def detect_lens_cap(frame):
    """
    Detecta frames completamente negros o uniformes.

    Método:
    - Calcular varianza del frame completo
    - Si varianza < 5 → probablemente tapa de lente
    - Si brightness_mean < 0.02 → negro total

    Returns:
        "lens_cap" | "black_frame" | "uniform" | None
    """
```

#### B. Detector de Tomas Accidentales (`detect_accidental_shot`)
```python
def detect_accidental_shot(frame):
    """
    Detecta cuando la cámara quedó grabando piso/cielo/nada.

    Método:
    - Analizar distribución de edges (Canny)
    - Si edge_density < threshold Y color uniforme → accidental
    - Detectar cielo: high brightness + low saturation en parte superior
    - Detectar piso: low brightness + textura repetitiva

    Returns:
        "sky_shot" | "ground_shot" | "accidental" | None
    """
```

#### C. Detector de Pre/Post Roll (`detect_dead_air`)
```python
def detect_dead_air(segment_metrics, position_in_video):
    """
    Detecta segundos muertos antes de acción o después de corte.

    Método:
    - Primeros/últimos N segundos del video
    - Sin movimiento significativo
    - Sin cambios de exposición
    - Puede tener audio ambiente pero visualmente "nada pasa"

    Returns:
        "pre_roll" | "post_roll" | None
    """
```

#### D. Detector de Flash de Exposición (`detect_exposure_flash`)
```python
def detect_exposure_flash(brightness_history):
    """
    Detecta ajuste automático de cámara al inicio.

    Método:
    - Analizar primeros 2-3 segundos
    - Detectar cambio brusco de brightness (>30% en <0.5s)
    - Seguido de estabilización

    Returns:
        {"type": "exposure_adjustment", "duration": 1.2} | None
    """
```

#### E. Detector de Corte Abrupto (`detect_abrupt_cut`)
```python
def detect_abrupt_cut(motion_history, position):
    """
    Detecta grabación que empieza/termina a medio movimiento.

    Método:
    - Si motion > threshold en primer/último frame
    - Y la dirección del movimiento indica continuidad
    → El clip está cortado

    Returns:
        "cut_at_start" | "cut_at_end" | None
    """
```

### 1.2 Estructura de Datos para Basura

```python
class GarbageDetection:
    garbage_type: str  # "lens_cap", "black_frame", "pre_roll", etc.
    confidence: float  # 0.0 - 1.0
    start_time: float
    end_time: float
    recoverable: bool  # True si se puede recortar y salvar algo
    suggested_trim: tuple  # (new_start, new_end) si recoverable
```

### 1.3 Integración en Pipeline

```python
def analyze_video(self, video_path):
    # NUEVO: Primera pasada - detectar basura
    garbage_segments = self.detect_garbage(frames)

    # Marcar segmentos de basura ANTES de análisis detallado
    # Opción: Skip análisis costoso en segmentos de basura

    # Análisis normal para segmentos no-basura
    for segment in non_garbage_segments:
        self.analyze_segment(segment)
```

---

## FASE 2: Clasificación de Tipo de Plano

### 2.1 Tipos de Plano a Detectar

| Tipo | Método de Detección |
|------|---------------------|
| **Plano General (ELS/LS)** | Muchos edges distribuidos, bajo % de frame ocupado por elementos principales |
| **Plano Medio (MS)** | Distribución equilibrada, rostro detectado ocupando 20-40% de frame |
| **Close-up (CU)** | Rostro detectado ocupando >40% de frame, o elemento único dominante |
| **Extreme Close-up (ECU)** | Muy pocos edges, área de foco concentrada, posible textura |
| **Plano Detalle** | Sin rostro, área pequeña muy definida, resto soft |
| **POV/Subjetiva** | Movimiento característico (walking motion), horizonte inclinado frecuente |
| **Over the Shoulder** | Rostro detectado + elemento borroso en primer plano en esquina |

### 2.2 Algoritmo de Clasificación

```python
def classify_shot_type(frame, face_detection_result, edge_map):
    """
    Clasifica el tipo de plano basado en múltiples señales.
    """
    features = {
        "edge_density": calculate_edge_density(edge_map),
        "edge_distribution": analyze_edge_distribution(edge_map),
        "face_coverage": face_detection_result.coverage if face_detection_result else 0,
        "face_count": face_detection_result.count if face_detection_result else 0,
        "foreground_blur": detect_foreground_blur(frame),
        "depth_of_field": estimate_dof(frame),
        "motion_pattern": analyze_motion_pattern(motion_history)
    }

    # Árbol de decisión simple (no ML)
    if features["face_count"] > 0:
        if features["foreground_blur"] > threshold:
            return "OVER_THE_SHOULDER"
        if features["face_coverage"] > 0.5:
            return "EXTREME_CLOSEUP"
        if features["face_coverage"] > 0.3:
            return "CLOSEUP"
        if features["face_coverage"] > 0.15:
            return "MEDIUM_SHOT"
        return "WIDE_SHOT"

    if features["edge_density"] < 0.05:
        if features["depth_of_field"] == "shallow":
            return "DETAIL_SHOT"
        return "ESTABLISHING"  # o cielo/paisaje

    if features["motion_pattern"] == "walking":
        return "POV"

    if features["edge_distribution"] == "spread":
        return "WIDE_SHOT"

    return "MEDIUM_SHOT"  # default
```

### 2.3 Estructura de Datos

```python
class ShotTypeClassification:
    shot_type: str  # "WIDE", "MEDIUM", "CLOSEUP", "ECU", "DETAIL", "POV", "OTS"
    confidence: float
    face_count: int
    face_coverage: float
    characteristics: list  # ["shallow_dof", "movement", "multiple_subjects"]
```

---

## FASE 3: Detección de Rostros

### 3.1 Usando OpenCV (sin IA externa)

```python
# Usar Haar Cascades incluidos en OpenCV
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_eye.xml'
)
```

### 3.2 Análisis de Rostros

```python
def analyze_faces(frame, gray_frame):
    """
    Detecta y analiza rostros en el frame.
    """
    faces = face_cascade.detectMultiScale(gray_frame, 1.1, 4)

    results = []
    for (x, y, w, h) in faces:
        face_roi = gray_frame[y:y+h, x:x+w]

        # Verificar foco en rostro específicamente
        face_sharpness = cv2.Laplacian(face_roi, cv2.CV_64F).var()

        # Detectar ojos
        eyes = eye_cascade.detectMultiScale(face_roi)
        eyes_open = len(eyes) >= 2

        # Verificar headroom (espacio sobre la cabeza)
        headroom_ratio = y / frame.shape[0]
        headroom_ok = 0.05 < headroom_ratio < 0.25

        # Verificar si rostro está cortado
        face_cut = (x < 5 or y < 5 or
                    x + w > frame.shape[1] - 5 or
                    y + h > frame.shape[0] - 5)

        results.append({
            "bbox": (x, y, w, h),
            "coverage": (w * h) / (frame.shape[0] * frame.shape[1]),
            "in_focus": face_sharpness > 50,  # threshold ajustable
            "sharpness": face_sharpness,
            "eyes_detected": len(eyes),
            "eyes_open": eyes_open,
            "headroom_ok": headroom_ok,
            "face_cut": face_cut,
            "position": classify_face_position(x, y, w, h, frame.shape)
        })

    return FaceAnalysisResult(
        face_count=len(results),
        faces=results,
        any_in_focus=any(f["in_focus"] for f in results),
        all_eyes_open=all(f["eyes_open"] for f in results),
        framing_issues=[f for f in results if f["face_cut"] or not f["headroom_ok"]]
    )
```

### 3.3 Estructura de Datos

```python
class FaceAnalysisResult:
    face_count: int
    faces: list[FaceInfo]
    any_in_focus: bool
    all_eyes_open: bool
    best_face_sharpness: float
    framing_issues: list[str]  # ["face_cut_left", "no_headroom", etc.]
```

---

## FASE 4: Agrupación por Setup/Escena

### 4.1 Concepto

Un "setup" es una configuración de cámara que se mantiene para múltiples tomas. El editor piensa: "todas las tomas del ángulo A", "todas las del ángulo B".

### 4.2 Features para Clustering

```python
def extract_setup_features(segment):
    """
    Extrae características para identificar el setup.
    """
    return {
        # Color dominante (paleta)
        "color_histogram": compute_color_histogram(segment.representative_frame),
        "dominant_colors": extract_dominant_colors(segment.representative_frame, k=3),

        # Composición general
        "edge_distribution_vector": compute_edge_distribution(segment),
        "brightness_profile": compute_brightness_profile(segment),

        # Tipo de plano (de Fase 2)
        "shot_type": segment.shot_type,

        # Características específicas
        "has_faces": segment.face_count > 0,
        "face_positions": segment.face_positions,  # normalized

        # Metadatos temporales
        "timestamp": segment.start_time,
        "video_index": segment.video_index
    }
```

### 4.3 Algoritmo de Clustering

```python
def cluster_by_setup(segments):
    """
    Agrupa segmentos que parecen ser del mismo setup.

    Usa clustering jerárquico con distancia personalizada.
    """
    features = [extract_setup_features(s) for s in segments]

    # Calcular matriz de distancia
    distance_matrix = compute_setup_distance_matrix(features)

    # Clustering jerárquico (no necesita especificar K)
    from scipy.cluster.hierarchy import linkage, fcluster
    Z = linkage(distance_matrix, method='ward')

    # Cortar donde la distancia aumenta significativamente
    clusters = fcluster(Z, t=threshold, criterion='distance')

    # Agrupar
    setups = defaultdict(list)
    for segment, cluster_id in zip(segments, clusters):
        setups[f"setup_{cluster_id}"].append(segment)

    return setups

def compute_setup_distance(feat1, feat2):
    """
    Distancia personalizada entre dos setups.
    """
    # Color es muy importante
    color_dist = histogram_distance(feat1["color_histogram"],
                                     feat2["color_histogram"])

    # Mismo tipo de plano = más probable mismo setup
    shot_type_match = 1.0 if feat1["shot_type"] == feat2["shot_type"] else 0.0

    # Proximidad temporal también cuenta
    time_proximity = 1.0 / (1.0 + abs(feat1["timestamp"] - feat2["timestamp"]))

    # Weighted combination
    return (0.5 * color_dist +
            0.3 * (1 - shot_type_match) +
            0.2 * (1 - time_proximity))
```

### 4.4 Estructura de Datos

```python
class SetupGroup:
    setup_id: str  # "setup_1", "setup_2", etc.
    segments: list[Segment]
    representative_thumbnail: str  # path to thumbnail
    characteristics: dict  # {"dominant_color": "#3a5a40", "shot_type": "MEDIUM"}
    total_duration: float
    video_sources: list[str]  # de qué videos vienen
```

---

## FASE 5: Detección de Takes Repetidos

### 5.1 Concepto

Cuando grabas múltiples takes de la misma escena, detectar cuáles son "el mismo momento" para comparar rápidamente.

### 5.2 Algoritmo

```python
def find_repeated_takes(segments, same_setup_only=True):
    """
    Encuentra segmentos que parecen ser takes del mismo momento.

    Señales:
    - Mismo setup (de Fase 4)
    - Duración similar
    - Composición casi idéntica
    - Cercanos en tiempo de grabación
    """
    take_groups = []

    for i, seg1 in enumerate(segments):
        if seg1.already_grouped:
            continue

        group = TakeGroup(primary=seg1)

        for seg2 in segments[i+1:]:
            if is_same_take(seg1, seg2):
                group.add_take(seg2)
                seg2.already_grouped = True

        if len(group.takes) > 1:
            # Ordenar por calidad técnica
            group.rank_by_technical_quality()
            take_groups.append(group)

    return take_groups

def is_same_take(seg1, seg2):
    """
    Determina si dos segmentos son takes del mismo momento.
    """
    # Mismo setup es requisito
    if seg1.setup_id != seg2.setup_id:
        return False

    # Duración similar (±20%)
    duration_ratio = min(seg1.duration, seg2.duration) / max(seg1.duration, seg2.duration)
    if duration_ratio < 0.8:
        return False

    # Composición muy similar (histograma de edges)
    composition_similarity = compare_composition(seg1, seg2)
    if composition_similarity < 0.85:
        return False

    # Verificar que NO sean el mismo segmento exacto
    if seg1.video_id == seg2.video_id and abs(seg1.start_time - seg2.start_time) < 1.0:
        return False

    return True
```

### 5.3 Estructura de Datos

```python
class TakeGroup:
    takes: list[Segment]
    best_technical: Segment  # el de mejor score técnico
    comparison_thumbnail: str  # grid de thumbnails side-by-side

    def get_comparison_data(self):
        """Datos para mostrar comparación en UI."""
        return [{
            "segment_id": t.id,
            "video": t.video_filename,
            "score": t.score,
            "metrics_summary": t.get_key_metrics(),
            "thumbnail": t.thumbnail_path
        } for t in self.takes]
```

---

## FASE 6: Etiquetado Contextual (Tags vs Tiers)

### 6.1 Filosofía

En lugar de `DISCARD`, etiquetar con **características observables** que le permitan al editor decidir.

### 6.2 Sistema de Tags

```python
class SegmentTags:
    # Estabilidad
    stability_tags: list  # ["rock_solid", "smooth", "handheld", "shaky", "very_shaky"]

    # Foco
    focus_tags: list  # ["tack_sharp", "good_focus", "soft_focus", "selective_focus", "out_of_focus"]

    # Exposición
    exposure_tags: list  # ["well_exposed", "slightly_over", "slightly_under",
                         #  "recoverable_over", "recoverable_under",
                         #  "clipped_highlights", "crushed_blacks"]

    # Combinaciones útiles
    compound_tags: list  # ["shaky_but_sharp", "soft_but_usable", "technically_perfect"]

    # Contexto de uso sugerido
    suggested_use: list  # ["hero_shot", "b_roll", "transition", "cutaway", "establishing"]

def generate_tags(segment):
    """
    Genera tags descriptivos basados en métricas.
    """
    tags = SegmentTags()

    # Estabilidad
    if segment.tremor_score < 0.1:
        tags.stability_tags.append("rock_solid")
    elif segment.tremor_score < 0.3:
        tags.stability_tags.append("smooth")
    elif segment.tremor_score < 0.5:
        tags.stability_tags.append("handheld")
    elif segment.tremor_score < 0.7:
        tags.stability_tags.append("shaky")
    else:
        tags.stability_tags.append("very_shaky")

    # Foco
    if segment.sharpness > 150:
        tags.focus_tags.append("tack_sharp")
    elif segment.sharpness > 80:
        tags.focus_tags.append("good_focus")
    elif segment.sharpness > 40:
        tags.focus_tags.append("soft_focus")
    else:
        tags.focus_tags.append("out_of_focus")

    # Exposición con análisis de recuperabilidad
    if 0.4 < segment.brightness_mean < 0.7:
        tags.exposure_tags.append("well_exposed")
    elif segment.brightness_mean > 0.7:
        if segment.has_clipped_highlights:
            tags.exposure_tags.append("clipped_highlights")
        else:
            tags.exposure_tags.append("recoverable_over")
    else:
        if segment.has_crushed_blacks:
            tags.exposure_tags.append("crushed_blacks")
        else:
            tags.exposure_tags.append("recoverable_under")

    # Tags compuestos
    if "shaky" in tags.stability_tags and "tack_sharp" in tags.focus_tags:
        tags.compound_tags.append("shaky_but_sharp")

    if all(t in ["rock_solid", "smooth"] for t in tags.stability_tags) and \
       "tack_sharp" in tags.focus_tags and \
       "well_exposed" in tags.exposure_tags:
        tags.compound_tags.append("technically_perfect")

    return tags
```

### 6.3 UI para Tags

En lugar de solo mostrar `GOLD/SILVER/BRONZE`, mostrar:

```
[GOLD] Plano Medio | rock_solid | tack_sharp | well_exposed
       2 rostros en foco | setup_A | take 2/3 (mejor técnico)

[SILVER] Close-up | handheld | good_focus | slightly_under (recuperable)
         1 rostro | ojos abiertos | headroom OK

[BRONZE] POV | shaky_but_sharp | recoverable_under
         Movimiento intencional detectado | B-roll sugerido
```

---

## FASE 7: Búsqueda Transversal

### 7.1 Índice de Búsqueda

```python
class ProjectSearchIndex:
    """
    Índice para búsquedas rápidas a través de todo el proyecto.
    """

    def __init__(self, project_id):
        self.segments = []  # todos los segmentos del proyecto
        self.indices = {
            "by_shot_type": defaultdict(list),
            "by_setup": defaultdict(list),
            "by_tier": defaultdict(list),
            "by_tag": defaultdict(list),
            "by_face_count": defaultdict(list),
            "with_faces_in_focus": [],
            "by_video": defaultdict(list)
        }

    def index_segment(self, segment):
        self.segments.append(segment)
        self.indices["by_shot_type"][segment.shot_type].append(segment)
        self.indices["by_setup"][segment.setup_id].append(segment)
        self.indices["by_tier"][segment.tier].append(segment)
        self.indices["by_video"][segment.video_id].append(segment)

        for tag in segment.all_tags:
            self.indices["by_tag"][tag].append(segment)

        if segment.face_count > 0:
            self.indices["by_face_count"][segment.face_count].append(segment)
            if segment.faces_in_focus:
                self.indices["with_faces_in_focus"].append(segment)

    def search(self, query: SearchQuery) -> list[Segment]:
        """
        Ejecuta una búsqueda con múltiples filtros.
        """
        results = set(self.segments)

        if query.shot_type:
            results &= set(self.indices["by_shot_type"][query.shot_type])

        if query.min_tier:
            valid_tiers = get_tiers_above(query.min_tier)
            tier_segments = set()
            for tier in valid_tiers:
                tier_segments |= set(self.indices["by_tier"][tier])
            results &= tier_segments

        if query.required_tags:
            for tag in query.required_tags:
                results &= set(self.indices["by_tag"][tag])

        if query.faces_required:
            results &= set(self.indices["with_faces_in_focus"])

        # Ordenar por score
        return sorted(results, key=lambda s: s.score, reverse=True)
```

### 7.2 API Endpoints Nuevos

```python
# Búsqueda transversal
@app.route('/api/projects/<project_id>/search', methods=['POST'])
def search_project(project_id):
    """
    Busca segmentos en todo el proyecto.

    Body:
    {
        "shot_type": "CLOSEUP",
        "min_tier": "silver",
        "tags": ["faces_in_focus", "good_exposure"],
        "limit": 20,
        "sort_by": "score"
    }
    """

# Mejores de cada tipo
@app.route('/api/projects/<project_id>/best/<shot_type>')
def get_best_shots(project_id, shot_type):
    """
    Retorna los mejores N shots de un tipo específico.
    """

# Comparación de takes
@app.route('/api/projects/<project_id>/takes')
def get_take_groups(project_id):
    """
    Retorna grupos de takes repetidos para comparación.
    """

# Estadísticas de setups
@app.route('/api/projects/<project_id>/setups')
def get_setups(project_id):
    """
    Retorna los setups detectados con sus segmentos.
    """
```

---

## Cambios en UI (React)

### 7.3 Nuevos Componentes

1. **GarbageFilter** - Mostrar/ocultar basura detectada
2. **ShotTypeFilter** - Filtrar por tipo de plano
3. **SetupBrowser** - Navegar por setups detectados
4. **TakeComparison** - Comparar takes side-by-side
5. **TagCloud** - Mostrar y filtrar por tags
6. **CrossProjectSearch** - Buscador transversal

### 7.4 Mejoras en Timeline Visual

```jsx
// Nuevo: Mini-waveform de actividad
<ActivityWaveform
  data={segment.motion_history}
  markers={segment.events}  // "motion_start", "stabilized", etc.
/>

// Nuevo: Indicadores de rostros
<FaceIndicator
  count={segment.face_count}
  inFocus={segment.faces_in_focus}
  issues={segment.framing_issues}
/>

// Nuevo: Tags inline
<TagBadges tags={segment.tags.slice(0, 3)} />
```

---

## Orden de Implementación Recomendado

### Sprint 1: Fundamentos (1-2 semanas)
1. **Detección de basura** - Máximo impacto inmediato
2. **Tags básicos** - Reemplazar el sistema de tiers absolutos
3. **Ajustes a data structures** - Preparar para nuevos campos

### Sprint 2: Clasificación (1-2 semanas)
4. **Clasificación de planos** - shot_type detection
5. **Detección de rostros** - Haar cascades + análisis
6. **UI para mostrar nueva info** - Badges, filtros

### Sprint 3: Agrupación (2 semanas)
7. **Setup clustering** - Agrupar por escena/ángulo
8. **Detección de takes** - Encontrar repeticiones
9. **UI de comparación** - Side-by-side

### Sprint 4: Búsqueda (1 semana)
10. **Índice de búsqueda** - Estructura de datos
11. **API de búsqueda** - Endpoints
12. **UI de búsqueda transversal** - Componentes

### Sprint 5: Polish (1 semana)
13. **Timeline mejorado** - Waveform, markers
14. **Export actualizado** - Incluir nueva metadata en XML
15. **Reportes HTML** - Actualizar con nueva info

---

## Archivos a Modificar/Crear

### Python Backend

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `video_analyzer_engine.py` | MODIFICAR | Agregar detectores de basura, clasificación de planos |
| `garbage_detector.py` | CREAR | Módulo dedicado a detección de basura |
| `shot_classifier.py` | CREAR | Clasificación de tipos de plano |
| `face_analyzer.py` | CREAR | Análisis de rostros con OpenCV |
| `setup_clusterer.py` | CREAR | Agrupación por setup |
| `take_matcher.py` | CREAR | Detección de takes repetidos |
| `tag_generator.py` | CREAR | Sistema de etiquetado |
| `search_index.py` | CREAR | Índice de búsqueda transversal |
| `app.py` | MODIFICAR | Nuevos endpoints |

### React Frontend

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `components/GarbageFilter.jsx` | CREAR | Filtro de basura |
| `components/ShotTypeFilter.jsx` | CREAR | Filtro por tipo de plano |
| `components/SetupBrowser.jsx` | CREAR | Navegador de setups |
| `components/TakeComparison.jsx` | CREAR | Comparador de takes |
| `components/TagBadges.jsx` | CREAR | Badges de tags |
| `components/SearchPanel.jsx` | CREAR | Búsqueda transversal |
| `components/VideoCard.jsx` | MODIFICAR | Mostrar nueva info |
| `components/ResultsPanel.jsx` | MODIFICAR | Nuevas estadísticas |
| `context/AppContext.jsx` | MODIFICAR | Nuevos estados y API calls |

---

## Métricas de Éxito

1. **Reducción de scroll** - Medir cuánto contenido se marca como "basura" automáticamente
2. **Precisión de clasificación** - % de planos correctamente clasificados
3. **Utilidad de agrupación** - ¿Los setups detectados coinciden con la realidad?
4. **Tiempo de primer pase** - ¿El editor encuentra lo que busca más rápido?

---

## Notas Técnicas

### Performance
- El análisis de rostros es costoso → hacerlo cada N frames, no cada frame
- El clustering se hace post-análisis, no en tiempo real
- Indexar para búsquedas O(1) en lugar de O(n)

### Compatibilidad
- Mantener backward compatibility con análisis existentes
- Los nuevos campos son opcionales en el JSON
- UI degrada gracefully si faltan datos nuevos

### Testing
- Unit tests para cada detector
- Test con videos reales de diferentes escenarios
- Benchmark de performance con videos largos
