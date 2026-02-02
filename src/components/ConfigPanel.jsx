import { useState } from 'react';
import { Settings, Rocket, Loader2 } from 'lucide-react';

const MODULES = [
  { id: 'movimiento', name: 'Movimiento', icon: '🎯', desc: 'Detecta paneos y movimientos' },
  { id: 'estabilidad', name: 'Estabilidad', icon: '📳', desc: 'Detecta temblor / shaky' },
  { id: 'composicion', name: 'Composición', icon: '📐', desc: 'Regla de tercios, balance' },
  { id: 'iluminacion', name: 'Iluminación', icon: '💡', desc: 'Exposición, contraste' },
  { id: 'color', name: 'Color', icon: '🎨', desc: 'Saturación, balance' },
];

const PRESETS = [
  { id: 'completo', name: 'Completo', modules: ['movimiento', 'estabilidad', 'composicion', 'iluminacion', 'color'] },
  { id: 'rapido', name: 'Rápido', modules: ['movimiento', 'estabilidad', 'iluminacion'] },
  { id: 'shaky', name: 'Solo Shaky', modules: ['estabilidad'] },
  { id: 'visual', name: 'Solo Visual', modules: ['composicion', 'iluminacion', 'color'] },
];

function ConfigPanel({ config, onChange, onAnalyze, disabled, isAnalyzing }) {
  const [activePreset, setActivePreset] = useState('completo');

  if (!config) {
    return (
      <div className="card">
        <div className="loading">
          <Loader2 className="spin" size={24} />
          <span>Cargando configuración...</span>
        </div>
      </div>
    );
  }

  const handleModuleToggle = (moduleId, checked) => {
    const newConfig = {
      ...config,
      analisis: {
        ...config.analisis,
        [moduleId]: {
          ...config.analisis[moduleId],
          activado: checked,
        },
      },
    };
    onChange(newConfig);
    setActivePreset(null);
  };

  const handlePresetClick = (preset) => {
    setActivePreset(preset.id);

    const newConfig = { ...config };
    MODULES.forEach(module => {
      newConfig.analisis[module.id] = {
        ...newConfig.analisis[module.id],
        activado: preset.modules.includes(module.id),
      };
    });
    onChange(newConfig);
  };

  const isModuleActive = (moduleId) => {
    return config.analisis?.[moduleId]?.activado ?? true;
  };

  return (
    <div className="card config-panel">
      <h2 className="card-title">
        <Settings size={20} />
        Configuración
      </h2>

      <div className="config-section">
        <h3 className="section-title">Módulos de Análisis</h3>

        <div className="modules-list">
          {MODULES.map((module) => (
            <div key={module.id} className="module-item">
              <div className="module-info">
                <span className="module-icon">{module.icon}</span>
                <div className="module-text">
                  <span className="module-name">{module.name}</span>
                  <span className="module-desc">{module.desc}</span>
                </div>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={isModuleActive(module.id)}
                  onChange={(e) => handleModuleToggle(module.id, e.target.checked)}
                  disabled={isAnalyzing}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h3 className="section-title">Presets</h3>
        <div className="presets-list">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              className={`preset-btn ${activePreset === preset.id ? 'active' : ''}`}
              onClick={() => handlePresetClick(preset)}
              disabled={isAnalyzing}
            >
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      <button
        className="analyze-btn"
        onClick={onAnalyze}
        disabled={disabled}
      >
        {isAnalyzing ? (
          <>
            <Loader2 className="spin" size={20} />
            Analizando...
          </>
        ) : (
          <>
            <Rocket size={20} />
            Analizar Videos
          </>
        )}
      </button>

      <style>{`
        .config-panel {
          position: sticky;
          top: 20px;
        }

        .card-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .loading {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 40px;
          color: var(--text-secondary);
        }

        .config-section {
          margin-bottom: 25px;
        }

        .section-title {
          font-size: 0.8em;
          color: var(--text-secondary);
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 15px;
        }

        .modules-list {
          display: flex;
          flex-direction: column;
        }

        .module-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 0;
          border-bottom: 1px solid var(--border-light);
        }

        .module-item:last-child {
          border-bottom: none;
        }

        .module-info {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .module-icon {
          font-size: 1.3em;
        }

        .module-text {
          display: flex;
          flex-direction: column;
        }

        .module-name {
          font-weight: 500;
          font-size: 0.95em;
        }

        .module-desc {
          font-size: 0.8em;
          color: var(--text-secondary);
        }

        /* Toggle Switch */
        .toggle {
          position: relative;
          width: 50px;
          height: 26px;
          flex-shrink: 0;
        }

        .toggle input {
          opacity: 0;
          width: 0;
          height: 0;
        }

        .toggle-slider {
          position: absolute;
          cursor: pointer;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 26px;
          transition: var(--transition-normal);
        }

        .toggle-slider:before {
          position: absolute;
          content: "";
          height: 20px;
          width: 20px;
          left: 3px;
          bottom: 3px;
          background: white;
          border-radius: 50%;
          transition: var(--transition-normal);
        }

        .toggle input:checked + .toggle-slider {
          background: var(--accent-gradient);
        }

        .toggle input:checked + .toggle-slider:before {
          transform: translateX(24px);
        }

        .toggle input:disabled + .toggle-slider {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Presets */
        .presets-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .preset-btn {
          padding: 8px 16px;
          border: 1px solid var(--border-medium);
          border-radius: 20px;
          background: transparent;
          color: var(--text-primary);
          cursor: pointer;
          font-size: 0.85em;
          transition: all var(--transition-fast);
        }

        .preset-btn:hover:not(:disabled) {
          border-color: var(--accent-primary);
          color: var(--accent-primary);
        }

        .preset-btn.active {
          background: var(--accent-gradient);
          border-color: transparent;
          color: white;
        }

        .preset-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Analyze Button */
        .analyze-btn {
          width: 100%;
          padding: 16px;
          border: none;
          border-radius: var(--radius-md);
          background: var(--accent-gradient);
          color: white;
          font-size: 1.05em;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          margin-top: 10px;
        }

        .analyze-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: var(--shadow-glow);
        }

        .analyze-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }
      `}</style>
    </div>
  );
}

export default ConfigPanel;
