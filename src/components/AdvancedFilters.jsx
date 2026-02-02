import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Tag, User, Star, Layers, X, ChevronDown, ChevronUp } from 'lucide-react';

function AdvancedFilters() {
  const {
    analyzedVideos,
    activeTagFilters,
    showOnlyWithFaces,
    showOnlyKeyMoments,
    selectedSceneGroup,
    getAllTags,
    getAllSceneGroups,
    toggleTagFilter,
    setShowOnlyWithFaces,
    setShowOnlyKeyMoments,
    setSelectedSceneGroup,
    clearAdvancedFilters,
  } = useApp();

  const [isExpanded, setIsExpanded] = useState(false);
  const [showAllTags, setShowAllTags] = useState(false);

  // Don't render if no analyzed videos
  if (analyzedVideos.length === 0) return null;

  const allTags = getAllTags();
  const sceneGroups = getAllSceneGroups();

  // Count active filters
  const activeFiltersCount = activeTagFilters.size +
    (showOnlyWithFaces ? 1 : 0) +
    (showOnlyKeyMoments ? 1 : 0) +
    (selectedSceneGroup !== null ? 1 : 0);

  const displayedTags = showAllTags ? allTags : allTags.slice(0, 12);
  const hasMoreTags = allTags.length > 12;

  return (
    <div className="advanced-filters">
      {/* Header row */}
      <div className="filters-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="filters-header-left">
          <Tag size={16} />
          <span>Filtros Avanzados</span>
          {activeFiltersCount > 0 && (
            <span className="active-count">{activeFiltersCount} activo{activeFiltersCount !== 1 ? 's' : ''}</span>
          )}
        </div>
        <div className="filters-header-right">
          {activeFiltersCount > 0 && (
            <button
              className="btn-clear-filters"
              onClick={(e) => {
                e.stopPropagation();
                clearAdvancedFilters();
              }}
            >
              <X size={14} />
              Limpiar
            </button>
          )}
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="filters-content">
          {/* Quick filters row */}
          <div className="quick-filters">
            <button
              className={`quick-filter ${showOnlyKeyMoments ? 'active' : ''}`}
              onClick={() => setShowOnlyKeyMoments(!showOnlyKeyMoments)}
            >
              <Star size={14} />
              Solo momentos clave
            </button>
            <button
              className={`quick-filter ${showOnlyWithFaces ? 'active' : ''}`}
              onClick={() => setShowOnlyWithFaces(!showOnlyWithFaces)}
            >
              <User size={14} />
              Con rostros
            </button>
          </div>

          {/* Scene groups */}
          {sceneGroups.length > 0 && (
            <div className="filter-section">
              <div className="filter-section-title">
                <Layers size={14} />
                Grupos de escena
              </div>
              <div className="scene-groups">
                <button
                  className={`scene-group-btn ${selectedSceneGroup === null ? 'active' : ''}`}
                  onClick={() => setSelectedSceneGroup(null)}
                >
                  Todos
                </button>
                {sceneGroups.slice(0, 8).map(group => (
                  <button
                    key={group.id}
                    className={`scene-group-btn ${selectedSceneGroup === group.id ? 'active' : ''}`}
                    onClick={() => setSelectedSceneGroup(group.id === selectedSceneGroup ? null : group.id)}
                    title={`${group.segmentCount} segmentos en ${group.videoCount} video(s)`}
                  >
                    Escena {group.id + 1}
                    <span className="group-count">{group.segmentCount}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {allTags.length > 0 && (
            <div className="filter-section">
              <div className="filter-section-title">
                <Tag size={14} />
                Tags detectados
              </div>
              <div className="tags-list">
                {displayedTags.map(tag => (
                  <button
                    key={tag}
                    className={`tag-btn ${activeTagFilters.has(tag) ? 'active' : ''}`}
                    onClick={() => toggleTagFilter(tag)}
                  >
                    {tag}
                  </button>
                ))}
                {hasMoreTags && (
                  <button
                    className="tag-btn show-more"
                    onClick={() => setShowAllTags(!showAllTags)}
                  >
                    {showAllTags ? 'Mostrar menos' : `+${allTags.length - 12} más`}
                  </button>
                )}
              </div>
            </div>
          )}

          {allTags.length === 0 && sceneGroups.length === 0 && (
            <div className="no-filters-available">
              No hay tags ni grupos de escena disponibles.
              Analiza más videos para obtener filtros avanzados.
            </div>
          )}
        </div>
      )}

      <style>{`
        .advanced-filters {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 10px;
          margin-bottom: 16px;
          overflow: hidden;
        }

        .filters-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 14px;
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .filters-header:hover {
          background: var(--bg-primary);
        }

        .filters-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-secondary);
        }

        .filters-header-left svg {
          color: var(--text-muted);
        }

        .active-count {
          background: var(--accent);
          color: white;
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 11px;
          font-weight: 600;
        }

        .filters-header-right {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--text-muted);
        }

        .btn-clear-filters {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          font-size: 12px;
          color: var(--red);
          background: var(--red-bg);
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }

        .btn-clear-filters:hover {
          filter: brightness(0.95);
        }

        .filters-content {
          border-top: 1px solid var(--border);
          padding: 14px;
        }

        .quick-filters {
          display: flex;
          gap: 8px;
          margin-bottom: 14px;
        }

        .quick-filter {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          font-size: 12px;
          font-weight: 500;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          border: 1px solid transparent;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .quick-filter:hover {
          background: var(--border);
        }

        .quick-filter.active {
          background: var(--blue-bg);
          color: var(--blue);
          border-color: var(--blue);
        }

        .filter-section {
          margin-bottom: 14px;
        }

        .filter-section:last-child {
          margin-bottom: 0;
        }

        .filter-section-title {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
        }

        .filter-section-title svg {
          color: var(--text-muted);
        }

        .scene-groups {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .scene-group-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 5px 10px;
          font-size: 12px;
          font-weight: 500;
          color: var(--text-secondary);
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .scene-group-btn:hover {
          border-color: var(--border-hover);
          background: var(--bg-primary);
        }

        .scene-group-btn.active {
          background: var(--tier-silver-bg);
          color: var(--tier-silver);
          border-color: var(--tier-silver);
        }

        .group-count {
          background: rgba(0,0,0,0.06);
          padding: 1px 5px;
          border-radius: 3px;
          font-size: 10px;
        }

        .scene-group-btn.active .group-count {
          background: rgba(107, 123, 140, 0.2);
        }

        .tags-list {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .tag-btn {
          padding: 4px 10px;
          font-size: 12px;
          font-weight: 500;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          border: 1px solid transparent;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .tag-btn:hover {
          background: var(--border);
        }

        .tag-btn.active {
          background: var(--tier-gold-bg);
          color: var(--tier-gold);
          border-color: var(--tier-gold);
        }

        .tag-btn.show-more {
          color: var(--blue);
          background: var(--blue-bg);
        }

        .tag-btn.show-more:hover {
          filter: brightness(0.95);
        }

        .no-filters-available {
          text-align: center;
          padding: 20px;
          color: var(--text-muted);
          font-size: 13px;
        }
      `}</style>
    </div>
  );
}

export default AdvancedFilters;
