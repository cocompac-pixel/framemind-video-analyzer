import { ClipboardList, ExternalLink, FileVideo } from 'lucide-react';

function ReportsPanel({ reports, xmlFiles }) {
  const hasContent = (reports?.length > 0) || (xmlFiles?.length > 0);

  if (!hasContent) {
    return (
      <div className="card reports-panel">
        <h2 className="card-title">
          <ClipboardList size={20} />
          Reportes Anteriores
        </h2>
        <div className="empty-state">
          No hay reportes aún
        </div>

        <style>{`
          .reports-panel .empty-state {
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.9em;
          }
        `}</style>
      </div>
    );
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return dateStr;
  };

  const openReport = (name) => {
    window.open(`http://127.0.0.1:5050/reports/${name}`, '_blank');
  };

  const downloadXml = (name) => {
    window.open(`http://127.0.0.1:5050/download/${name}`, '_blank');
  };

  return (
    <div className="card reports-panel">
      <h2 className="card-title">
        <ClipboardList size={20} />
        Reportes Anteriores
      </h2>

      {reports?.length > 0 && (
        <div className="reports-section">
          <h3 className="section-label">Análisis HTML</h3>
          <div className="reports-list">
            {reports.slice(0, 5).map((report) => (
              <div
                key={report.name}
                className="report-item"
                onClick={() => openReport(report.name)}
              >
                <div className="report-info">
                  <span className="report-icon">📊</span>
                  <span className="report-name truncate">{report.name}</span>
                </div>
                <div className="report-meta">
                  <span className="report-date">{formatDate(report.date)}</span>
                  <ExternalLink size={14} className="external-icon" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {xmlFiles?.length > 0 && (
        <div className="reports-section">
          <h3 className="section-label">Archivos Premiere</h3>
          <div className="reports-list">
            {xmlFiles.slice(0, 3).map((xml) => (
              <div
                key={xml.name}
                className="report-item xml"
                onClick={() => downloadXml(xml.name)}
              >
                <div className="report-info">
                  <FileVideo size={16} className="xml-icon" />
                  <span className="report-name truncate">{xml.name}</span>
                </div>
                <div className="report-meta">
                  <span className="report-date">{formatDate(xml.date)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        .reports-panel .card-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .reports-section {
          margin-bottom: 16px;
        }

        .reports-section:last-child {
          margin-bottom: 0;
        }

        .section-label {
          font-size: 0.75em;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 10px;
          padding-left: 4px;
        }

        .reports-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .report-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 14px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: var(--radius-sm);
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .report-item:hover {
          background: rgba(0, 0, 0, 0.3);
        }

        .report-item:hover .external-icon {
          opacity: 1;
        }

        .report-info {
          display: flex;
          align-items: center;
          gap: 10px;
          flex: 1;
          min-width: 0;
        }

        .report-icon {
          font-size: 1em;
        }

        .xml-icon {
          color: var(--success);
        }

        .report-name {
          font-size: 0.85em;
          color: var(--accent-primary);
        }

        .report-item.xml .report-name {
          color: var(--success);
        }

        .report-meta {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .report-date {
          font-size: 0.75em;
          color: var(--text-muted);
        }

        .external-icon {
          color: var(--text-muted);
          opacity: 0;
          transition: opacity var(--transition-fast);
        }
      `}</style>
    </div>
  );
}

export default ReportsPanel;
