import { useState, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { X, Star, User, Film, Sparkles, Clock, Layers, FileVideo, Settings, ChevronDown, ChevronUp } from 'lucide-react';

// Configuración de tiers
const TIERS = [
  { id: 'gold', name: 'Gold', color: '#C9A227', description: 'Mejor material' },
  { id: 'silver', name: 'Silver', color: '#8A9A9A', description: 'Material usable' },
  { id: 'bronze', name: 'Bronze', color: '#8B6914', description: 'Revisión sugerida' },
  { id: 'discard', name: 'Descartar', color: '#6B3D3D', description: 'No recomendado' },
];

// Presets de exportación inteligentes
const EXPORT_PRESETS = [
  {
    id: 'best',
    name: 'Lo Mejor',
    icon: Star,
    color: '#C9A227',
    description: 'Solo segmentos gold + key moments',
    tiers: ['gold'],
    filters: { onlyKeyMoments: false, onlyBestTakes: true, excludeGarbage: true }
  },
  {
    id: 'usable',
    name: 'Todo Usable',
    icon: Sparkles,
    color: '#7A9A6D',
    description: 'Gold + Silver, excluye basura',
    tiers: ['gold', 'silver'],
    filters: { excludeGarbage: true }
  },
  {
    id: 'interviews',
    name: 'Entrevistas',
    icon: User,
    color: '#6B8A9A',
    description: 'Segmentos con rostros detectados',
    tiers: ['gold', 'silver'],
    filters: { onlyWithFaces: true, excludeGarbage: true }
  },
  {
    id: 'highlights',
    name: 'Highlights',
    icon: Film,
    color: '#D8CFBC',
    description: 'Solo momentos clave',
    tiers: ['gold', 'silver'],
    filters: { onlyKeyMoments: true, excludeGarbage: true }
  },
  {
    id: 'custom',
    name: 'Personalizado',
    icon: Settings,
    color: '#8A8578',
    description: 'Configura manualmente',
    tiers: ['gold', 'silver'],
    filters: {}
  },
];

function ExportModal({ isOpen, onClose, videosToExport }) {
  const { exportVideos, showToast } = useApp();

  // State
  const [activePreset, setActivePreset] = useState('usable');
  const [selectedTiers, setSelectedTiers] = useState({
    gold: true,
    silver: true,
    bronze: false,
    discard: false,
  });
  const [filters, setFilters] = useState({
    onlyKeyMoments: false,
    onlyBestTakes: false,
    onlyWithFaces: false,
    excludeGarbage: true,
    excludeRepeatedTakes: true,
  });
  const [trackMode, setTrackMode] = useState('multi');
  const [sortBy, setSortBy] = useState('time'); // 'time', 'tier', 'duration'
  const [handles, setHandles] = useState(2);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [namingPattern, setNamingPattern] = useState('video_segment'); // 'video_segment', 'tier_time', 'scene_take'

  // Calcular estadísticas detalladas
  const stats = useMemo(() => {
    const result = {
      byTier: { gold: { duration: 0, clips: 0 }, silver: { duration: 0, clips: 0 }, bronze: { duration: 0, clips: 0 }, discard: { duration: 0, clips: 0 } },
      keyMoments: { duration: 0, clips: 0 },
      bestTakes: { duration: 0, clips: 0 },
      withFaces: { duration: 0, clips: 0 },
      garbage: { duration: 0, clips: 0 },
      repeatedTakes: { duration: 0, clips: 0 },
      totalVideos: videosToExport.length,
      allSegments: [],
    };

    for (const video of videosToExport) {
      for (const seg of video.segments || []) {
        const tier = seg.tier || 'discard';
        const duration = (seg.end_time || 0) - (seg.start_time || 0);

        // Por tier
        if (result.byTier[tier]) {
          result.byTier[tier].duration += duration;
          result.byTier[tier].clips += 1;
        }

        // Key moments
        if (seg.is_key_moment) {
          result.keyMoments.duration += duration;
          result.keyMoments.clips += 1;
        }

        // Best takes
        if (seg.is_best_take) {
          result.bestTakes.duration += duration;
          result.bestTakes.clips += 1;
        }

        // With faces
        if (seg.face_count > 0 || seg.face_analysis?.has_faces) {
          result.withFaces.duration += duration;
          result.withFaces.clips += 1;
        }

        // Garbage
        if (seg.is_garbage || seg.tier === 'garbage') {
          result.garbage.duration += duration;
          result.garbage.clips += 1;
        }

        // Repeated takes
        if (seg.is_repeated_take) {
          result.repeatedTakes.duration += duration;
          result.repeatedTakes.clips += 1;
        }

        result.allSegments.push({ ...seg, videoName: video.filename });
      }
    }

    return result;
  }, [videosToExport]);

  // Calcular clips que se exportarán según configuración actual
  const exportPreview = useMemo(() => {
    let clips = stats.allSegments.filter(seg => {
      const tier = seg.tier || 'discard';

      // Filtrar por tier seleccionado
      if (!selectedTiers[tier]) return false;

      // Filtros adicionales
      if (filters.excludeGarbage && (seg.is_garbage || seg.tier === 'garbage')) return false;
      if (filters.excludeRepeatedTakes && seg.is_repeated_take) return false;
      if (filters.onlyKeyMoments && !seg.is_key_moment) return false;
      if (filters.onlyBestTakes && !seg.is_best_take && stats.bestTakes.clips > 0) return false;
      if (filters.onlyWithFaces && !(seg.face_count > 0 || seg.face_analysis?.has_faces)) return false;

      return true;
    });

    const totalDuration = clips.reduce((sum, seg) => sum + ((seg.end_time || 0) - (seg.start_time || 0)), 0);
    const tierBreakdown = {};

    for (const tier of ['gold', 'silver', 'bronze', 'discard']) {
      const tierClips = clips.filter(s => (s.tier || 'discard') === tier);
      tierBreakdown[tier] = {
        clips: tierClips.length,
        duration: tierClips.reduce((sum, s) => sum + ((s.end_time || 0) - (s.start_time || 0)), 0)
      };
    }

    return {
      clips: clips.length,
      totalDuration,
      tierBreakdown,
      videos: new Set(clips.map(c => c.videoName)).size
    };
  }, [stats, selectedTiers, filters]);

  // Aplicar preset
  const applyPreset = (presetId) => {
    const preset = EXPORT_PRESETS.find(p => p.id === presetId);
    if (!preset) return;

    setActivePreset(presetId);

    if (presetId !== 'custom') {
      // Configurar tiers
      setSelectedTiers({
        gold: preset.tiers.includes('gold'),
        silver: preset.tiers.includes('silver'),
        bronze: preset.tiers.includes('bronze'),
        discard: preset.tiers.includes('discard'),
      });

      // Configurar filtros
      setFilters({
        onlyKeyMoments: preset.filters.onlyKeyMoments || false,
        onlyBestTakes: preset.filters.onlyBestTakes || false,
        onlyWithFaces: preset.filters.onlyWithFaces || false,
        excludeGarbage: preset.filters.excludeGarbage !== false,
        excludeRepeatedTakes: preset.filters.excludeRepeatedTakes !== false,
      });
    }
  };

  // Toggle tier (cambia a custom)
  const toggleTier = (tierId) => {
    setActivePreset('custom');
    setSelectedTiers(prev => ({
      ...prev,
      [tierId]: !prev[tierId],
    }));
  };

  // Toggle filter (cambia a custom)
  const toggleFilter = (filterKey) => {
    setActivePreset('custom');
    setFilters(prev => ({
      ...prev,
      [filterKey]: !prev[filterKey],
    }));
  };

  // Formatear duración
  const formatDuration = (seconds) => {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins >= 60) {
      const hours = Math.floor(mins / 60);
      const remainMins = mins % 60;
      return `${hours}h ${remainMins}m`;
    }
    return `${mins}m ${secs}s`;
  };

  // Exportar
  const handleExport = async () => {
    if (exportPreview.clips === 0) {
      showToast('No hay clips para exportar con la configuración actual');
      return;
    }

    const tiersToExport = Object.entries(selectedTiers)
      .filter(([_, selected]) => selected)
      .map(([tier]) => tier);

    const options = {
      tiers: tiersToExport,
      track_mode: trackMode,
      organization: trackMode === 'multi' ? 'by_tier' : 'sequence',
      sort_by: sortBy,
      handles: handles,
      media_folder: '/Users/danielazpe/Movies',
      // Filtros avanzados
      filters: {
        only_key_moments: filters.onlyKeyMoments,
        only_best_takes: filters.onlyBestTakes,
        only_with_faces: filters.onlyWithFaces,
        exclude_garbage: filters.excludeGarbage,
        exclude_repeated_takes: filters.excludeRepeatedTakes,
      },
      naming_pattern: namingPattern,
    };

    const downloadUrl = await exportVideos(videosToExport, options);
    if (downloadUrl) {
      window.location.href = `http://127.0.0.1:5050${downloadUrl}`;
      showToast(`Exportando ${exportPreview.clips} clips...`);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="export-modal-smart" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Exportar a Premiere</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Presets rápidos */}
          <div className="section">
            <label className="section-label">Exportación rápida</label>
            <div className="presets-grid">
              {EXPORT_PRESETS.map(preset => {
                const Icon = preset.icon;
                const isActive = activePreset === preset.id;
                return (
                  <button
                    key={preset.id}
                    className={`preset-btn ${isActive ? 'active' : ''}`}
                    onClick={() => applyPreset(preset.id)}
                    style={{ '--preset-color': preset.color }}
                  >
                    <Icon size={18} />
                    <span className="preset-name">{preset.name}</span>
                    <span className="preset-desc">{preset.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tier selection visual */}
          <div className="section">
            <label className="section-label">Tiers a exportar</label>
            <div className="tier-chips">
              {TIERS.map(tier => {
                const tierStats = stats.byTier[tier.id];
                const isSelected = selectedTiers[tier.id];
                const hasDuration = tierStats.duration > 0;

                return (
                  <button
                    key={tier.id}
                    className={`tier-chip ${isSelected ? 'selected' : ''} ${!hasDuration ? 'empty' : ''}`}
                    onClick={() => hasDuration && toggleTier(tier.id)}
                    disabled={!hasDuration}
                    style={{ '--tier-color': tier.color }}
                  >
                    <span className="tier-dot" style={{ background: tier.color }}></span>
                    <div className="tier-info">
                      <span className="tier-name">{tier.name}</span>
                      <span className="tier-stats">{tierStats.clips} clips • {formatDuration(tierStats.duration)}</span>
                    </div>
                    {isSelected && <span className="tier-check">✓</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Filtros inteligentes */}
          <div className="section">
            <label className="section-label">Filtros inteligentes</label>
            <div className="smart-filters">
              <button
                className={`smart-filter ${filters.onlyKeyMoments ? 'active' : ''}`}
                onClick={() => toggleFilter('onlyKeyMoments')}
                disabled={stats.keyMoments.clips === 0}
              >
                <Star size={14} />
                <span>Solo momentos clave</span>
                <span className="filter-count">{stats.keyMoments.clips}</span>
              </button>

              <button
                className={`smart-filter ${filters.onlyWithFaces ? 'active' : ''}`}
                onClick={() => toggleFilter('onlyWithFaces')}
                disabled={stats.withFaces.clips === 0}
              >
                <User size={14} />
                <span>Solo con rostros</span>
                <span className="filter-count">{stats.withFaces.clips}</span>
              </button>

              <button
                className={`smart-filter ${filters.excludeRepeatedTakes ? 'active' : ''}`}
                onClick={() => toggleFilter('excludeRepeatedTakes')}
                disabled={stats.repeatedTakes.clips === 0}
              >
                <Layers size={14} />
                <span>Excluir repetidos</span>
                <span className="filter-count">-{stats.repeatedTakes.clips}</span>
              </button>

              <button
                className={`smart-filter warning ${filters.excludeGarbage ? 'active' : ''}`}
                onClick={() => toggleFilter('excludeGarbage')}
                disabled={stats.garbage.clips === 0}
              >
                <X size={14} />
                <span>Excluir basura</span>
                <span className="filter-count">-{stats.garbage.clips}</span>
              </button>
            </div>
          </div>

          {/* Preview de exportación */}
          <div className="export-preview">
            <div className="preview-header">
              <FileVideo size={18} />
              <span>Vista previa de exportación</span>
            </div>
            <div className="preview-stats">
              <div className="preview-main">
                <span className="preview-clips">{exportPreview.clips}</span>
                <span className="preview-label">clips</span>
              </div>
              <div className="preview-duration">
                <Clock size={14} />
                <span>{formatDuration(exportPreview.totalDuration)}</span>
              </div>
              <div className="preview-videos">
                de {exportPreview.videos} video{exportPreview.videos !== 1 ? 's' : ''}
              </div>
            </div>
            {exportPreview.clips > 0 && (
              <div className="preview-breakdown">
                {Object.entries(exportPreview.tierBreakdown).map(([tier, data]) => {
                  if (data.clips === 0) return null;
                  const tierInfo = TIERS.find(t => t.id === tier);
                  return (
                    <div key={tier} className="breakdown-item">
                      <span className="breakdown-dot" style={{ background: tierInfo?.color }}></span>
                      <span className="breakdown-tier">{tierInfo?.name}</span>
                      <span className="breakdown-value">{data.clips} ({formatDuration(data.duration)})</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Opciones avanzadas colapsables */}
          <div className="advanced-section">
            <button
              className="advanced-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <Settings size={16} />
              <span>Opciones avanzadas</span>
              {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showAdvanced && (
              <div className="advanced-content">
                {/* Track mode */}
                <div className="advanced-row">
                  <label>Organización</label>
                  <div className="track-buttons">
                    <button
                      className={trackMode === 'single' ? 'active' : ''}
                      onClick={() => setTrackMode('single')}
                    >
                      Track único
                    </button>
                    <button
                      className={trackMode === 'multi' ? 'active' : ''}
                      onClick={() => setTrackMode('multi')}
                    >
                      Multitrack
                    </button>
                  </div>
                </div>

                {/* Sort by */}
                <div className="advanced-row">
                  <label>Ordenar por</label>
                  <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="time">Tiempo original</option>
                    <option value="tier">Por tier (gold primero)</option>
                    <option value="duration">Por duración</option>
                    <option value="score">Por score</option>
                  </select>
                </div>

                {/* Handles */}
                <div className="advanced-row">
                  <label>Handles (frames)</label>
                  <div className="handles-input">
                    <button onClick={() => setHandles(Math.max(0, handles - 1))}>-</button>
                    <span>{handles}</span>
                    <button onClick={() => setHandles(Math.min(30, handles + 1))}>+</button>
                  </div>
                </div>

                {/* Naming pattern */}
                <div className="advanced-row">
                  <label>Nombrar clips</label>
                  <select value={namingPattern} onChange={(e) => setNamingPattern(e.target.value)}>
                    <option value="video_segment">Video_Segmento</option>
                    <option value="tier_time">Tier_Tiempo</option>
                    <option value="scene_take">Escena_Take</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn-export"
            onClick={handleExport}
            disabled={exportPreview.clips === 0}
          >
            Exportar {exportPreview.clips} clips
          </button>
        </div>

        <style>{`
          .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.3);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
          }

          .export-modal-smart {
            background: var(--bg-secondary);
            border-radius: 16px;
            width: 100%;
            max-width: 560px;
            max-height: 90vh;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border);
          }

          .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
          }

          .modal-header h2 {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
          }

          .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 8px;
            border-radius: 8px;
            display: flex;
          }

          .modal-close:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
          }

          .modal-body {
            padding: 20px 24px;
            overflow-y: auto;
            flex: 1;
          }

          .section {
            margin-bottom: 20px;
          }

          .section-label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
          }

          /* Presets grid */
          .presets-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
          }

          .preset-btn {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            padding: 12px 8px;
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: center;
          }

          .preset-btn:hover {
            border-color: var(--preset-color);
            background: var(--bg-primary);
          }

          .preset-btn.active {
            border-color: var(--preset-color);
            background: var(--bg-secondary);
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
          }

          .preset-btn.active svg {
            color: var(--preset-color);
          }

          .preset-btn svg {
            color: var(--text-muted);
          }

          .preset-name {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-primary);
          }

          .preset-desc {
            font-size: 9px;
            color: var(--text-muted);
            line-height: 1.2;
          }

          /* Tier chips */
          .tier-chips {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
          }

          .tier-chip {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: left;
          }

          .tier-chip:hover:not(:disabled) {
            border-color: var(--tier-color);
          }

          .tier-chip.selected {
            border-color: var(--tier-color);
            background: var(--bg-primary);
          }

          .tier-chip.empty {
            opacity: 0.4;
            cursor: not-allowed;
          }

          .tier-dot {
            width: 12px;
            height: 12px;
            border-radius: 4px;
            flex-shrink: 0;
          }

          .tier-info {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 2px;
          }

          .tier-name {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
          }

          .tier-stats {
            font-size: 11px;
            color: var(--text-muted);
          }

          .tier-check {
            color: var(--tier-color);
            font-weight: bold;
          }

          /* Smart filters */
          .smart-filters {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
          }

          .smart-filter {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            font-size: 12px;
            color: var(--text-secondary);
            background: var(--bg-tertiary);
            border: 1px solid transparent;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .smart-filter:hover:not(:disabled) {
            background: var(--bg-primary);
          }

          .smart-filter.active {
            background: var(--tier-gold-bg);
            color: var(--tier-gold);
            border-color: var(--tier-gold);
          }

          .smart-filter.warning.active {
            background: var(--tier-garbage-bg);
            color: var(--tier-garbage);
            border-color: var(--tier-garbage);
          }

          .smart-filter:disabled {
            opacity: 0.4;
            cursor: not-allowed;
          }

          .filter-count {
            font-weight: 600;
            font-size: 11px;
            background: rgba(0,0,0,0.06);
            padding: 1px 5px;
            border-radius: 3px;
          }

          .smart-filter.active .filter-count {
            background: rgba(0,0,0,0.1);
          }

          /* Export preview */
          .export-preview {
            background: linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%);
            border-radius: 12px;
            padding: 16px;
            color: #FFFFFF;
            border: none;
          }

          .preview-header {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: #9A9A9A;
            margin-bottom: 12px;
          }

          .preview-stats {
            display: flex;
            align-items: baseline;
            gap: 16px;
            margin-bottom: 12px;
          }

          .preview-main {
            display: flex;
            align-items: baseline;
            gap: 6px;
          }

          .preview-clips {
            font-size: 32px;
            font-weight: 700;
            color: #FFFFFF;
          }

          .preview-label {
            font-size: 14px;
            color: #9A9A9A;
          }

          .preview-duration {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 14px;
            color: #9A9A9A;
          }

          .preview-videos {
            font-size: 13px;
            color: #7A7A7A;
          }

          .preview-breakdown {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding-top: 12px;
            border-top: 1px solid #3A3A3A;
          }

          .breakdown-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
          }

          .breakdown-dot {
            width: 8px;
            height: 8px;
            border-radius: 2px;
          }

          .breakdown-tier {
            color: #9A9A9A;
          }

          .breakdown-value {
            color: #E5E5E5;
          }

          /* Advanced section */
          .advanced-section {
            margin-top: 16px;
            border-top: 1px solid var(--border);
            padding-top: 16px;
          }

          .advanced-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            width: 100%;
            padding: 10px;
            background: none;
            border: none;
            font-size: 13px;
            color: var(--text-muted);
            cursor: pointer;
            border-radius: 8px;
          }

          .advanced-toggle:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
          }

          .advanced-toggle span {
            flex: 1;
            text-align: left;
          }

          .advanced-content {
            padding: 12px 0;
          }

          .advanced-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 0;
          }

          .advanced-row label {
            font-size: 13px;
            color: var(--text-secondary);
          }

          .advanced-row select {
            padding: 6px 10px;
            font-size: 13px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-tertiary);
            color: var(--text-primary);
          }

          .track-buttons {
            display: flex;
            gap: 4px;
          }

          .track-buttons button {
            padding: 6px 12px;
            font-size: 12px;
            border: 1px solid var(--border);
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border-radius: 6px;
            cursor: pointer;
          }

          .track-buttons button.active {
            background: var(--accent);
            color: #FFFFFF;
            border-color: var(--accent);
          }

          .handles-input {
            display: flex;
            align-items: center;
            gap: 8px;
          }

          .handles-input button {
            width: 28px;
            height: 28px;
            border: 1px solid var(--border);
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
          }

          .handles-input button:hover {
            background: var(--bg-primary);
          }

          .handles-input span {
            width: 30px;
            text-align: center;
            font-weight: 600;
            color: var(--text-primary);
          }

          /* Footer */
          .modal-footer {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            padding: 16px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg-tertiary);
            flex-shrink: 0;
          }

          .btn-cancel {
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-muted);
            cursor: pointer;
          }

          .btn-cancel:hover {
            border-color: var(--border-hover);
            color: var(--text-primary);
          }

          .btn-export {
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 10px;
            border: none;
            background: var(--accent);
            color: #FFFFFF;
            cursor: pointer;
          }

          .btn-export:hover:not(:disabled) {
            background: var(--accent-hover);
          }

          .btn-export:disabled {
            background: var(--border);
            color: var(--text-muted);
            cursor: not-allowed;
          }
        `}</style>
      </div>
    </div>
  );
}

export default ExportModal;
