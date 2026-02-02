import { Film, X, Trash2 } from 'lucide-react';

function VideoList({ videos, onDelete, onClear }) {
  if (videos.length === 0) {
    return (
      <div className="empty-state">
        <p>No hay videos cargados</p>
        <style>{`
          .empty-state {
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.9em;
          }
        `}</style>
      </div>
    );
  }

  const formatSize = (mb) => {
    if (mb >= 1000) {
      return `${(mb / 1000).toFixed(1)} GB`;
    }
    return `${mb.toFixed(1)} MB`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="video-list-container">
      <div className="video-list-header">
        <span className="count">{videos.length} video{videos.length !== 1 ? 's' : ''}</span>
        {videos.length > 0 && (
          <button className="clear-btn" onClick={onClear} title="Limpiar lista">
            <Trash2 size={14} />
            Limpiar
          </button>
        )}
      </div>

      <div className="video-list">
        {videos.map((video) => (
          <div key={video.name} className="video-item fade-in">
            <div className="video-info">
              <div className="video-thumbnail">
                {video.thumbnail ? (
                  <img
                    src={`http://127.0.0.1:5050/thumbnails/${video.thumbnail}`}
                    alt={video.name}
                  />
                ) : (
                  <Film size={24} />
                )}
              </div>
              <div className="video-details">
                <span className="video-name truncate" title={video.name}>
                  {video.name}
                </span>
                <span className="video-meta">
                  {formatSize(video.size_mb)}
                  {video.duration && ` • ${formatDuration(video.duration)}`}
                </span>
              </div>
            </div>
            <button
              className="delete-btn"
              onClick={() => onDelete(video.name)}
              title="Eliminar"
            >
              <X size={18} />
            </button>
          </div>
        ))}
      </div>

      <style>{`
        .video-list-container {
          display: flex;
          flex-direction: column;
        }

        .video-list-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          padding: 0 4px;
        }

        .video-list-header .count {
          font-size: 0.85em;
          color: var(--text-secondary);
        }

        .clear-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          background: transparent;
          border: none;
          color: var(--error);
          font-size: 0.8em;
          cursor: pointer;
          padding: 6px 10px;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
          opacity: 0.7;
        }

        .clear-btn:hover {
          opacity: 1;
          background: rgba(255, 107, 107, 0.1);
        }

        .video-list {
          max-height: 300px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .video-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
        }

        .video-item:hover {
          background: rgba(0, 0, 0, 0.3);
        }

        .video-info {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 1;
          min-width: 0;
        }

        .video-thumbnail {
          width: 48px;
          height: 32px;
          border-radius: 4px;
          overflow: hidden;
          background: rgba(255, 255, 255, 0.05);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          color: var(--text-muted);
        }

        .video-thumbnail img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .video-details {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .video-name {
          font-weight: 500;
          font-size: 0.9em;
          color: var(--text-primary);
        }

        .video-meta {
          font-size: 0.8em;
          color: var(--text-secondary);
        }

        .delete-btn {
          background: transparent;
          border: none;
          color: var(--error);
          cursor: pointer;
          padding: 6px;
          border-radius: var(--radius-sm);
          opacity: 0.5;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .delete-btn:hover {
          opacity: 1;
          background: rgba(255, 107, 107, 0.1);
        }
      `}</style>
    </div>
  );
}

export default VideoList;
