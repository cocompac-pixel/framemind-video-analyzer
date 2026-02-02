import { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { Plus, Folder, Settings, MoreVertical, Pencil, Trash2 } from 'lucide-react';

function Sidebar() {
  const {
    projects,
    currentProjectId,
    selectProject,
    createProject,
    renameProject,
    deleteProject,
  } = useApp();

  const [contextMenu, setContextMenu] = useState(null);
  const [editingProject, setEditingProject] = useState(null);
  const [editName, setEditName] = useState('');
  const editInputRef = useRef(null);

  // Focus input when editing
  useEffect(() => {
    if (editingProject && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingProject]);

  // Close context menu on click outside
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    if (contextMenu) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [contextMenu]);

  const handleNewProject = async () => {
    await createProject();
  };

  const handleContextMenu = (e, project) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      project,
    });
  };

  const startRename = (project) => {
    setContextMenu(null);
    setEditingProject(project.id);
    setEditName(project.name);
  };

  const handleRename = async () => {
    if (editingProject && editName.trim()) {
      await renameProject(editingProject, editName.trim());
    }
    setEditingProject(null);
    setEditName('');
  };

  const handleDelete = async (project) => {
    setContextMenu(null);
    if (confirm(`¿Eliminar proyecto "${project.name}"?`)) {
      await deleteProject(project.id);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleRename();
    } else if (e.key === 'Escape') {
      setEditingProject(null);
      setEditName('');
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">
            <svg width="24" height="24" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
              <circle cx="50" cy="50" r="28" fill="none" stroke="currentColor" strokeWidth="3"/>
              <line x1="8" y1="55" x2="92" y2="45" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="logo-text">FrameMind</span>
        </div>
        <button className="btn-new-project" onClick={handleNewProject}>
          <Plus size={18} />
          <span>Nuevo Proyecto</span>
        </button>
      </div>

      <div className="sidebar-projects">
        <div className="sidebar-section-title">Proyectos</div>
        {projects.length === 0 ? (
          <div className="sidebar-empty">
            No hay proyectos aún
          </div>
        ) : (
          projects.map(project => (
            <div
              key={project.id}
              className={`project-item ${currentProjectId === project.id ? 'active' : ''}`}
              onClick={() => selectProject(project.id)}
              onContextMenu={(e) => handleContextMenu(e, project)}
            >
              <div className="project-item-icon">
                <Folder size={18} />
              </div>
              <div className="project-item-info">
                {editingProject === project.id ? (
                  <input
                    ref={editInputRef}
                    type="text"
                    className="project-item-rename-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onBlur={handleRename}
                    onKeyDown={handleKeyDown}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div className="project-item-name">{project.name}</div>
                )}
              </div>
              {project.video_count > 0 && (
                <span className="project-item-badge">{project.video_count}</span>
              )}
              <button
                className="project-item-menu"
                onClick={(e) => handleContextMenu(e, project)}
              >
                <MoreVertical size={16} />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <div className="nav-item">
          <Settings size={18} />
          <span>Configuración</span>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          <button onClick={() => startRename(contextMenu.project)}>
            <Pencil size={14} />
            <span>Renombrar</span>
          </button>
          <button onClick={() => handleDelete(contextMenu.project)} className="danger">
            <Trash2 size={14} />
            <span>Eliminar</span>
          </button>
        </div>
      )}

      <style>{`
        .sidebar {
          width: 280px;
          background: var(--bg-sidebar);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          position: fixed;
          height: 100vh;
          overflow-y: auto;
          z-index: 100;
        }

        .sidebar-header {
          padding: 16px 12px;
        }

        .logo {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 4px 8px;
          margin-bottom: 20px;
        }

        .logo-icon {
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
        }

        .logo-text {
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary);
          letter-spacing: -0.3px;
        }

        .btn-new-project {
          width: 100%;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          font-size: 14px;
          font-weight: 500;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid var(--border);
          background: var(--bg-tertiary);
          color: var(--text-primary);
          justify-content: flex-start;
        }

        .btn-new-project:hover {
          background: var(--bg-primary);
          border-color: var(--border-hover);
        }

        .btn-new-project svg {
          opacity: 0.7;
        }

        .sidebar-projects {
          flex: 1;
          padding: 0 8px;
          overflow-y: auto;
        }

        .sidebar-section-title {
          font-size: 12px;
          font-weight: 500;
          color: var(--text-muted);
          padding: 20px 8px 8px 8px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .sidebar-empty {
          padding: 16px;
          text-align: center;
          color: var(--text-muted);
          font-size: 13px;
        }

        .project-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 10px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
          margin-bottom: 1px;
        }

        .project-item:hover {
          background: var(--bg-tertiary);
        }

        .project-item.active {
          background: var(--bg-tertiary);
        }

        .project-item-icon {
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          color: var(--text-muted);
        }

        .project-item.active .project-item-icon {
          color: var(--text-primary);
        }

        .project-item-info {
          flex: 1;
          min-width: 0;
        }

        .project-item-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .project-item.active .project-item-name {
          color: var(--text-primary);
        }

        .project-item-rename-input {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-primary);
          background: var(--bg-primary);
          border: 2px solid var(--accent);
          border-radius: 4px;
          padding: 2px 6px;
          width: 100%;
          outline: none;
        }

        .project-item-badge {
          font-size: 11px;
          font-weight: 500;
          color: var(--text-muted);
          background: var(--bg-tertiary);
          padding: 2px 6px;
          border-radius: 4px;
        }

        .project-item.active .project-item-badge {
          background: var(--border);
          color: var(--text-primary);
        }

        .project-item-menu {
          opacity: 0;
          background: none;
          border: none;
          padding: 4px;
          cursor: pointer;
          color: var(--text-muted);
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .project-item:hover .project-item-menu {
          opacity: 1;
        }

        .project-item-menu:hover {
          background: var(--bg-tertiary);
          color: var(--text-primary);
        }

        .sidebar-footer {
          padding: 8px;
          border-top: 1px solid var(--border);
          margin-top: auto;
        }

        .nav-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 10px;
          border-radius: 8px;
          color: var(--text-muted);
          text-decoration: none;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          background: none;
          border: none;
          width: 100%;
        }

        .nav-item:hover {
          background: var(--bg-tertiary);
          color: var(--text-primary);
        }

        .nav-item svg {
          width: 18px;
          height: 18px;
          opacity: 0.7;
        }

        /* Context Menu */
        .context-menu {
          position: fixed;
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 8px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.12);
          padding: 4px;
          z-index: 1000;
          min-width: 140px;
        }

        .context-menu button {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 8px 12px;
          font-size: 13px;
          color: var(--text-secondary);
          background: none;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          text-align: left;
        }

        .context-menu button:hover {
          background: var(--bg-tertiary);
          color: var(--text-primary);
        }

        .context-menu button.danger {
          color: var(--red);
        }

        .context-menu button.danger:hover {
          background: var(--red-bg);
        }
      `}</style>
    </aside>
  );
}

export default Sidebar;
