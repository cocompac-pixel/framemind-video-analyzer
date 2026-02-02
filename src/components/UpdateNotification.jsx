import { Download, X, RefreshCw } from 'lucide-react';

function UpdateNotification({ info, onInstall, onDismiss }) {
  if (!info) return null;

  const isDownloaded = info.type === 'downloaded';

  return (
    <div className="update-notification fade-in">
      <div className="update-content">
        <div className="update-icon">
          {isDownloaded ? <Download size={20} /> : <RefreshCw size={20} className="spin" />}
        </div>
        <div className="update-text">
          <span className="update-title">
            {isDownloaded
              ? 'Actualización lista para instalar'
              : 'Descargando actualización...'}
          </span>
          {info.version && (
            <span className="update-version">Versión {info.version}</span>
          )}
        </div>
      </div>

      <div className="update-actions">
        {isDownloaded && (
          <button className="install-btn" onClick={onInstall}>
            Reiniciar e Instalar
          </button>
        )}
        <button className="dismiss-btn" onClick={onDismiss} title="Cerrar">
          <X size={18} />
        </button>
      </div>

      <style>{`
        .update-notification {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: rgba(30, 30, 50, 0.95);
          backdrop-filter: blur(10px);
          border: 1px solid var(--accent-primary);
          border-radius: var(--radius-md);
          padding: 16px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
          z-index: 1000;
          max-width: 400px;
        }

        .update-content {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .update-icon {
          color: var(--accent-primary);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .update-text {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .update-title {
          font-size: 0.9em;
          font-weight: 500;
          color: var(--text-primary);
        }

        .update-version {
          font-size: 0.8em;
          color: var(--text-secondary);
        }

        .update-actions {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .install-btn {
          background: var(--accent-gradient);
          border: none;
          color: white;
          padding: 8px 16px;
          border-radius: var(--radius-sm);
          font-size: 0.85em;
          font-weight: 500;
          cursor: pointer;
          transition: all var(--transition-fast);
          white-space: nowrap;
        }

        .install-btn:hover {
          transform: translateY(-1px);
          box-shadow: var(--shadow-glow);
        }

        .dismiss-btn {
          background: transparent;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
        }

        .dismiss-btn:hover {
          color: var(--text-primary);
          background: rgba(255, 255, 255, 0.1);
        }
      `}</style>
    </div>
  );
}

export default UpdateNotification;
