function PendingVideoRow({ video }) {
  const formatTime = (seconds) => {
    if (!seconds || seconds <= 0) return '...';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  const isProcessingMeta = video.metadata_status === 'processing';

  let statusClass, statusText;
  if (video.status === 'completed') {
    statusClass = 'completed';
    statusText = '✓ Analizado';
  } else if (video.status === 'analyzing') {
    statusClass = 'analyzing';
    statusText = `Analizando... ${video.progress || 0}%`;
  } else if (video.status === 'queued') {
    statusClass = 'queued';
    statusText = 'En cola...';
  } else if (isProcessingMeta) {
    statusClass = 'processing';
    statusText = 'Procesando...';
  } else {
    statusClass = 'pending';
    statusText = 'Listo para analizar';
  }

  return (
    <div className={`pending-video-row ${isProcessingMeta ? 'processing' : ''}`}>
      <div className="pending-video-info">
        <div className="pending-video-name">{video.filename}</div>
        <div className="pending-video-meta">
          <span>Duración: {formatTime(video.duration)}</span>
          {video.size_mb && <span>{video.size_mb} MB</span>}
        </div>
      </div>
      <span className={`pending-video-status ${statusClass}`}>{statusText}</span>

      <style>{`
        .pending-video-row {
          background: white;
          border: 1px solid #E4E4E7;
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          align-items: center;
          gap: 16px;
          transition: all 0.15s ease;
        }

        .pending-video-row:hover {
          border-color: #D4D4D8;
          background: #FAFAFA;
        }

        .pending-video-row.processing {
          opacity: 0.7;
        }

        .pending-video-info {
          flex: 1;
          min-width: 0;
        }

        .pending-video-name {
          font-size: 15px;
          font-weight: 600;
          color: #18181B;
          margin-bottom: 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .pending-video-meta {
          font-size: 13px;
          color: #71717A;
          display: flex;
          gap: 16px;
        }

        .pending-video-status {
          font-size: 12px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 6px;
          white-space: nowrap;
        }

        .pending-video-status.pending {
          background: #FEF3C7;
          color: #D97706;
        }

        .pending-video-status.analyzing {
          background: #DBEAFE;
          color: #2563EB;
          animation: pulse 1.5s ease-in-out infinite;
        }

        .pending-video-status.queued {
          background: #FEF3C7;
          color: #D97706;
        }

        .pending-video-status.completed {
          background: #DCFCE7;
          color: #16A34A;
        }

        .pending-video-status.processing {
          background: #F3F4F6;
          color: #6B7280;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

export default PendingVideoRow;
