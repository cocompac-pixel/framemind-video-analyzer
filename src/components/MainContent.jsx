import { useState, useRef, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import VideoCard from './VideoCard';
import PendingVideoRow from './PendingVideoRow';
import VideosToolbar from './VideosToolbar';
import AdvancedFilters from './AdvancedFilters';
import ExportModal from './ExportModal';
import AnalysisConfigModal from './AnalysisConfigModal';
import { Upload, Play, Download, FolderPlus, Film } from 'lucide-react';

function MainContent() {
  const {
    currentProject,
    currentProjectId,
    pendingVideos,
    analyzedVideos,
    selectedVideos,
    analysisRunning,
    loading,
    hideGarbage,
    uploadFiles,
    startAnalysis,
    getFilteredVideos,
    createProject,
  } = useApp();

  const [showExportModal, setShowExportModal] = useState(false);
  const [showAnalysisConfig, setShowAnalysisConfig] = useState(false);
  const [exportMode, setExportMode] = useState('all'); // 'all' or 'selected'
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // Calculate stats
  const allSegments = analyzedVideos.flatMap(v => v.segments || []);

  const goldDuration = allSegments
    .filter(s => s.tier === 'gold')
    .reduce((sum, seg) => sum + (seg.end_time - seg.start_time), 0);

  const silverDuration = allSegments
    .filter(s => s.tier === 'silver')
    .reduce((sum, seg) => sum + (seg.end_time - seg.start_time), 0);

  // New stats
  const keyMomentsCount = allSegments.filter(s => s.is_key_moment).length;
  const bestTakesCount = allSegments.filter(s => s.is_best_take).length;
  const repeatedTakesCount = allSegments.filter(s => s.is_repeated_take).length;
  const garbageDuration = allSegments
    .filter(s => s.is_garbage || s.tier === 'garbage')
    .reduce((sum, seg) => sum + (seg.end_time - seg.start_time), 0);
  const facesCount = allSegments.filter(s => s.face_count > 0 || s.face_analysis?.has_faces).length;

  const formatDuration = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  // Drag and drop handlers
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files).filter(f =>
      f.type.startsWith('video/') || f.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)
    );
    if (files.length > 0) {
      uploadFiles(files);
    }
  }, [uploadFiles]);

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      uploadFiles(files);
    }
    e.target.value = '';
  };

  const openExportAll = () => {
    setExportMode('all');
    setShowExportModal(true);
  };

  const openExportSelected = () => {
    setExportMode('selected');
    setShowExportModal(true);
  };

  // Abrir modal de configuración de análisis
  const openAnalysisConfig = () => {
    setShowAnalysisConfig(true);
  };

  // Iniciar análisis con configuración
  const handleStartAnalysisWithConfig = (config) => {
    startAnalysis(config);
  };

  const videosToExport = exportMode === 'all'
    ? analyzedVideos
    : analyzedVideos.filter(v => selectedVideos.has(v.id));

  const filteredVideos = getFilteredVideos();

  // No project selected
  if (!currentProjectId) {
    return (
      <main className="main-content">
        <div className="empty-main">
          <div className="empty-icon">
            <Film size={64} strokeWidth={1} />
          </div>
          <h2 className="empty-title">Selecciona o crea un proyecto</h2>
          <p className="empty-desc">Usa el botón "Nuevo Proyecto" en la barra lateral para comenzar</p>
          <button className="btn-primary" onClick={() => createProject()}>
            <FolderPlus size={18} />
            Crear Proyecto
          </button>
        </div>

        <style>{`
          .main-content {
            flex: 1;
            margin-left: 280px;
            padding: 32px 40px;
            max-width: 1100px;
          }

          .empty-main {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: calc(100vh - 100px);
            text-align: center;
          }

          .empty-icon {
            color: #D4D4D8;
            margin-bottom: 24px;
          }

          .empty-title {
            font-size: 20px;
            font-weight: 600;
            color: #18181B;
            margin-bottom: 8px;
          }

          .empty-desc {
            font-size: 15px;
            color: #71717A;
            margin-bottom: 24px;
          }

          .btn-primary {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 10px;
            border: none;
            background: #18181B;
            color: white;
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .btn-primary:hover {
            background: #27272A;
          }
        `}</style>
      </main>
    );
  }

  return (
    <main
      className="main-content"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {isDragging && (
        <div className="drag-overlay">
          <div className="drag-content">
            <Upload size={48} />
            <span>Suelta los videos aquí</span>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
        </div>
      )}

      {/* Project header */}
      <div className="project-header">
        <div className="project-info">
          <h1 className="project-title">{currentProject?.name || 'Proyecto'}</h1>
          <div className="project-stats-inline">
            {analyzedVideos.length > 0 && (
              <>
                <div className="stat">
                  <span className="gold">●</span>
                  <strong>{formatDuration(goldDuration)}</strong>
                  <span>gold</span>
                </div>
                <div className="stat">
                  <span className="silver">●</span>
                  <strong>{formatDuration(silverDuration)}</strong>
                  <span>silver</span>
                </div>
                {keyMomentsCount > 0 && (
                  <div className="stat stat-key">
                    <span>★</span>
                    <strong>{keyMomentsCount}</strong>
                    <span>momento{keyMomentsCount !== 1 ? 's' : ''} clave</span>
                  </div>
                )}
                {bestTakesCount > 0 && (
                  <div className="stat stat-takes">
                    <span>✓</span>
                    <strong>{bestTakesCount}</strong>
                    <span>mejor{bestTakesCount !== 1 ? 'es' : ''} take{bestTakesCount !== 1 ? 's' : ''}</span>
                  </div>
                )}
                {repeatedTakesCount > 0 && (
                  <div className="stat stat-repeated">
                    <span>⟲</span>
                    <strong>-{repeatedTakesCount}</strong>
                    <span>repetido{repeatedTakesCount !== 1 ? 's' : ''}</span>
                  </div>
                )}
                {facesCount > 0 && (
                  <div className="stat stat-faces">
                    <span>👤</span>
                    <strong>{facesCount}</strong>
                    <span>con rostros</span>
                  </div>
                )}
                {garbageDuration > 0 && !hideGarbage && (
                  <div className="stat stat-garbage">
                    <span>🗑</span>
                    <strong>{formatDuration(garbageDuration)}</strong>
                    <span>basura</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="header-actions">
          <button
            className="btn-import"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={18} />
            Importar Videos
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />

          {selectedVideos.size > 0 && (
            <button className="btn-export-selection" onClick={openExportSelected}>
              <Download size={18} />
              Exportar selección
              <span className="count">{selectedVideos.size}</span>
            </button>
          )}

          {analyzedVideos.length > 0 && (
            <button className="btn-export" onClick={openExportAll}>
              <Download size={18} />
              Exportar todo
              <span className="count">{analyzedVideos.length}</span>
            </button>
          )}
        </div>
      </div>

      {/* Pending videos section with analyze button */}
      {pendingVideos.length > 0 && (
        <div className="pending-section">
          <div className="pending-header">
            <div>
              <div className="pending-title">Videos pendientes de análisis</div>
              <div className="pending-subtitle">{pendingVideos.length} video(s) listos</div>
            </div>
            <button
              className="btn-analyze"
              onClick={openAnalysisConfig}
              disabled={analysisRunning}
            >
              {analysisRunning ? (
                <>
                  <span className="spinner" />
                  Analizando...
                </>
              ) : (
                <>
                  <Play size={18} />
                  Analizar todos
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Videos section */}
      {(pendingVideos.length > 0 || analyzedVideos.length > 0) ? (
        <div className="videos-section">
          <VideosToolbar />
          <AdvancedFilters />

          <div className="videos-list">
            {filteredVideos.length === 0 ? (
              <div className="no-results">
                No se encontraron videos
              </div>
            ) : (
              filteredVideos.map(video => (
                video.type === 'pending' ? (
                  <PendingVideoRow key={video.id} video={video} />
                ) : (
                  <VideoCard key={video.id} video={video} hideGarbage={hideGarbage} />
                )
              ))
            )}
          </div>
        </div>
      ) : (
        <div className="empty-clips">
          <div className="empty-icon">
            <Upload size={40} strokeWidth={1.5} />
          </div>
          <h3>No hay videos en este proyecto</h3>
          <p>Arrastra videos aquí o usa el botón "Importar Videos"</p>
        </div>
      )}

      {/* Export modal */}
      <ExportModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        videosToExport={videosToExport}
      />

      {/* Analysis config modal */}
      <AnalysisConfigModal
        isOpen={showAnalysisConfig}
        onClose={() => setShowAnalysisConfig(false)}
        onStartAnalysis={handleStartAnalysisWithConfig}
        pendingCount={pendingVideos.length}
      />

      <style>{`
        .main-content {
          flex: 1;
          margin-left: 280px;
          padding: 32px 40px;
          max-width: 1100px;
          position: relative;
          min-height: 100vh;
        }

        .drag-overlay {
          position: fixed;
          top: 0;
          left: 280px;
          right: 0;
          bottom: 0;
          background: rgba(201, 162, 39, 0.1);
          border: 3px dashed var(--tier-gold);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 50;
        }

        .drag-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          color: var(--tier-gold);
          font-size: 18px;
          font-weight: 500;
        }

        .loading-overlay {
          position: fixed;
          top: 0;
          left: 280px;
          right: 0;
          bottom: 0;
          background: rgba(250, 250, 250, 0.9);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 40;
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--border);
          border-top-color: var(--tier-gold);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        /* Project header */
        .project-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 32px;
        }

        .project-title {
          font-size: 28px;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .project-stats-inline {
          display: flex;
          gap: 20px;
          font-size: 14px;
          color: var(--text-muted);
        }

        .project-stats-inline .stat {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .project-stats-inline .stat strong {
          color: var(--text-primary);
          font-weight: 600;
        }

        .project-stats-inline .gold {
          color: var(--tier-gold);
        }

        .project-stats-inline .silver {
          color: var(--tier-silver);
        }

        .project-stats-inline .stat-key span:first-child {
          color: var(--tier-gold);
        }

        .project-stats-inline .stat-takes span:first-child {
          color: var(--green);
        }

        .project-stats-inline .stat-repeated span:first-child {
          color: var(--text-muted);
        }

        .project-stats-inline .stat-repeated strong {
          color: var(--text-muted);
        }

        .project-stats-inline .stat-faces span:first-child {
          color: var(--text-secondary);
        }

        .project-stats-inline .stat-garbage span:first-child {
          color: var(--tier-garbage);
        }

        .project-stats-inline .stat-garbage strong {
          color: var(--tier-garbage);
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .btn-import {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 20px;
          font-size: 14px;
          font-weight: 600;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          color: var(--text-primary);
        }

        .btn-import:hover {
          background: var(--bg-tertiary);
          border-color: var(--border-hover);
        }

        .btn-import svg {
          opacity: 0.7;
        }

        .btn-export {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 20px;
          font-size: 14px;
          font-weight: 600;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s ease;
          border: none;
          background: var(--accent);
          color: #FFF;
          box-shadow: 0 2px 8px rgba(26, 26, 26, 0.15);
        }

        .btn-export:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(26, 26, 26, 0.25);
        }

        .btn-export .count {
          background: rgba(255,255,255,0.2);
          padding: 2px 8px;
          border-radius: 6px;
          font-size: 12px;
        }

        .btn-export-selection {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 20px;
          font-size: 14px;
          font-weight: 600;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s ease;
          background: transparent;
          color: var(--text-primary);
          border: 1px solid var(--accent);
        }

        .btn-export-selection:hover {
          background: var(--tier-gold-bg);
        }

        .btn-export-selection .count {
          background: var(--accent);
          color: #FFF;
          padding: 2px 8px;
          border-radius: 6px;
          font-size: 12px;
        }

        /* Pending section */
        .pending-section {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
          margin-bottom: 24px;
          overflow: hidden;
        }

        .pending-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 20px;
          background: var(--bg-tertiary);
          border-bottom: 1px solid var(--border);
        }

        .pending-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .pending-subtitle {
          font-size: 13px;
          color: var(--text-muted);
        }

        .btn-analyze {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          font-size: 14px;
          font-weight: 600;
          border-radius: 8px;
          border: none;
          background: var(--accent);
          color: #FFF;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .btn-analyze:hover:not(:disabled) {
          background: var(--accent-hover);
        }

        .btn-analyze:disabled {
          background: var(--border);
          cursor: not-allowed;
        }

        .btn-analyze .spinner {
          width: 16px;
          height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #FFF;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        /* Videos section */
        .videos-section {
          /* container */
        }

        .videos-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .no-results {
          text-align: center;
          padding: 40px;
          color: var(--text-muted);
        }

        /* Empty clips */
        .empty-clips {
          text-align: center;
          padding: 60px 20px;
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
        }

        .empty-clips .empty-icon {
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .empty-clips h3 {
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .empty-clips p {
          font-size: 14px;
          color: var(--text-muted);
          margin: 0;
        }
      `}</style>
    </main>
  );
}

export default MainContent;
