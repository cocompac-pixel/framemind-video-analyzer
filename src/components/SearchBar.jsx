import { useState, useRef, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { Search, X, Clock, Sparkles, User, Star, Film, Trash2, Camera } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5050';

// Búsquedas predefinidas
const QUICK_SEARCHES = [
  { id: 'gold', label: 'Segmentos Gold', icon: Star, color: '#3B82F6', endpoint: '/api/find/gold' },
  { id: 'usable', label: 'Contenido Usable', icon: Sparkles, color: '#10B981', endpoint: '/api/find/usable' },
  { id: 'faces', label: 'Con Rostros', icon: User, color: '#7C3AED', endpoint: '/api/find/faces' },
  { id: 'interviews', label: 'Entrevistas', icon: Film, color: '#F59E0B', endpoint: '/api/find/interviews' },
  { id: 'static', label: 'Tomas Estáticas', icon: Camera, color: '#6366F1', endpoint: '/api/find/static' },
];

function SearchBar() {
  const {
    currentProjectId,
    analyzedVideos,
    searchQuery,
    setSearchQuery,
    showToast,
  } = useApp();

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [recentSearches, setRecentSearches] = useState([]);
  const [activeQuickSearch, setActiveQuickSearch] = useState(null);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  // Load recent searches from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('video-analyzer-recent-searches');
      if (saved) {
        setRecentSearches(JSON.parse(saved).slice(0, 5));
      }
    } catch (e) {
      console.error('Error loading recent searches:', e);
    }
  }, []);

  // Save recent search
  const saveRecentSearch = useCallback((query) => {
    if (!query.trim()) return;
    const updated = [query, ...recentSearches.filter(s => s !== query)].slice(0, 5);
    setRecentSearches(updated);
    try {
      localStorage.setItem('video-analyzer-recent-searches', JSON.stringify(updated));
    } catch (e) {
      console.error('Error saving recent searches:', e);
    }
  }, [recentSearches]);

  // Handle click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Execute quick search
  const executeQuickSearch = async (quickSearch) => {
    if (!currentProjectId) {
      showToast('Selecciona un proyecto primero');
      return;
    }

    setIsLoading(true);
    setActiveQuickSearch(quickSearch.id);

    try {
      const response = await fetch(`${API_BASE}${quickSearch.endpoint}?project_id=${currentProjectId}`);
      const data = await response.json();

      if (data.segments) {
        setSearchResults({
          type: 'quick',
          label: quickSearch.label,
          count: data.segments.length,
          segments: data.segments.slice(0, 10),
          totalDuration: data.segments.reduce((sum, s) => sum + (s.end_time - s.start_time), 0)
        });
        showToast(`${data.segments.length} segmentos encontrados`);
      }
    } catch (err) {
      console.error('Error executing quick search:', err);
      showToast('Error en la búsqueda');
    } finally {
      setIsLoading(false);
    }
  };

  // Execute text search
  const executeTextSearch = async (query) => {
    if (!query.trim() || !currentProjectId) return;

    saveRecentSearch(query);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/quick-search?project_id=${currentProjectId}&q=${encodeURIComponent(query)}`);
      const data = await response.json();

      if (data.segments) {
        setSearchResults({
          type: 'text',
          query: query,
          count: data.segments.length,
          segments: data.segments.slice(0, 10),
        });
      }
    } catch (err) {
      console.error('Error executing text search:', err);
      // Fallback to local search
      setSearchQuery(query);
    } finally {
      setIsLoading(false);
      setIsOpen(false);
    }
  };

  // Handle input change
  const handleInputChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    setActiveQuickSearch(null);
    setSearchResults(null);
    if (value) {
      setIsOpen(true);
    }
  };

  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      executeTextSearch(searchQuery);
    }
    if (e.key === 'Escape') {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  };

  // Clear search
  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
    setActiveQuickSearch(null);
    inputRef.current?.focus();
  };

  // Clear recent search
  const clearRecentSearch = (query, e) => {
    e.stopPropagation();
    const updated = recentSearches.filter(s => s !== query);
    setRecentSearches(updated);
    localStorage.setItem('video-analyzer-recent-searches', JSON.stringify(updated));
  };

  // Format duration
  const formatDuration = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  // Don't render if no analyzed videos
  if (analyzedVideos.length === 0) {
    return (
      <div className="search-box-simple">
        <Search size={16} className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Buscar videos..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          disabled
        />
        <style>{`
          .search-box-simple {
            position: relative;
            width: 240px;
            opacity: 0.5;
          }
          .search-box-simple .search-icon {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: #A1A1AA;
          }
          .search-box-simple .search-input {
            width: 100%;
            padding: 10px 12px 10px 38px;
            font-size: 14px;
            border: 1px solid #E4E4E7;
            border-radius: 8px;
            background: white;
            color: #18181B;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="search-bar-advanced" ref={dropdownRef}>
      <div className={`search-box ${isOpen ? 'focused' : ''} ${activeQuickSearch ? 'has-filter' : ''}`}>
        <Search size={16} className="search-icon" />
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder={activeQuickSearch ? QUICK_SEARCHES.find(q => q.id === activeQuickSearch)?.label : "Buscar en segmentos..."}
          value={searchQuery}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyPress}
        />
        {(searchQuery || activeQuickSearch) && (
          <button className="btn-clear" onClick={clearSearch}>
            <X size={16} />
          </button>
        )}
        {isLoading && <div className="search-spinner" />}
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="search-dropdown">
          {/* Quick searches */}
          <div className="dropdown-section">
            <div className="dropdown-section-title">Búsquedas rápidas</div>
            <div className="quick-searches">
              {QUICK_SEARCHES.map(qs => {
                const Icon = qs.icon;
                return (
                  <button
                    key={qs.id}
                    className={`quick-search-btn ${activeQuickSearch === qs.id ? 'active' : ''}`}
                    onClick={() => executeQuickSearch(qs)}
                    style={{ '--accent-color': qs.color }}
                  >
                    <Icon size={14} />
                    <span>{qs.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Recent searches */}
          {recentSearches.length > 0 && !searchQuery && (
            <div className="dropdown-section">
              <div className="dropdown-section-title">Búsquedas recientes</div>
              <div className="recent-searches">
                {recentSearches.map((query, idx) => (
                  <button
                    key={idx}
                    className="recent-search-item"
                    onClick={() => {
                      setSearchQuery(query);
                      executeTextSearch(query);
                    }}
                  >
                    <Clock size={14} />
                    <span>{query}</span>
                    <button
                      className="btn-remove-recent"
                      onClick={(e) => clearRecentSearch(query, e)}
                    >
                      <X size={12} />
                    </button>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Search results preview */}
          {searchResults && (
            <div className="dropdown-section">
              <div className="dropdown-section-title">
                {searchResults.type === 'quick' ? searchResults.label : `Resultados para "${searchResults.query}"`}
                <span className="results-count">{searchResults.count} encontrados</span>
              </div>
              {searchResults.totalDuration && (
                <div className="results-duration">
                  Duración total: {formatDuration(searchResults.totalDuration)}
                </div>
              )}
              <div className="results-preview">
                {searchResults.segments.slice(0, 5).map((seg, idx) => (
                  <div key={idx} className={`result-item tier-${seg.tier}`}>
                    <span className="result-time">
                      {formatDuration(seg.start_time)} - {formatDuration(seg.end_time)}
                    </span>
                    <span className="result-type">{seg.shot_type || 'N/A'}</span>
                    <span className={`result-tier ${seg.tier}`}>{seg.tier}</span>
                  </div>
                ))}
                {searchResults.count > 5 && (
                  <div className="results-more">
                    +{searchResults.count - 5} segmentos más
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Search hint */}
          {searchQuery && !searchResults && (
            <div className="search-hint">
              Presiona Enter para buscar "{searchQuery}"
            </div>
          )}
        </div>
      )}

      <style>{`
        .search-bar-advanced {
          position: relative;
          width: 320px;
        }

        .search-box {
          position: relative;
          display: flex;
          align-items: center;
        }

        .search-box .search-icon {
          position: absolute;
          left: 12px;
          color: var(--text-muted);
          z-index: 1;
        }

        .search-box .search-input {
          width: 100%;
          padding: 10px 40px 10px 38px;
          font-size: 14px;
          border: 1px solid var(--border);
          border-radius: 8px;
          background: var(--bg-secondary);
          color: var(--text-primary);
          transition: all 0.15s ease;
        }

        .search-box.focused .search-input {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(26, 26, 26, 0.08);
        }

        .search-box.has-filter .search-input {
          border-color: var(--green);
          background: var(--green-bg);
        }

        .search-box .search-input:focus {
          outline: none;
        }

        .search-box .search-input::placeholder {
          color: var(--text-muted);
        }

        .btn-clear {
          position: absolute;
          right: 10px;
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
        }

        .btn-clear:hover {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .search-spinner {
          position: absolute;
          right: 40px;
          width: 16px;
          height: 16px;
          border: 2px solid var(--border);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .search-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          left: 0;
          right: 0;
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
          box-shadow: 0 10px 40px rgba(0,0,0,0.12);
          z-index: 100;
          max-height: 400px;
          overflow-y: auto;
        }

        .dropdown-section {
          padding: 12px;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .dropdown-section:last-child {
          border-bottom: none;
        }

        .dropdown-section-title {
          font-size: 11px;
          font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .results-count {
          font-weight: 500;
          color: var(--accent);
          text-transform: none;
        }

        .results-duration {
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 8px;
        }

        .quick-searches {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .quick-search-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 10px;
          font-size: 12px;
          font-weight: 500;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          border: 1px solid transparent;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .quick-search-btn:hover {
          background: var(--border);
        }

        .quick-search-btn.active {
          background: var(--accent-color);
          color: white;
        }

        .quick-search-btn svg {
          opacity: 0.7;
        }

        .recent-searches {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .recent-search-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          font-size: 13px;
          color: var(--text-secondary);
          background: none;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          text-align: left;
          width: 100%;
        }

        .recent-search-item:hover {
          background: var(--bg-tertiary);
        }

        .recent-search-item span {
          flex: 1;
        }

        .recent-search-item svg {
          color: var(--text-muted);
        }

        .btn-remove-recent {
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: 2px;
          display: flex;
          opacity: 0;
        }

        .recent-search-item:hover .btn-remove-recent {
          opacity: 1;
        }

        .btn-remove-recent:hover {
          color: var(--red);
        }

        .results-preview {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .result-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 6px 8px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          font-size: 12px;
          border-left: 3px solid var(--border);
        }

        .result-item.tier-gold {
          border-left-color: var(--tier-gold);
        }

        .result-item.tier-silver {
          border-left-color: var(--tier-silver);
        }

        .result-time {
          font-family: monospace;
          color: var(--text-muted);
        }

        .result-type {
          flex: 1;
          color: var(--text-secondary);
        }

        .result-tier {
          font-size: 10px;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 3px;
          text-transform: uppercase;
        }

        .result-tier.gold {
          background: var(--tier-gold-bg);
          color: var(--tier-gold);
        }

        .result-tier.silver {
          background: var(--tier-silver-bg);
          color: var(--tier-silver);
        }

        .results-more {
          text-align: center;
          font-size: 12px;
          color: var(--text-muted);
          padding: 8px;
        }

        .search-hint {
          padding: 12px;
          text-align: center;
          font-size: 13px;
          color: var(--text-muted);
        }
      `}</style>
    </div>
  );
}

export default SearchBar;
