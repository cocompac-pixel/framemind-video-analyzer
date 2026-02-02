import { useState, useEffect } from 'react';

// Frame Mind Logo Component - Circle with diagonal line
const FrameMindLogo = ({ size = 32 }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    {/* Circle ring (outline only) */}
    <circle cx="50" cy="50" r="28" fill="none" stroke="currentColor" strokeWidth="3"/>
    {/* Diagonal line passing through */}
    <line x1="8" y1="55" x2="92" y2="45" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
  </svg>
);

function Header() {
  const [appInfo, setAppInfo] = useState({ version: '1.0.0' });

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.getAppInfo().then(setAppInfo);
    }
  }, []);

  return (
    <header className="header drag-region">
      <div className="header-content no-drag">
        <h1 className="title">
          <span className="title-logo"><FrameMindLogo size={36} /></span>
          FrameMind
        </h1>
        <p className="subtitle">
          Análisis inteligente de video para post-producción
        </p>
      </div>
      <div className="header-meta no-drag">
        <span className="version">v{appInfo.version}</span>
      </div>

      <style>{`
        .header {
          text-align: center;
          padding: 20px 20px 30px;
          position: relative;
        }

        .header-content {
          display: inline-block;
        }

        .title {
          font-size: 2.2em;
          font-weight: 700;
          background: var(--accent-gradient);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          margin-bottom: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
        }

        .title-logo {
          display: flex;
          align-items: center;
          -webkit-text-fill-color: initial;
          color: var(--text-secondary);
        }

        .subtitle {
          color: var(--text-secondary);
          font-size: 1em;
        }

        .header-meta {
          position: absolute;
          right: 20px;
          top: 50%;
          transform: translateY(-50%);
        }

        .version {
          font-size: 0.75em;
          color: var(--text-muted);
          background: var(--bg-tertiary);
          padding: 4px 10px;
          border-radius: 10px;
          border: 1px solid var(--border);
        }
      `}</style>
    </header>
  );
}

export default Header;
