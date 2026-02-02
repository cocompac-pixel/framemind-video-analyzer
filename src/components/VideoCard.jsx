import { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';

// Traducciones de términos técnicos a lenguaje de editor
const SHOT_TYPE_LABELS = {
  'ESTATICA': 'Cámara fija',
  'TRIPOD': 'Cámara en trípode',
  'LOCKED': 'Plano bloqueado',
  'PANEO': 'Paneo horizontal',
  'TILT': 'Paneo vertical',
  'TRACKING': 'Seguimiento',
  'DOLLY': 'Dolly / travelling',
  'MOVIMIENTO_FLUIDO': 'Movimiento fluido',
  'SHAKY': 'Cámara en mano (inestable)',
  'TRANSICION': 'Transición',
  'DESCONOCIDO': 'Sin clasificar'
};

const GARBAGE_TYPE_LABELS = {
  'lens_cap': 'Tapa de lente',
  'floor': 'Apuntando al piso',
  'black': 'Pantalla negra',
  'overexposed': 'Sobreexpuesto total',
  'pre_roll': 'Pre-roll (antes de grabar)',
  'post_roll': 'Post-roll (después de grabar)',
  'blurry': 'Completamente borroso',
  'no usable': 'Material no usable'
};

// Traducciones de tipos de key moment
const KEY_MOMENT_LABELS = {
  'mejor_calidad': 'de mejor calidad',
  'best_quality': 'de mejor calidad',
  'peak_action': 'de acción',
  'highlight': 'destacado',
  'emotional': 'emotivo',
  'transition': 'de transición',
};

// Función para humanizar tags (quitar underscores y capitalizar)
const humanizeTag = (tag) => {
  if (!tag) return '';
  return tag
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
};

function VideoCard({ video, hideGarbage = false }) {
  const { selectedVideos, toggleVideoSelection } = useApp();
  const [tooltipData, setTooltipData] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [showFacesPanel, setShowFacesPanel] = useState(false);
  const timelineRef = useRef(null);

  const isSelected = selectedVideos.has(video.id);
  const allSegments = video.segments || [];

  // Filtrar basura si está activado
  const segments = hideGarbage
    ? allSegments.filter(s => !s.is_garbage && s.tier !== 'garbage')
    : allSegments;

  // Calculate usable percentage
  const goldDuration = segments
    .filter(s => s.tier === 'gold')
    .reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
  const silverDuration = segments
    .filter(s => s.tier === 'silver')
    .reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
  const usablePercent = video.duration > 0
    ? Math.round(((goldDuration + silverDuration) / video.duration) * 100)
    : 0;

  // Calcular estadísticas de takes repetidos
  const takesInfo = (() => {
    const bestTakes = segments.filter(s => s.is_best_take === true);
    const repeatedTakes = segments.filter(s => s.is_repeated_take === true);
    const totalAlternatives = segments.reduce((sum, s) => sum + (s.take_alternatives || 0), 0);
    return {
      hasTakeGroups: bestTakes.length > 0 || repeatedTakes.length > 0,
      bestTakesCount: bestTakes.length,
      repeatedCount: repeatedTakes.length,
      totalAlternatives
    };
  })();

  // Calcular key moments
  const keyMomentsCount = segments.filter(s => s.is_key_moment).length;

  // Calcular basura
  const garbageInfo = (() => {
    const garbageSegments = allSegments.filter(s => s.is_garbage || s.tier === 'garbage');
    const garbageDuration = garbageSegments.reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
    return {
      hasGarbage: garbageSegments.length > 0,
      count: garbageSegments.length,
      duration: garbageDuration
    };
  })();

  // Calcular grupos de escena
  const sceneGroupsInfo = (() => {
    const groupIds = new Set(segments.filter(s => s.scene_group_id != null).map(s => s.scene_group_id));
    return {
      hasGroups: groupIds.size > 1,
      count: groupIds.size
    };
  })();

  // Calcular rostros con detalles
  const facesInfo = (() => {
    const withFaces = segments.filter(s => s.face_count > 0 || s.face_analysis?.has_faces);
    const totalFaceTime = withFaces.reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
    const maxFaces = Math.max(0, ...withFaces.map(s => s.face_count || s.face_analysis?.avg_face_count || 0));
    const faceSegments = withFaces.map(s => ({
      start: s.start_time,
      end: s.end_time,
      count: s.face_count || s.face_analysis?.avg_face_count || 0,
      tier: s.tier,
      shotType: s.shot_type,
      framingType: s.framing_type_display || s.framing_type
    }));
    return {
      hasFaces: withFaces.length > 0,
      segmentsWithFaces: withFaces.length,
      totalFaceTime,
      maxFaces,
      faceSegments
    };
  })();

  const handleMouseMove = (e, segment) => {
    if (!timelineRef.current) return;

    const rect = timelineRef.current.getBoundingClientRect();
    setTooltipPos({ x: e.clientX, y: rect.top });

    // Preparar datos para el tooltip orientado a acción
    setTooltipData({
      start: segment.start_time,
      end: segment.end_time,
      duration: segment.end_time - segment.start_time,
      tier: segment.tier,
      shotType: segment.shot_type || 'DESCONOCIDO',
      framingType: segment.framing_type_display || segment.framing_type || '',
      stability: segment.human_readable?.stability,
      imageQuality: segment.human_readable?.image_quality,
      framing: segment.human_readable?.framing,
      isKeyMoment: segment.is_key_moment,
      keyMomentType: segment.key_moment_type,
      keyMomentReason: segment.key_moment_reason,
      isBestTake: segment.is_best_take,
      isRepeatedTake: segment.is_repeated_take,
      takeAlternatives: segment.take_alternatives || 0,
      isGarbage: segment.is_garbage || segment.tier === 'garbage',
      garbageType: segment.garbage_type,
      faceCount: segment.face_count || segment.face_analysis?.avg_face_count || 0,
      tags: segment.tags || [],
      sceneGroupId: segment.scene_group_id,
      score: segment.score,
      // Nuevas métricas v2 de movimiento cámara/objeto
      cameraMotion: segment.metrics?.camera_motion_mean || 0,
      objectMotion: segment.metrics?.object_motion_mean || 0,
      hasCameraShake: segment.metrics?.has_camera_shake || false,
      motionUniformity: segment.metrics?.motion_uniformity || 0,
    });
  };

  const handleMouseLeave = () => {
    setTooltipData(null);
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  const formatTimecode = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const f = Math.floor((seconds % 1) * 30);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}:${String(f).padStart(2, '0')}`;
  };

  // Determinar el header del tooltip según el tipo de segmento
  const getTooltipHeader = (data) => {
    if (data.isGarbage) {
      return { icon: '🗑', label: 'DESCARTAR', className: 'garbage' };
    }
    if (data.isKeyMoment) {
      return { icon: '★', label: 'DESTACADO', className: 'key-moment' };
    }
    if (data.isBestTake) {
      return { icon: '✓', label: 'USAR - MEJOR TOMA', className: 'best-take' };
    }
    if (data.isRepeatedTake) {
      return { icon: '⟲', label: 'OMITIR - REPETIDO', className: 'repeated' };
    }
    // Por tier
    const tierHeaders = {
      gold: { icon: '✓', label: 'USAR', className: 'gold' },
      silver: { icon: '⚠', label: 'REVISAR', className: 'silver' },
      bronze: { icon: '⚠', label: 'REVISAR CON CUIDADO', className: 'bronze' },
      discard: { icon: '✗', label: 'NO USAR', className: 'discard' },
    };
    return tierHeaders[data.tier] || tierHeaders.discard;
  };

  // Generar las razones de "por qué" según el contexto
  const getReasons = (data) => {
    const reasons = [];

    if (data.isGarbage) {
      const garbageLabel = GARBAGE_TYPE_LABELS[data.garbageType] || data.garbageType || 'Material no usable';
      reasons.push({ type: 'bad', text: garbageLabel });
      return reasons;
    }

    if (data.isRepeatedTake) {
      reasons.push({ type: 'info', text: 'Hay una toma mejor disponible' });
      reasons.push({ type: 'info', text: `Es 1 de ${data.takeAlternatives + 1} tomas similares` });
      return reasons;
    }

    if (data.isBestTake) {
      reasons.push({ type: 'good', text: 'Mejor calidad del grupo de tomas' });
      if (data.takeAlternatives > 0) {
        reasons.push({ type: 'info', text: `Hay ${data.takeAlternatives} alternativa${data.takeAlternatives > 1 ? 's' : ''}` });
      }
    }

    if (data.isKeyMoment) {
      const momentTypeLabel = KEY_MOMENT_LABELS[data.keyMomentType] || data.keyMomentType || 'destacado';
      reasons.push({ type: 'good', text: `Momento ${momentTypeLabel}` });
      if (data.keyMomentReason) {
        reasons.push({ type: 'info', text: data.keyMomentReason });
      }
    }

    // Razones técnicas basadas en métricas
    // MEJORA v2: Usar métricas de separación cámara/objeto
    if (data.hasCameraShake) {
      reasons.push({ type: 'bad', text: 'Temblor de cámara detectado' });
    } else if (data.stability) {
      if (data.stability.status === 'good') {
        // Si hay movimiento de objetos pero cámara estable, es positivo
        if (data.objectMotion > 0.5 && data.cameraMotion < 0.5) {
          reasons.push({ type: 'good', text: 'Cámara estable con acción en escena' });
        } else {
          reasons.push({ type: 'good', text: 'Imagen estable' });
        }
      } else if (data.stability.status === 'warning') {
        // Diferenciar: ¿es movimiento de cámara o de objetos?
        if (data.objectMotion > data.cameraMotion) {
          reasons.push({ type: 'info', text: 'Movimiento de objetos en escena' });
        } else {
          reasons.push({ type: 'warning', text: 'Algo de movimiento de cámara' });
        }
      } else if (data.stability.status === 'bad') {
        reasons.push({ type: 'bad', text: 'Mucho movimiento/temblor' });
      }
    }

    if (data.imageQuality) {
      if (data.imageQuality.status === 'bad') {
        reasons.push({ type: 'bad', text: data.imageQuality.phrase || 'Problemas de imagen' });
      } else if (data.imageQuality.status === 'warning') {
        reasons.push({ type: 'warning', text: data.imageQuality.phrase || 'Revisar calidad' });
      }
    }

    return reasons;
  };

  // Generar contenido positivo del segmento
  const getContent = (data) => {
    const content = [];

    if (data.faceCount > 0) {
      content.push({ icon: '👤', text: `${data.faceCount} persona${data.faceCount > 1 ? 's' : ''} en cuadro` });
    }

    if (data.framingType) {
      content.push({ icon: '🎬', text: data.framingType });
    }

    if (data.sceneGroupId != null) {
      content.push({ icon: '📁', text: `Escena ${data.sceneGroupId + 1}` });
    }

    // MEJORA v2: Mostrar si hay acción en escena (movimiento de objetos)
    if (data.objectMotion > 1.0 && data.cameraMotion < 0.5) {
      content.push({ icon: '🎭', text: 'Acción en escena' });
    }

    return content;
  };

  // Filtrar y priorizar tags
  const getPriorityTags = (tags) => {
    if (!tags || tags.length === 0) return [];

    // Tags prioritarios (contenido) vs técnicos
    const priorityKeywords = ['persona', 'rostro', 'entrevista', 'accion', 'dialogo', 'exterior', 'interior'];
    const priority = [];
    const others = [];

    for (const tag of tags) {
      const lowerTag = tag.toLowerCase();
      if (priorityKeywords.some(k => lowerTag.includes(k))) {
        priority.push(tag);
      } else {
        others.push(tag);
      }
    }

    // Retornar prioritarios primero, luego otros, máximo 4
    return [...priority, ...others].slice(0, 4);
  };

  // Determinar clase especial para segmentos
  const getSegmentClass = (seg) => {
    if (seg.is_garbage || seg.tier === 'garbage') return 'garbage';
    if (seg.is_key_moment) return `${seg.tier || 'discard'} key-moment`;
    if (seg.is_best_take) return `${seg.tier || 'discard'} best-take`;
    if (seg.is_repeated_take) return `${seg.tier || 'discard'} repeated-take`;
    return seg.tier || 'discard';
  };

  return (
    <div
      className={`video-card-minimal ${isSelected ? 'selected' : ''}`}
      onClick={() => toggleVideoSelection(video.id)}
    >
      <div className="video-card-row-1">
        <div
          className="video-card-checkbox"
          onClick={(e) => {
            e.stopPropagation();
            toggleVideoSelection(video.id);
          }}
        />

        {video.thumbnail_id && (
          <img
            className="video-card-thumb"
            src={`http://127.0.0.1:5050/thumbnails/${video.thumbnail_id}.jpg`}
            alt=""
          />
        )}

        <div className="mini-timeline" ref={timelineRef}>
          <div className="mini-timeline-segments">
            {segments.map((seg, idx) => {
              const widthPercent = ((seg.end_time - seg.start_time) / video.duration) * 100;
              const isGarbage = seg.is_garbage || seg.tier === 'garbage';
              const sceneColors = ['#EC4899', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#14B8A6'];
              const sceneColor = seg.scene_group_id != null ? sceneColors[seg.scene_group_id % sceneColors.length] : null;
              return (
                <div
                  key={idx}
                  className={`mini-timeline-segment ${getSegmentClass(seg)}`}
                  style={{
                    width: `${widthPercent}%`,
                    opacity: isGarbage && !hideGarbage ? 0.4 : 1,
                    borderBottom: sceneColor ? `2px solid ${sceneColor}` : 'none'
                  }}
                  onMouseMove={(e) => handleMouseMove(e, seg)}
                  onMouseLeave={handleMouseLeave}
                >
                  {seg.is_key_moment && (
                    <span className="segment-indicator key">★</span>
                  )}
                  {seg.is_best_take && !seg.is_key_moment && (
                    <span className="segment-indicator best">✓</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="video-card-duration">{formatTime(video.duration)}</div>
      </div>

      <div className="video-card-row-2">
        <div className="video-card-filename">{video.filename}</div>
        <div className="video-card-badges">
          {keyMomentsCount > 0 && (
            <span className="badge badge-key" title={`${keyMomentsCount} momento(s) clave`}>
              ★ {keyMomentsCount}
            </span>
          )}
          {takesInfo.hasTakeGroups && (
            <span className="badge badge-takes" title={`${takesInfo.bestTakesCount} mejor(es), ${takesInfo.repeatedCount} repetido(s)`}>
              ⟲ {takesInfo.repeatedCount > 0 ? `-${takesInfo.repeatedCount}` : takesInfo.bestTakesCount}
            </span>
          )}
          {sceneGroupsInfo.hasGroups && (
            <span className="badge badge-scenes" title={`${sceneGroupsInfo.count} escenas detectadas`}>
              🎬 {sceneGroupsInfo.count}
            </span>
          )}
          {facesInfo.hasFaces && (
            <span
              className={`badge badge-faces ${showFacesPanel ? 'active' : ''}`}
              title={`${facesInfo.segmentsWithFaces} segmento(s) con rostros - Click para detalles`}
              onClick={(e) => {
                e.stopPropagation();
                setShowFacesPanel(!showFacesPanel);
              }}
            >
              👤 {facesInfo.segmentsWithFaces}
            </span>
          )}
          {garbageInfo.hasGarbage && !hideGarbage && (
            <span className="badge badge-garbage" title={`${formatTime(garbageInfo.duration)} de material no usable`}>
              🗑 {formatTime(garbageInfo.duration)}
            </span>
          )}
        </div>
        <div className="video-card-usable">{usablePercent}% usable</div>
      </div>

      {/* Panel de rostros expandido */}
      {showFacesPanel && facesInfo.hasFaces && (
        <div className="faces-panel" onClick={(e) => e.stopPropagation()}>
          <div className="faces-panel-header">
            <span className="faces-panel-title">👤 Segmentos con personas</span>
            <span className="faces-panel-summary">
              {facesInfo.segmentsWithFaces} segmentos • {formatTime(facesInfo.totalFaceTime)} total
            </span>
          </div>
          <div className="faces-panel-list">
            {facesInfo.faceSegments.slice(0, 6).map((seg, idx) => (
              <div key={idx} className={`faces-segment-item ${seg.tier}`}>
                <div className="faces-segment-time">
                  {formatTimecode(seg.start)} - {formatTimecode(seg.end)}
                </div>
                <div className="faces-segment-info">
                  <span className="faces-count">{seg.count} persona{seg.count > 1 ? 's' : ''}</span>
                  {seg.framingType && <span className="faces-framing">{seg.framingType}</span>}
                </div>
              </div>
            ))}
            {facesInfo.faceSegments.length > 6 && (
              <div className="faces-more">
                +{facesInfo.faceSegments.length - 6} segmentos más
              </div>
            )}
          </div>
        </div>
      )}

      {/* Nuevo Tooltip orientado a acción */}
      {tooltipData && (
        <div
          className="tooltip-action"
          style={{
            left: tooltipPos.x,
            top: tooltipPos.y - 10,
          }}
        >
          {/* Header con acción principal */}
          {(() => {
            const header = getTooltipHeader(tooltipData);
            return (
              <div className={`tooltip-action-header ${header.className}`}>
                <span className="tooltip-action-icon">{header.icon}</span>
                <span className="tooltip-action-label">{header.label}</span>
              </div>
            );
          })()}

          {/* Timecode y duración */}
          <div className="tooltip-action-time">
            <span className="tooltip-timecode">
              {formatTimecode(tooltipData.start)} - {formatTimecode(tooltipData.end)}
            </span>
            <span className="tooltip-duration-pill">
              {tooltipData.duration.toFixed(1)}s
            </span>
          </div>

          {/* Razones (por qué) */}
          {(() => {
            const reasons = getReasons(tooltipData);
            if (reasons.length === 0) return null;
            return (
              <div className="tooltip-action-reasons">
                <div className="tooltip-section-title">
                  {tooltipData.isGarbage ? 'Problema:' :
                   tooltipData.isRepeatedTake ? 'Por qué omitir:' :
                   tooltipData.tier === 'gold' || tooltipData.isBestTake ? 'Por qué usar:' :
                   'Por qué revisar:'}
                </div>
                {reasons.map((reason, idx) => (
                  <div key={idx} className={`tooltip-reason ${reason.type}`}>
                    <span className="reason-bullet">
                      {reason.type === 'good' ? '✓' : reason.type === 'bad' ? '✗' : reason.type === 'warning' ? '⚠' : '•'}
                    </span>
                    <span>{reason.text}</span>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Contenido positivo */}
          {(() => {
            const content = getContent(tooltipData);
            if (content.length === 0 && !tooltipData.shotType) return null;
            return (
              <div className="tooltip-action-content">
                <div className="tooltip-section-title">Contenido:</div>
                {/* Tipo de plano traducido */}
                <div className="tooltip-content-item">
                  <span className="content-icon">🎥</span>
                  <span>{SHOT_TYPE_LABELS[tooltipData.shotType] || tooltipData.shotType}</span>
                </div>
                {content.map((item, idx) => (
                  <div key={idx} className="tooltip-content-item">
                    <span className="content-icon">{item.icon}</span>
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Tip para takes repetidos */}
          {tooltipData.isRepeatedTake && (
            <div className="tooltip-tip">
              💡 Busca el segmento con ✓ para la mejor toma
            </div>
          )}

          {/* Tags priorizados */}
          {(() => {
            const tags = getPriorityTags(tooltipData.tags);
            if (tags.length === 0) return null;
            return (
              <div className="tooltip-action-tags">
                {tags.map((tag, idx) => (
                  <span key={idx} className="tooltip-tag-pill">{humanizeTag(tag)}</span>
                ))}
                {tooltipData.tags.length > 4 && (
                  <span className="tooltip-tag-more">+{tooltipData.tags.length - 4}</span>
                )}
              </div>
            );
          })()}
        </div>
      )}

      <style>{`
        .video-card-minimal {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 12px 16px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .video-card-minimal:hover {
          border-color: var(--border-hover);
          background: var(--bg-tertiary);
        }

        .video-card-minimal.selected {
          border-color: var(--tier-gold);
          background: var(--tier-gold-bg);
        }

        .video-card-row-1 {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 8px;
        }

        .video-card-checkbox {
          width: 20px;
          height: 20px;
          border: 2px solid var(--border);
          border-radius: 5px;
          flex-shrink: 0;
          transition: all 0.15s ease;
          position: relative;
        }

        .video-card-minimal.selected .video-card-checkbox {
          background: var(--tier-gold);
          border-color: var(--tier-gold);
        }

        .video-card-minimal.selected .video-card-checkbox::after {
          content: '';
          position: absolute;
          left: 6px;
          top: 2px;
          width: 5px;
          height: 10px;
          border: solid white;
          border-width: 0 2px 2px 0;
          transform: rotate(45deg);
        }

        .video-card-thumb {
          width: 48px;
          height: 32px;
          border-radius: 4px;
          object-fit: cover;
          flex-shrink: 0;
        }

        .mini-timeline {
          flex: 1;
          position: relative;
          height: 24px;
        }

        .mini-timeline-segments {
          display: flex;
          height: 100%;
          background: var(--bg-tertiary);
          border-radius: 4px;
          overflow: hidden;
        }

        .mini-timeline-segment {
          height: 100%;
          min-width: 2px;
          transition: opacity 0.15s ease;
          position: relative;
        }

        .mini-timeline-segment:hover {
          opacity: 0.8;
        }

        .mini-timeline-segment.gold {
          background: linear-gradient(180deg, var(--tier-gold) 0%, #9A7209 100%);
        }

        .mini-timeline-segment.silver {
          background: linear-gradient(180deg, var(--tier-silver) 0%, #5A6A7A 100%);
        }

        .mini-timeline-segment.bronze {
          background: linear-gradient(180deg, var(--tier-bronze) 0%, #6A4420 100%);
        }

        .mini-timeline-segment.discard {
          background: linear-gradient(180deg, #C0C0C0 0%, #A0A0A0 100%);
        }

        .mini-timeline-segment.garbage {
          background: linear-gradient(180deg, var(--tier-garbage) 0%, #7A3030 100%);
        }

        .mini-timeline-segment.key-moment {
          box-shadow: inset 0 0 0 2px var(--tier-gold);
        }

        .mini-timeline-segment.best-take {
          box-shadow: inset 0 0 0 2px var(--text-primary);
        }

        .mini-timeline-segment.repeated-take {
          opacity: 0.6;
        }

        .segment-indicator {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          font-size: 10px;
          line-height: 1;
        }

        .segment-indicator.key {
          color: #FFF;
          text-shadow: 0 0 2px rgba(0,0,0,0.6);
        }

        .segment-indicator.best {
          color: #FFF;
          text-shadow: 0 0 2px rgba(0,0,0,0.6);
        }

        .video-card-duration {
          font-size: 13px;
          font-weight: 500;
          color: var(--text-muted);
          min-width: 45px;
          text-align: right;
        }

        .video-card-row-2 {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-left: 32px;
        }

        .video-card-filename {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 50%;
        }

        .video-card-badges {
          display: flex;
          gap: 6px;
          flex-shrink: 0;
        }

        .badge {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 500;
        }

        .badge-key { background: var(--tier-gold-bg); color: var(--tier-gold); }
        .badge-takes { background: var(--blue-bg); color: var(--blue); }
        .badge-scenes { background: var(--bg-tertiary); color: var(--text-secondary); }
        .badge-faces {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .badge-faces:hover { background: var(--border); transform: scale(1.05); }
        .badge-faces.active { background: var(--accent); color: #FFF; }
        .badge-garbage { background: var(--tier-garbage-bg); color: var(--tier-garbage); }

        .video-card-usable {
          font-size: 13px;
          color: var(--text-muted);
        }

        /* ================ NUEVO TOOLTIP ORIENTADO A ACCIÓN ================ */
        .tooltip-action {
          position: fixed;
          transform: translate(-50%, -100%);
          background: var(--bg-secondary);
          color: var(--text-primary);
          border-radius: 12px;
          font-size: 13px;
          z-index: 1000;
          pointer-events: none;
          min-width: 220px;
          max-width: 280px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.15);
          overflow: hidden;
          border: 1px solid var(--border);
        }

        /* Header con acción */
        .tooltip-action-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          font-weight: 600;
          font-size: 12px;
          letter-spacing: 0.5px;
        }

        .tooltip-action-header.gold { background: var(--tier-gold); color: #FFF; }
        .tooltip-action-header.best-take { background: var(--green); color: #FFF; }
        .tooltip-action-header.key-moment { background: var(--tier-gold); color: #FFF; }
        .tooltip-action-header.silver { background: var(--tier-silver); color: #FFF; }
        .tooltip-action-header.bronze { background: var(--tier-bronze); color: #FFF; }
        .tooltip-action-header.discard { background: var(--border); color: var(--text-primary); }
        .tooltip-action-header.repeated { background: var(--border); color: var(--text-primary); }
        .tooltip-action-header.garbage { background: var(--tier-garbage); color: #FFF; }

        .tooltip-action-icon { font-size: 14px; }
        .tooltip-action-label { flex: 1; }

        /* Timecode */
        .tooltip-action-time {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 14px;
          background: var(--bg-tertiary);
          border-bottom: 1px solid var(--border);
        }

        .tooltip-timecode {
          font-family: 'SF Mono', Monaco, monospace;
          font-size: 11px;
          color: var(--text-muted);
        }

        .tooltip-duration-pill {
          background: var(--bg-tertiary);
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 11px;
          font-weight: 500;
          color: var(--text-secondary);
        }

        /* Secciones */
        .tooltip-action-reasons,
        .tooltip-action-content {
          padding: 10px 14px;
        }

        .tooltip-action-reasons {
          border-bottom: 1px solid var(--border);
        }

        .tooltip-section-title {
          font-size: 10px;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 6px;
        }

        /* Razones */
        .tooltip-reason {
          display: flex;
          align-items: flex-start;
          gap: 6px;
          font-size: 12px;
          margin-bottom: 4px;
          line-height: 1.4;
        }

        .tooltip-reason:last-child { margin-bottom: 0; }

        .reason-bullet {
          font-size: 10px;
          margin-top: 2px;
          flex-shrink: 0;
        }

        .tooltip-reason.good { color: var(--green); }
        .tooltip-reason.good .reason-bullet { color: var(--green); }

        .tooltip-reason.warning { color: var(--tier-gold); }
        .tooltip-reason.warning .reason-bullet { color: var(--tier-gold); }

        .tooltip-reason.bad { color: var(--red); }
        .tooltip-reason.bad .reason-bullet { color: var(--red); }

        .tooltip-reason.info { color: var(--text-muted); }
        .tooltip-reason.info .reason-bullet { color: var(--text-muted); }

        /* Contenido */
        .tooltip-content-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 4px;
        }

        .tooltip-content-item:last-child { margin-bottom: 0; }

        .content-icon {
          font-size: 12px;
          width: 16px;
          text-align: center;
        }

        /* Tip */
        .tooltip-tip {
          padding: 8px 14px;
          background: var(--bg-tertiary);
          font-size: 11px;
          color: var(--tier-gold);
          border-top: 1px solid var(--border);
        }

        /* Tags */
        .tooltip-action-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          padding: 8px 14px;
          background: var(--bg-tertiary);
          border-top: 1px solid var(--border);
        }

        .tooltip-tag-pill {
          background: var(--bg-tertiary);
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          color: var(--text-secondary);
        }

        .tooltip-tag-more {
          color: var(--text-muted);
          font-size: 10px;
          padding: 2px 4px;
        }

        /* Faces Panel */
        .faces-panel {
          margin-top: 12px;
          padding: 12px;
          background: var(--bg-tertiary);
          border-radius: 8px;
          border: 1px solid var(--border);
        }

        .faces-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }

        .faces-panel-title {
          font-size: 13px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .faces-panel-summary {
          font-size: 11px;
          color: var(--text-muted);
        }

        .faces-panel-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 8px;
        }

        .faces-segment-item {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 8px 10px;
          border-left: 3px solid var(--border);
        }

        .faces-segment-item.gold { border-left-color: var(--tier-gold); }
        .faces-segment-item.silver { border-left-color: var(--tier-silver); }
        .faces-segment-item.bronze { border-left-color: var(--tier-bronze); }

        .faces-segment-time {
          font-size: 11px;
          font-family: monospace;
          color: var(--text-muted);
          margin-bottom: 4px;
        }

        .faces-segment-info {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .faces-count {
          font-size: 12px;
          font-weight: 600;
          color: var(--text-secondary);
        }

        .faces-framing {
          font-size: 11px;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          padding: 1px 6px;
          border-radius: 3px;
        }

        .faces-more {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          color: var(--text-muted);
          padding: 8px;
          background: var(--bg-tertiary);
          border-radius: 6px;
        }
      `}</style>
    </div>
  );
}

export default VideoCard;
