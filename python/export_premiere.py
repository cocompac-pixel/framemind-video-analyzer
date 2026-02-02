#!/usr/bin/env python3
"""
Export to Premiere Pro XML
Genera XML compatible con Premiere Pro desde clips seleccionados

Soporta dos modos:
- single: Un track con todos los clips en secuencia
- multi: Un track por cada tier seleccionado

HOTFIX V5.1:
- FPS dinámico basado en el video source
- IDs consistentes usando hash MD5
- Sanitización de nombres (remover acentos)
- Validación de media_folder
"""

import json
import hashlib
import re
import unicodedata
from pathlib import Path
from datetime import datetime

try:
    from xml_validator import XMEMLValidator
except ImportError:
    XMEMLValidator = None


def _sanitize_filename(filename):
    """
    Sanitiza nombre de archivo para XML:
    - Remueve acentos y caracteres especiales
    - Solo permite alfanuméricos, guiones y guiones bajos
    """
    # Normalizar Unicode (NFKD separa caracteres base de acentos)
    normalized = unicodedata.normalize('NFKD', filename)
    # Convertir a ASCII ignorando acentos
    ascii_name = normalized.encode('ASCII', 'ignore').decode('ASCII')
    # Reemplazar caracteres no permitidos
    sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '_', ascii_name)
    return sanitized


def _get_file_id(filepath):
    """
    Genera ID consistente para archivo usando hash MD5
    """
    # Usar hash del path completo para evitar colisiones
    hash_obj = hashlib.md5(filepath.encode('utf-8'))
    return f"f_{hash_obj.hexdigest()[:8]}"


def _detect_source_fps(clips):
    """
    Detecta el FPS más común entre los clips
    Fallback a 30 si no se puede determinar
    """
    fps_values = []
    for clip in clips:
        fps = clip.get('fps', 0)
        if fps and fps > 0:
            fps_values.append(fps)
    
    if fps_values:
        # Usar el FPS más común (moda)
        from statistics import mode
        try:
            return mode(fps_values)
        except:
            return fps_values[0]
    
    return 30  # Default fallback


def _validate_media_folder(media_folder):
    """
    Valida que el media_folder existe y es accesible
    Retorna tupla (is_valid, resolved_path)
    """
    path = Path(media_folder)
    
    # Expandir home directory si es necesario
    if str(path).startswith('~'):
        path = path.expanduser()
    
    if path.exists() and path.is_dir():
        return True, str(path)
    
    # Intentar crear si no existe
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True, str(path)
    except:
        return False, str(path)


def generate_premiere_xml_v2(clips, options, output_path=None):
    """
    Genera XML compatible con Premiere Pro

    Args:
        clips: Lista de clips con {filename, path, start_time, end_time, tier, ...}
        options: {
            tiers: ['gold', 'silver', ...],
            track_mode: 'single' | 'multi',
            media_folder: str (opcional),
        }
        output_path: Path de salida (opcional)

    Returns:
        Path del archivo generado o None si hay error
    """

    if not clips:
        return None

    # Configuración
    tiers_to_export = options.get('tiers', ['gold', 'silver'])
    track_mode = options.get('track_mode', 'multi')
    media_folder = options.get('media_folder', '/Users/danielazpe/Movies')
    
    # HOTFIX: Validar media_folder
    is_valid_folder, resolved_media_folder = _validate_media_folder(media_folder)
    if not is_valid_folder:
        print(f"WARNING: Media folder no accesible: {media_folder}")
        print(f"Usando fallback: {resolved_media_folder}")
    
    # HOTFIX: Detectar FPS del source
    fps = _detect_source_fps(clips)
    timebase = int(fps) if fps == int(fps) else fps
    
    print(f"Exportando con FPS: {fps}")

    def frames(seconds):
        return int(seconds * fps)

    # Filtrar clips por tiers seleccionados
    filtered_clips = [c for c in clips if c.get('tier') in tiers_to_export]

    if not filtered_clips:
        return None

    # Organizar clips por tier
    clips_by_tier = {tier: [] for tier in ['gold', 'silver', 'bronze', 'discard']}
    file_registry = {}

    for clip in filtered_clips:
        tier = clip.get('tier', 'discard')
        filename = clip.get('filename', 'unknown')
        filepath = clip.get('path', f'{resolved_media_folder}/{filename}')

        # HOTFIX: Usar hash para ID consistente
        file_id = _get_file_id(filepath)
        
        # HOTFIX: Sanitizar nombre
        safe_filename = _sanitize_filename(filename)

        if file_id not in file_registry:
            file_registry[file_id] = {
                'filename': safe_filename,
                'filepath': filepath,
                'duration': clip.get('duration', 0)
            }

        clips_by_tier[tier].append({
            'file_id': file_id,
            'filename': safe_filename,
            'start': clip.get('start_time', 0),
            'end': clip.get('end_time', 0),
            'duration': clip.get('end_time', 0) - clip.get('start_time', 0),
            'tier': tier,
        })

    # Calcular duración total
    total_duration = sum(c['duration'] for c in filtered_clips)

    # Labels de Premiere por tier
    tier_labels = {
        'gold': 'Forest',    # Verde
        'silver': 'Iris',    # Morado
        'bronze': 'Mango',   # Naranja
        'discard': 'Rose',   # Rosa
    }

    # Construir XML header
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
            <width>1920</width>
            <height>1080</height>
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

    def generate_clip_xml(clip, timeline_pos, clip_id, defined_files):
        """Genera XML para un clip individual"""
        file_id = clip['file_id']
        file_info = file_registry[file_id]
        tier = clip['tier']

        if file_id not in defined_files:
            defined_files.add(file_id)
            file_xml = f'''
              <file id="file-{file_id}">
                <name>{file_info['filename']}</name>
                <pathurl>file://{file_info['filepath']}</pathurl>
                <rate>
                  <timebase>{timebase}</timebase>
                  <ntsc>FALSE</ntsc>
                </rate>
                <duration>{frames(file_info['duration'])}</duration>
                <media>
                  <video>
                    <samplecharacteristics>
                      <width>1920</width>
                      <height>1080</height>
                    </samplecharacteristics>
                  </video>
                </media>
              </file>'''
        else:
            file_xml = f'''
              <file id="file-{file_id}"/>'''

        short_name = clip['filename'][:15]
        tier_upper = tier.upper()
        label = tier_labels.get(tier, 'Lavender')

        return f'''          <clipitem id="clipitem-{clip_id}">
            <name>{short_name} {tier_upper}</name>
            <duration>{frames(clip['duration'])}</duration>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <start>{frames(timeline_pos)}</start>
            <end>{frames(timeline_pos + clip['duration'])}</end>
            <in>{frames(clip['start'])}</in>
            <out>{frames(clip['end'])}</out>{file_xml}
            <labels>
              <label2>{label}</label2>
            </labels>
          </clipitem>
'''

    if track_mode == 'single':
        # MODO SINGLE: Un track con todos los clips
        xml += '''        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
'''
        timeline_pos = 0

        # Ordenar por tier (gold primero, luego silver, etc.) y luego por tiempo
        tier_order = {'gold': 0, 'silver': 1, 'bronze': 2, 'discard': 3}
        all_clips = []
        for tier in tiers_to_export:
            all_clips.extend(clips_by_tier.get(tier, []))

        # Ordenar por tiempo dentro de cada tier
        all_clips.sort(key=lambda c: (tier_order.get(c['tier'], 99), c['start']))

        for clip in all_clips:
            xml += generate_clip_xml(clip, timeline_pos, clip_id, defined_files)
            timeline_pos += clip['duration']
            clip_id += 1

        xml += '''        </track>
'''

    else:
        # MODO MULTI: Un track por tier
        for tier in tiers_to_export:
            tier_clips = clips_by_tier.get(tier, [])
            if not tier_clips:
                continue

            # Ordenar por tiempo
            tier_clips.sort(key=lambda c: c['start'])

            xml += f'''        <track>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
'''
            timeline_pos = 0

            for clip in tier_clips:
                xml += generate_clip_xml(clip, timeline_pos, clip_id, defined_files)
                timeline_pos += clip['duration']
                clip_id += 1

            xml += '''        </track>
'''

    # Cerrar XML
    xml += '''      </video>
    </media>
  </sequence>
</xmeml>'''

    # HOTFIX: Validar XML antes de guardar
    if XMEMLValidator:
        is_valid, errors = XMEMLValidator.validate(xml)
        if not is_valid:
            print("WARNING: XML generado tiene errores de validación:")
            for error in errors[:5]:  # Mostrar primeros 5 errores
                print(f"  - {error}")
            if len(errors) > 5:
                print(f"  ... y {len(errors) - 5} errores más")
    
    # Guardar
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f'premiere_export_{timestamp}.xml')

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    
    print(f"XML exportado exitosamente: {output_path}")
    print(f"  - FPS: {fps}")
    print(f"  - Clips: {len(filtered_clips)}")
    print(f"  - Duración total: {total_duration:.2f}s")

    return output_path


# Mantener compatibilidad con versión anterior
def generate_premiere_xml(json_path, output_path=None):
    """Versión legacy - genera desde JSON de análisis"""

    with open(json_path, 'r') as f:
        data = json.load(f)

    results = data.get('analyses', [])

    if not results:
        return None

    # Convertir a formato de clips
    clips = []
    for r in results:
        if not r.get('success', True):
            continue

        filename = r.get('filename', 'unknown')
        filepath = r.get('path', f'/Users/danielazpe/Movies/{filename}')
        duration = r.get('duration', 0)
        ranges = r.get('ranges', {})

        for tier in ['gold', 'silver', 'bronze', 'discard']:
            for rng in ranges.get(tier, []):
                clips.append({
                    'filename': filename,
                    'path': filepath,
                    'start_time': rng['start'],
                    'end_time': rng['end'],
                    'duration': duration,
                    'tier': tier,
                })

    options = {
        'tiers': ['gold', 'silver', 'bronze', 'discard'],
        'track_mode': 'multi',
    }

    return generate_premiere_xml_v2(clips, options, output_path)


if __name__ == "__main__":
    import sys

    print("="*60)
    print("   🎬 EXPORT TO PREMIERE PRO")
    print("="*60)

    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
        if json_path.exists():
            output_path = generate_premiere_xml(json_path)
            if output_path:
                print(f"   ✅ Generado: {output_path}")
            else:
                print("   ❌ No se pudo generar el XML")
        else:
            print(f"   ❌ No existe: {json_path}")
    else:
        print("   Uso: python3 export_premiere.py <archivo.json>")
