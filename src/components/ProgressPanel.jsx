import { Zap } from 'lucide-react';

function ProgressPanel({ status }) {
  if (!status) return null;

  const formatTime = (seconds) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="card progress-panel fade-in">
      <h2 className="card-title">
        <Zap size={20} className="pulse" />
        Analizando...
      </h2>

      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${status.progress || 0}%` }}
        />
      </div>

      <div className="progress-info">
        <span className="progress-count">
          <span className="current">{status.completed || 0}</span>
          <span className="divider">/</span>
          <span className="total">{status.total_videos || 0}</span>
          <span className="label">videos</span>
        </span>

        {status.elapsed > 0 && (
          <span className="elapsed">
            Tiempo: {formatTime(status.elapsed)}
          </span>
        )}
      </div>

      {status.current_video && (
        <div className="current-video">
          <span className="label">Procesando:</span>
          <span className="name truncate">{status.current_video}</span>
          {status.current_progress > 0 && (
            <span className="sub-progress">({status.current_progress}%)</span>
          )}
        </div>
      )}

      {status.log && status.log.length > 0 && (
        <div className="log-container">
          {status.log.slice(-10).map((entry, i) => (
            <div
              key={i}
              className={`log-entry ${
                entry.includes('✓') || entry.includes('✅') ? 'success' :
                entry.includes('❌') ? 'error' : ''
              }`}
            >
              {entry}
            </div>
          ))}
        </div>
      )}

      <style>{`
        .progress-panel {
          animation: fadeIn 0.3s ease;
        }

        .card-title {
          display: flex;
          align-items: center;
          gap: 10px;
          color: var(--accent-primary);
        }

        .progress-bar-container {
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 15px;
        }

        .progress-bar-fill {
          height: 100%;
          background: var(--accent-gradient);
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .progress-info {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .progress-count {
          display: flex;
          align-items: baseline;
          gap: 4px;
        }

        .progress-count .current {
          font-size: 1.4em;
          font-weight: 600;
          color: var(--accent-primary);
        }

        .progress-count .divider {
          color: var(--text-muted);
        }

        .progress-count .total {
          font-size: 1.1em;
          color: var(--text-secondary);
        }

        .progress-count .label {
          font-size: 0.85em;
          color: var(--text-muted);
          margin-left: 4px;
        }

        .elapsed {
          font-size: 0.85em;
          color: var(--text-secondary);
        }

        .current-video {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: var(--radius-sm);
          font-size: 0.85em;
          margin-bottom: 12px;
        }

        .current-video .label {
          color: var(--text-muted);
          flex-shrink: 0;
        }

        .current-video .name {
          color: var(--text-primary);
          flex: 1;
          min-width: 0;
        }

        .current-video .sub-progress {
          color: var(--accent-primary);
          flex-shrink: 0;
        }

        .log-container {
          background: rgba(0, 0, 0, 0.3);
          border-radius: var(--radius-sm);
          padding: 12px;
          max-height: 180px;
          overflow-y: auto;
          font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
          font-size: 0.8em;
        }

        .log-entry {
          padding: 3px 0;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .log-entry.success {
          color: var(--success);
        }

        .log-entry.error {
          color: var(--error);
        }
      `}</style>
    </div>
  );
}

export default ProgressPanel;
