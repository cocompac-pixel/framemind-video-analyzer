import { useApp } from '../context/AppContext';
import { Eye, EyeOff } from 'lucide-react';
import SearchBar from './SearchBar';

function VideosToolbar() {
  const {
    pendingVideos,
    analyzedVideos,
    selectedVideos,
    currentFilter,
    hideGarbage,
    setCurrentFilter,
    setHideGarbage,
    toggleSelectAll,
  } = useApp();

  const totalCount = pendingVideos.length + analyzedVideos.length;
  const pendingCount = pendingVideos.length;
  const analyzedCount = analyzedVideos.length;

  return (
    <div className="videos-toolbar">
      <div className="toolbar-left">
        <div className="filter-pills">
          <button
            className={`filter-pill ${currentFilter === 'all' ? 'active' : ''}`}
            onClick={() => setCurrentFilter('all')}
          >
            Todos
            <span className="pill-count">{totalCount}</span>
          </button>
          <button
            className={`filter-pill ${currentFilter === 'pending' ? 'active' : ''}`}
            onClick={() => setCurrentFilter('pending')}
          >
            Pendientes
            <span className="pill-count">{pendingCount}</span>
          </button>
          <button
            className={`filter-pill ${currentFilter === 'analyzed' ? 'active' : ''}`}
            onClick={() => setCurrentFilter('analyzed')}
          >
            Analizados
            <span className="pill-count">{analyzedCount}</span>
          </button>
        </div>

        {analyzedVideos.length > 0 && (
          <div className="selection-info">
            <span>
              <strong>{selectedVideos.size}</strong> de {analyzedCount} seleccionados
            </span>
            <button className="btn-select-all" onClick={toggleSelectAll}>
              {selectedVideos.size === analyzedCount ? 'Deseleccionar todo' : 'Seleccionar todo'}
            </button>
          </div>
        )}
      </div>

      <div className="toolbar-right">
        {analyzedVideos.length > 0 && (
          <button
            className={`toggle-garbage ${hideGarbage ? 'active' : ''}`}
            onClick={() => setHideGarbage(!hideGarbage)}
            title={hideGarbage ? 'Mostrando solo contenido usable' : 'Mostrando todo incluyendo basura'}
          >
            {hideGarbage ? <EyeOff size={16} /> : <Eye size={16} />}
            <span>{hideGarbage ? 'Basura oculta' : 'Ocultar basura'}</span>
          </button>
        )}
        <SearchBar />
      </div>

      <style>{`
        .videos-toolbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          margin-bottom: 20px;
          flex-wrap: wrap;
        }

        .toolbar-left {
          display: flex;
          align-items: center;
          gap: 24px;
          flex-wrap: wrap;
        }

        .toolbar-right {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .filter-pills {
          display: flex;
          gap: 8px;
        }

        .filter-pill {
          padding: 8px 16px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-muted);
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 20px;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .filter-pill:hover {
          border-color: var(--border-hover);
        }

        .filter-pill.active {
          background: var(--accent);
          color: white;
          border-color: var(--accent);
        }

        .pill-count {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 20px;
          height: 20px;
          padding: 0 6px;
          font-size: 11px;
          font-weight: 600;
          background: rgba(0,0,0,0.08);
          border-radius: 10px;
        }

        .filter-pill.active .pill-count {
          background: rgba(255,255,255,0.25);
        }

        .selection-info {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 14px;
          color: var(--text-muted);
        }

        .selection-info strong {
          color: var(--text-primary);
        }

        .btn-select-all {
          font-size: 13px;
          color: var(--text-muted);
          background: none;
          border: none;
          cursor: pointer;
          text-decoration: underline;
          padding: 0;
        }

        .btn-select-all:hover {
          color: var(--text-primary);
        }

        .toggle-garbage {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-muted);
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .toggle-garbage:hover {
          border-color: var(--border-hover);
          background: var(--bg-tertiary);
        }

        .toggle-garbage.active {
          background: var(--tier-garbage-bg);
          border-color: var(--tier-garbage);
          color: var(--tier-garbage);
        }

        .toggle-garbage.active:hover {
          background: var(--tier-garbage-bg);
          filter: brightness(0.95);
        }
      `}</style>
    </div>
  );
}

export default VideosToolbar;
