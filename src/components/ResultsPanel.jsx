import { BarChart3, FileText, Download, ExternalLink } from 'lucide-react';

function ResultsPanel({ results }) {
  if (!results) return null;

  const { stats, xmlFile } = results;

  const formatTime = (seconds) => {
    if (!seconds) return '0s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const totalDuration = stats.total_duration || 0;
  const getPercentage = (value) => {
    if (totalDuration === 0) return 0;
    return Math.round((value / totalDuration) * 100);
  };

  const categories = [
    { key: 'gold', label: 'Oro', icon: '🥇', color: 'var(--gold)', value: stats.total_gold || 0 },
    { key: 'silver', label: 'Plata', icon: '🥈', color: 'var(--silver)', value: stats.total_silver || 0 },
    { key: 'bronze', label: 'Bronce', icon: '🥉', color: 'var(--bronze)', value: stats.total_bronze || 0 },
    { key: 'discard', label: 'Descartar', icon: '❌', color: 'var(--text-muted)', value: stats.total_discard || 0 },
  ];

  const openReport = () => {
    window.open('http://127.0.0.1:5050/api/reports', '_blank');
  };

  const downloadXml = () => {
    if (xmlFile) {
      window.open(`http://127.0.0.1:5050/download/${xmlFile}`, '_blank');
    }
  };

  return (
    <div className="card results-panel fade-in">
      <h2 className="card-title">
        <BarChart3 size={20} />
        Resultados
      </h2>

      <div className="stats-grid">
        {categories.map((cat) => (
          <div key={cat.key} className="stat-box">
            <div className="stat-value" style={{ color: cat.color }}>
              {formatTime(cat.value)}
            </div>
            <div className="stat-label">
              {cat.icon} {cat.label}
              <span className="stat-percent">
                ({getPercentage(cat.value)}%)
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="actions">
        <button className="action-btn report" onClick={openReport}>
          <FileText size={18} />
          Ver Reporte HTML
          <ExternalLink size={14} />
        </button>

        {xmlFile && (
          <button className="action-btn xml" onClick={downloadXml}>
            <Download size={18} />
            Descargar XML Premiere
          </button>
        )}
      </div>

      <style>{`
        .results-panel {
          animation: fadeIn 0.3s ease;
        }

        .card-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-bottom: 20px;
        }

        @media (max-width: 600px) {
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        .stat-box {
          background: rgba(0, 0, 0, 0.2);
          padding: 16px 12px;
          border-radius: var(--radius-sm);
          text-align: center;
        }

        .stat-value {
          font-size: 1.4em;
          font-weight: 700;
          margin-bottom: 6px;
        }

        .stat-label {
          font-size: 0.8em;
          color: var(--text-secondary);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          flex-wrap: wrap;
        }

        .stat-percent {
          opacity: 0.7;
        }

        .actions {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
        }

        .action-btn {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 20px;
          border-radius: var(--radius-sm);
          font-size: 0.9em;
          font-weight: 500;
          cursor: pointer;
          transition: all var(--transition-fast);
          border: 1px solid;
          background: transparent;
        }

        .action-btn.report {
          border-color: var(--accent-primary);
          color: var(--accent-primary);
        }

        .action-btn.report:hover {
          background: var(--accent-primary);
          color: white;
        }

        .action-btn.xml {
          border-color: var(--success);
          color: var(--success);
        }

        .action-btn.xml:hover {
          background: var(--success);
          color: var(--bg-primary);
        }
      `}</style>
    </div>
  );
}

export default ResultsPanel;
