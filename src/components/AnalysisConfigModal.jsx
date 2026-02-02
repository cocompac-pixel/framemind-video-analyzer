import { useState, useEffect } from 'react';
import { X, Film, Video, Zap, Smartphone, Settings, ChevronDown, ChevronUp } from 'lucide-react';

// Definición de perfiles con sus configuraciones
const PROFILES = {
  documental: {
    id: 'documental',
    name: 'Documental',
    icon: Film,
    description: 'Entrevistas, B-roll, contenido narrativo',
    categories: {
      stability: true,
      focus: true,
      exposure: true,
      composition: false,
    },
    intelligent: {
      garbage_detection: true,
      shot_classification: true,
      face_analysis: true,
      scene_grouping: true,
      take_detection: true,
      key_moments: true,
    }
  },
  cine: {
    id: 'cine',
    name: 'Cine',
    icon: Video,
    description: 'Películas, cortos, contenido cinematográfico',
    categories: {
      stability: true,
      focus: true,
      exposure: true,
      composition: true,
    },
    intelligent: {
      garbage_detection: true,
      shot_classification: true,
      face_analysis: true,
      scene_grouping: true,
      take_detection: true,
      key_moments: true,
    }
  },
  rungun: {
    id: 'rungun',
    name: 'Run & Gun',
    icon: Zap,
    description: 'Eventos, cobertura rápida, acción',
    categories: {
      stability: true,
      focus: true,
      exposure: false,
      composition: false,
    },
    intelligent: {
      garbage_detection: true,
      shot_classification: true,
      face_analysis: false,
      scene_grouping: false,
      take_detection: false,
      key_moments: true,
    }
  },
  social: {
    id: 'social',
    name: 'Social Media',
    icon: Smartphone,
    description: 'TikTok, Reels, contenido casual',
    categories: {
      stability: false,
      focus: true,
      exposure: true,
      composition: false,
    },
    intelligent: {
      garbage_detection: true,
      shot_classification: false,
      face_analysis: true,
      scene_grouping: false,
      take_detection: false,
      key_moments: false,
    }
  },
};

// Categorías de análisis técnico
const CATEGORIES = [
  { id: 'stability', name: 'Estabilidad', description: 'Detecta temblor, paneos, movimiento de cámara' },
  { id: 'focus', name: 'Enfoque', description: 'Detecta borrosidad y foco suave' },
  { id: 'exposure', name: 'Iluminación', description: 'Detecta sobre/subexposición' },
  { id: 'composition', name: 'Composición', description: 'Evalúa encuadre y balance visual' },
];

// Opciones de análisis inteligente
const INTELLIGENT_OPTIONS = [
  {
    id: 'garbage_detection',
    name: 'Detectar basura',
    description: 'Identifica clips inutilizables (tapados, piso, etc.)',
    icon: '🗑'
  },
  {
    id: 'shot_classification',
    name: 'Clasificar planos',
    description: 'Estática, paneo, tracking, etc.',
    icon: '🎬'
  },
  {
    id: 'face_analysis',
    name: 'Detectar rostros',
    description: 'Identifica presencia de personas',
    icon: '👤'
  },
  {
    id: 'scene_grouping',
    name: 'Agrupar escenas',
    description: 'Agrupa clips visualmente similares',
    icon: '📁'
  },
  {
    id: 'take_detection',
    name: 'Detectar tomas',
    description: 'Encuentra repeticiones y mejores takes',
    icon: '🔄'
  },
  {
    id: 'key_moments',
    name: 'Momentos clave',
    description: 'Marca highlights automáticamente',
    icon: '⭐'
  },
];

function AnalysisConfigModal({ isOpen, onClose, onStartAnalysis, pendingCount }) {
  const [selectedProfile, setSelectedProfile] = useState('documental');
  const [categories, setCategories] = useState(PROFILES.documental.categories);
  const [intelligent, setIntelligent] = useState(PROFILES.documental.intelligent);
  const [isCustom, setIsCustom] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Cuando se selecciona un perfil, actualizar las configuraciones
  const handleProfileSelect = (profileId) => {
    setSelectedProfile(profileId);
    setCategories({ ...PROFILES[profileId].categories });
    setIntelligent({ ...PROFILES[profileId].intelligent });
    setIsCustom(false);
  };

  // Cuando se cambia un checkbox de categoría
  const handleCategoryToggle = (categoryId) => {
    const newCategories = {
      ...categories,
      [categoryId]: !categories[categoryId],
    };
    setCategories(newCategories);
    checkIfCustom(newCategories, intelligent);
  };

  // Cuando se cambia un toggle de análisis inteligente
  const handleIntelligentToggle = (optionId) => {
    const newIntelligent = {
      ...intelligent,
      [optionId]: !intelligent[optionId],
    };
    setIntelligent(newIntelligent);
    checkIfCustom(categories, newIntelligent);
  };

  // Verificar si la configuración actual coincide con algún perfil
  const checkIfCustom = (cats, intel) => {
    let matchedProfile = null;
    for (const [profileId, profile] of Object.entries(PROFILES)) {
      const catsMatch = Object.keys(profile.categories).every(
        key => profile.categories[key] === cats[key]
      );
      const intelMatch = Object.keys(profile.intelligent).every(
        key => profile.intelligent[key] === intel[key]
      );
      if (catsMatch && intelMatch) {
        matchedProfile = profileId;
        break;
      }
    }

    if (matchedProfile) {
      setSelectedProfile(matchedProfile);
      setIsCustom(false);
    } else {
      setSelectedProfile(null);
      setIsCustom(true);
    }
  };

  // Verificar que al menos una categoría esté seleccionada
  const hasAtLeastOneCategory = Object.values(categories).some(v => v);

  // Contar opciones activas en cada sección
  const activeCategoriesCount = Object.values(categories).filter(v => v).length;
  const activeIntelligentCount = Object.values(intelligent).filter(v => v).length;

  const handleStart = () => {
    if (!hasAtLeastOneCategory) return;

    onStartAnalysis({
      profile: isCustom ? 'custom' : selectedProfile,
      categories: categories,
      intelligent: intelligent,
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Configurar análisis</h2>
          <button className="btn-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Perfiles */}
          <div className="section">
            <label className="section-label">Perfil de grabación</label>
            <div className="profiles-grid">
              {Object.values(PROFILES).map(profile => {
                const Icon = profile.icon;
                const isSelected = selectedProfile === profile.id && !isCustom;
                return (
                  <button
                    key={profile.id}
                    className={`profile-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleProfileSelect(profile.id)}
                  >
                    <Icon size={20} />
                    <span className="profile-name">{profile.name}</span>
                  </button>
                );
              })}
              {isCustom && (
                <button className="profile-card selected custom">
                  <Settings size={20} />
                  <span className="profile-name">Personalizado</span>
                </button>
              )}
            </div>
            {selectedProfile && !isCustom && (
              <p className="profile-description">
                {PROFILES[selectedProfile].description}
              </p>
            )}
          </div>

          {/* Análisis Técnico */}
          <div className="section">
            <label className="section-label">
              Análisis técnico
              <span className="section-count">{activeCategoriesCount}/4</span>
            </label>
            <div className="categories-grid">
              {CATEGORIES.map(category => (
                <label key={category.id} className="category-item">
                  <input
                    type="checkbox"
                    checked={categories[category.id]}
                    onChange={() => handleCategoryToggle(category.id)}
                  />
                  <div className="category-info">
                    <span className="category-name">{category.name}</span>
                    <span className="category-desc">{category.description}</span>
                  </div>
                </label>
              ))}
            </div>
            {!hasAtLeastOneCategory && (
              <p className="error-text">Selecciona al menos una categoría</p>
            )}
          </div>

          {/* Análisis Inteligente */}
          <div className="section">
            <button
              className="section-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <div className="toggle-left">
                <label className="section-label" style={{ marginBottom: 0 }}>
                  Análisis inteligente
                  <span className="section-count">{activeIntelligentCount}/6</span>
                </label>
                <span className="toggle-hint">
                  {showAdvanced ? 'Ocultar opciones' : 'Mostrar opciones'}
                </span>
              </div>
              {showAdvanced ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>

            {showAdvanced && (
              <div className="intelligent-grid">
                {INTELLIGENT_OPTIONS.map(option => (
                  <label key={option.id} className="intelligent-item">
                    <div className="intelligent-toggle">
                      <input
                        type="checkbox"
                        checked={intelligent[option.id]}
                        onChange={() => handleIntelligentToggle(option.id)}
                      />
                      <span className="toggle-slider"></span>
                    </div>
                    <span className="intelligent-icon">{option.icon}</span>
                    <div className="intelligent-info">
                      <span className="intelligent-name">{option.name}</span>
                      <span className="intelligent-desc">{option.description}</span>
                    </div>
                  </label>
                ))}
              </div>
            )}

            {!showAdvanced && activeIntelligentCount > 0 && (
              <div className="intelligent-summary">
                {INTELLIGENT_OPTIONS.filter(o => intelligent[o.id]).map(o => (
                  <span key={o.id} className="summary-tag" title={o.name}>
                    {o.icon}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn-start"
            onClick={handleStart}
            disabled={!hasAtLeastOneCategory}
          >
            Analizar {pendingCount} video{pendingCount !== 1 ? 's' : ''}
          </button>
        </div>

        <style>{`
          .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
          }

          .modal-content {
            background: var(--bg-secondary);
            border-radius: 16px;
            width: 100%;
            max-width: 560px;
            max-height: 90vh;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
            border: 1px solid var(--border);
          }

          .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
          }

          .modal-header h2 {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
          }

          .btn-close {
            background: none;
            border: none;
            padding: 8px;
            cursor: pointer;
            color: var(--text-muted);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
          }

          .btn-close:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
          }

          .modal-body {
            padding: 24px;
            overflow-y: auto;
            max-height: calc(90vh - 160px);
          }

          .section {
            margin-bottom: 24px;
          }

          .section:last-child {
            margin-bottom: 0;
          }

          .section-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
          }

          .section-count {
            font-size: 11px;
            font-weight: 500;
            color: var(--text-muted);
            background: var(--bg-tertiary);
            padding: 2px 8px;
            border-radius: 10px;
          }

          /* Profiles grid */
          .profiles-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
          }

          .profile-card {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            padding: 16px 12px;
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.15s ease;
            color: var(--text-muted);
          }

          .profile-card:hover {
            border-color: var(--border-hover);
            background: var(--bg-primary);
          }

          .profile-card.selected {
            border-color: var(--accent);
            background: var(--accent);
            color: white;
          }

          .profile-card.custom {
            border-color: var(--blue);
            background: var(--blue);
          }

          .profile-name {
            font-size: 12px;
            font-weight: 600;
            text-align: center;
          }

          .profile-description {
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 12px;
            text-align: center;
          }

          /* Categories grid */
          .categories-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
          }

          .category-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 14px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .category-item:hover {
            border-color: var(--border-hover);
            background: var(--bg-primary);
          }

          .category-item:has(input:checked) {
            border-color: var(--accent);
            background: var(--bg-secondary);
          }

          .category-item input[type="checkbox"] {
            width: 18px;
            height: 18px;
            margin-top: 2px;
            accent-color: var(--accent);
            cursor: pointer;
          }

          .category-info {
            display: flex;
            flex-direction: column;
            gap: 2px;
          }

          .category-name {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
          }

          .category-desc {
            font-size: 12px;
            color: var(--text-muted);
          }

          .error-text {
            color: var(--red);
            font-size: 13px;
            margin-top: 12px;
          }

          /* Section toggle */
          .section-toggle {
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            color: var(--text-muted);
            transition: all 0.15s ease;
          }

          .section-toggle:hover {
            border-color: var(--border-hover);
            background: var(--bg-primary);
          }

          .toggle-left {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 2px;
          }

          .toggle-hint {
            font-size: 12px;
            color: var(--text-muted);
          }

          /* Intelligent options grid */
          .intelligent-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 12px;
          }

          .intelligent-item {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px 14px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .intelligent-item:hover {
            border-color: var(--border-hover);
            background: var(--bg-primary);
          }

          .intelligent-item:has(input:checked) {
            border-color: var(--blue);
            background: var(--blue-bg);
          }

          .intelligent-toggle {
            position: relative;
            width: 36px;
            height: 20px;
            flex-shrink: 0;
          }

          .intelligent-toggle input {
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
            background-color: var(--border);
            transition: 0.2s;
            border-radius: 20px;
          }

          .toggle-slider:before {
            position: absolute;
            content: "";
            height: 16px;
            width: 16px;
            left: 2px;
            bottom: 2px;
            background-color: white;
            transition: 0.2s;
            border-radius: 50%;
          }

          .intelligent-toggle input:checked + .toggle-slider {
            background-color: var(--blue);
          }

          .intelligent-toggle input:checked + .toggle-slider:before {
            transform: translateX(16px);
          }

          .intelligent-icon {
            font-size: 16px;
            margin-top: 2px;
          }

          .intelligent-info {
            display: flex;
            flex-direction: column;
            gap: 1px;
          }

          .intelligent-name {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
          }

          .intelligent-desc {
            font-size: 11px;
            color: var(--text-muted);
          }

          /* Summary tags when collapsed */
          .intelligent-summary {
            display: flex;
            gap: 6px;
            margin-top: 10px;
            padding-left: 4px;
          }

          .summary-tag {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            font-size: 14px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            cursor: default;
          }

          /* Footer */
          .modal-footer {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            padding: 16px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg-tertiary);
          }

          .btn-cancel {
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .btn-cancel:hover {
            border-color: var(--border-hover);
            color: var(--text-primary);
          }

          .btn-start {
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 10px;
            border: none;
            background: var(--accent);
            color: white;
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .btn-start:hover:not(:disabled) {
            background: var(--accent-hover);
          }

          .btn-start:disabled {
            background: var(--border);
            cursor: not-allowed;
          }
        `}</style>
      </div>
    </div>
  );
}

export default AnalysisConfigModal;
