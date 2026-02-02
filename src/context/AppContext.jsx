import { createContext, useContext, useState, useCallback, useEffect } from 'react';

const AppContext = createContext(null);

const API_BASE = 'http://127.0.0.1:5050';

export function AppProvider({ children }) {
  // Projects state
  const [projects, setProjects] = useState([]);
  const [currentProjectId, setCurrentProjectId] = useState(null);
  const [currentProject, setCurrentProject] = useState(null);

  // Videos state
  const [pendingVideos, setPendingVideos] = useState([]);
  const [analyzedVideos, setAnalyzedVideos] = useState([]);
  const [selectedVideos, setSelectedVideos] = useState(new Set());

  // UI state
  const [currentFilter, setCurrentFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hideGarbage, setHideGarbage] = useState(false);

  // Advanced filters (Fase B)
  const [activeTagFilters, setActiveTagFilters] = useState(new Set()); // Tags seleccionados
  const [showOnlyWithFaces, setShowOnlyWithFaces] = useState(false);
  const [showOnlyKeyMoments, setShowOnlyKeyMoments] = useState(false);
  const [selectedSceneGroup, setSelectedSceneGroup] = useState(null); // null = all, number = specific group

  // Toast
  const [toast, setToast] = useState(null);

  // API helpers
  const api = useCallback(async (endpoint, options = {}) => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  }, []);

  // Show toast notification
  const showToast = useCallback((message) => {
    setToast(message);
    setTimeout(() => setToast(null), 3000);
  }, []);

  // Load all projects
  const loadProjects = useCallback(async () => {
    try {
      const data = await api('/api/projects');
      setProjects(data.projects || []);
      return data.projects || [];
    } catch (err) {
      console.error('Error loading projects:', err);
      return [];
    }
  }, [api]);

  // Select a project
  const selectProject = useCallback(async (projectId) => {
    if (!projectId) {
      setCurrentProjectId(null);
      setCurrentProject(null);
      setPendingVideos([]);
      setAnalyzedVideos([]);
      setSelectedVideos(new Set());
      return;
    }

    setLoading(true);
    setCurrentProjectId(projectId);
    setSelectedVideos(new Set());

    try {
      // Load project details
      const projectData = await api(`/api/projects/${projectId}`);
      setCurrentProject(projectData);

      // Load analyzed videos with segments from dedicated endpoint
      const videosData = await api(`/api/projects/${projectId}/videos`);
      setAnalyzedVideos(videosData.videos || []);

      // Load pending videos
      const pendingData = await api(`/api/projects/${projectId}/pending`);
      setPendingVideos(pendingData.videos || []);
    } catch (err) {
      console.error('Error loading project:', err);
      showToast('Error al cargar el proyecto');
    } finally {
      setLoading(false);
    }
  }, [api, showToast]);

  // Create new project
  const createProject = useCallback(async (name) => {
    try {
      // POST a /api/projects con el nombre
      const result = await api('/api/projects', {
        method: 'POST',
        body: JSON.stringify({ name: name || generateProjectName() }),
      });
      await loadProjects();
      // El servidor devuelve el proyecto creado con su id
      if (result && result.id) {
        await selectProject(result.id);
        showToast('Proyecto creado');
        return result.id;
      }
      return null;
    } catch (err) {
      console.error('Error creating project:', err);
      showToast('Error al crear proyecto');
      return null;
    }
  }, [api, loadProjects, selectProject, showToast]);

  // Rename project
  const renameProject = useCallback(async (projectId, newName) => {
    try {
      // PATCH a /api/projects/{id} para actualizar
      await api(`/api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: newName }),
      });
      await loadProjects();
      if (currentProjectId === projectId) {
        setCurrentProject(prev => prev ? { ...prev, name: newName } : prev);
      }
      showToast('Proyecto renombrado');
    } catch (err) {
      console.error('Error renaming project:', err);
      showToast('Error al renombrar');
    }
  }, [api, loadProjects, currentProjectId, showToast]);

  // Delete project
  const deleteProject = useCallback(async (projectId) => {
    try {
      await api(`/api/projects/${projectId}`, { method: 'DELETE' });
      await loadProjects();
      if (currentProjectId === projectId) {
        selectProject(null);
      }
      showToast('Proyecto eliminado');
    } catch (err) {
      console.error('Error deleting project:', err);
      showToast('Error al eliminar proyecto');
    }
  }, [api, loadProjects, currentProjectId, selectProject, showToast]);

  // Upload files
  const uploadFiles = useCallback(async (files) => {
    if (!currentProjectId || files.length === 0) return;

    const formData = new FormData();
    for (const file of files) {
      formData.append('videos', file);
    }
    formData.append('project_id', currentProjectId);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();

      if (data.uploaded) {
        // Add to pending videos
        const newPending = data.uploaded.map(name => ({
          name,
          status: 'pending',
          duration: 0,
          metadata_status: 'processing'
        }));
        setPendingVideos(prev => [...prev, ...newPending]);
        showToast(`${data.uploaded.length} video(s) subido(s)`);

        // Check for metadata periodically
        checkPendingVideos();
      }
    } catch (err) {
      console.error('Error uploading:', err);
      showToast('Error al subir videos');
    }
  }, [currentProjectId, showToast]);

  // Check pending videos metadata
  const checkPendingVideos = useCallback(async () => {
    if (!currentProjectId) return;

    try {
      const data = await api(`/api/projects/${currentProjectId}/pending`);
      setPendingVideos(data.videos || []);
    } catch (err) {
      console.error('Error checking pending:', err);
    }
  }, [api, currentProjectId]);

  // Start analysis with optional config from modal
  const startAnalysis = useCallback(async (analysisConfig = null) => {
    if (analysisRunning || !currentProjectId || pendingVideos.length === 0) return;

    setAnalysisRunning(true);
    setPendingVideos(prev => prev.map(v => ({ ...v, status: 'queued' })));

    // Construir configuración para el backend
    const configPayload = {
      project_id: currentProjectId,
      config: {},
    };

    // Si hay configuración del modal, agregarla
    if (analysisConfig) {
      configPayload.analysis_categories = analysisConfig.categories;
      configPayload.analysis_profile = analysisConfig.profile;
      // Opciones de análisis inteligente
      if (analysisConfig.intelligent) {
        configPayload.intelligent_analysis = analysisConfig.intelligent;
      }
    }

    try {
      await api('/api/analyze', {
        method: 'POST',
        body: JSON.stringify(configPayload),
      });
      showToast('Análisis iniciado');
    } catch (err) {
      console.error('Error starting analysis:', err);
      setAnalysisRunning(false);
      showToast('Error al iniciar análisis');
    }
  }, [api, analysisRunning, currentProjectId, pendingVideos.length, showToast]);

  // Check analysis status
  const checkAnalysisStatus = useCallback(async () => {
    try {
      const status = await api('/api/status');

      if (!status.running && status.total_videos > 0 && status.completed_videos?.length > 0) {
        setAnalysisRunning(false);
        setPendingVideos([]);
        setSelectedVideos(new Set());
        await selectProject(currentProjectId);
        showToast('Análisis completado!');
        return true; // Analysis finished
      } else if (status.running) {
        setPendingVideos(prev => prev.map(v => {
          if (status.completed_videos?.includes(v.name)) {
            return { ...v, status: 'completed', progress: 100 };
          } else if (status.current_video === v.name) {
            return { ...v, status: 'analyzing', progress: status.current_progress || 50 };
          }
          return { ...v, status: 'queued' };
        }));
      }
      return false;
    } catch (err) {
      console.error('Error checking status:', err);
      return false;
    }
  }, [api, currentProjectId, selectProject, showToast]);

  // Toggle video selection
  const toggleVideoSelection = useCallback((videoId) => {
    setSelectedVideos(prev => {
      const next = new Set(prev);
      if (next.has(videoId)) {
        next.delete(videoId);
      } else {
        next.add(videoId);
      }
      return next;
    });
  }, []);

  // Select all / deselect all
  const toggleSelectAll = useCallback(() => {
    if (selectedVideos.size === analyzedVideos.length) {
      setSelectedVideos(new Set());
    } else {
      setSelectedVideos(new Set(analyzedVideos.map(v => v.id)));
    }
  }, [selectedVideos.size, analyzedVideos]);

  // Get all unique tags from analyzed videos
  const getAllTags = useCallback(() => {
    const tagsSet = new Set();
    for (const video of analyzedVideos) {
      for (const seg of video.segments || []) {
        for (const tag of seg.tags || []) {
          tagsSet.add(tag);
        }
      }
    }
    return Array.from(tagsSet).sort();
  }, [analyzedVideos]);

  // Get all scene groups from analyzed videos
  const getAllSceneGroups = useCallback(() => {
    const groupsMap = new Map(); // group_id -> { count, videos }
    for (const video of analyzedVideos) {
      for (const seg of video.segments || []) {
        if (seg.scene_group_id != null) {
          if (!groupsMap.has(seg.scene_group_id)) {
            groupsMap.set(seg.scene_group_id, { count: 0, videos: new Set() });
          }
          const g = groupsMap.get(seg.scene_group_id);
          g.count++;
          g.videos.add(video.id);
        }
      }
    }
    return Array.from(groupsMap.entries()).map(([id, data]) => ({
      id,
      segmentCount: data.count,
      videoCount: data.videos.size
    })).sort((a, b) => b.segmentCount - a.segmentCount);
  }, [analyzedVideos]);

  // Toggle tag filter
  const toggleTagFilter = useCallback((tag) => {
    setActiveTagFilters(prev => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  }, []);

  // Clear all advanced filters
  const clearAdvancedFilters = useCallback(() => {
    setActiveTagFilters(new Set());
    setShowOnlyWithFaces(false);
    setShowOnlyKeyMoments(false);
    setSelectedSceneGroup(null);
  }, []);

  // Get filtered videos
  const getFilteredVideos = useCallback(() => {
    const allVideos = [];

    // Add pending
    for (const v of pendingVideos) {
      allVideos.push({
        id: `pending_${v.name}`,
        filename: v.name,
        duration: v.duration || 0,
        type: 'pending',
        status: v.status || 'pending',
        progress: v.progress || 0,
        metadata_status: v.metadata_status,
        size_mb: v.size_mb,
      });
    }

    // Add analyzed
    for (const v of analyzedVideos) {
      allVideos.push({ ...v, type: 'analyzed' });
    }

    // Apply filter
    let filtered = allVideos;
    if (currentFilter === 'pending') {
      filtered = allVideos.filter(v => v.type === 'pending');
    } else if (currentFilter === 'analyzed') {
      filtered = allVideos.filter(v => v.type === 'analyzed');
    }

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(v => v.filename.toLowerCase().includes(query));
    }

    // Apply advanced filters (only on analyzed videos)
    if (activeTagFilters.size > 0) {
      filtered = filtered.filter(v => {
        if (v.type !== 'analyzed') return true;
        // Video must have at least one segment with any of the selected tags
        return (v.segments || []).some(seg =>
          (seg.tags || []).some(tag => activeTagFilters.has(tag))
        );
      });
    }

    if (showOnlyWithFaces) {
      filtered = filtered.filter(v => {
        if (v.type !== 'analyzed') return true;
        return (v.segments || []).some(seg =>
          seg.face_count > 0 || seg.face_analysis?.has_faces
        );
      });
    }

    if (showOnlyKeyMoments) {
      filtered = filtered.filter(v => {
        if (v.type !== 'analyzed') return true;
        return (v.segments || []).some(seg => seg.is_key_moment);
      });
    }

    if (selectedSceneGroup !== null) {
      filtered = filtered.filter(v => {
        if (v.type !== 'analyzed') return true;
        return (v.segments || []).some(seg => seg.scene_group_id === selectedSceneGroup);
      });
    }

    return filtered;
  }, [pendingVideos, analyzedVideos, currentFilter, searchQuery, activeTagFilters, showOnlyWithFaces, showOnlyKeyMoments, selectedSceneGroup]);

  // Export videos
  const exportVideos = useCallback(async (videosToExport, options) => {
    if (!currentProjectId) return null;

    const allClips = [];
    for (const video of videosToExport) {
      for (const seg of video.segments || []) {
        if (options.tiers.includes(seg.tier)) {
          allClips.push({
            filename: video.filename,
            path: video.path,
            start_time: seg.start_time,
            end_time: seg.end_time,
            tier: seg.tier,
            shot_type: seg.shot_type,
            duration: video.duration,
            // Métricas para capa de texto
            score: seg.score,
            metrics: seg.metrics,
            human_readable: seg.human_readable,
          });
        }
      }
    }

    if (allClips.length === 0) {
      showToast('No hay clips para exportar');
      return null;
    }

    try {
      const project = projects.find(p => p.id === currentProjectId);
      const response = await api('/api/export', {
        method: 'POST',
        body: JSON.stringify({
          project_id: currentProjectId,
          tiers: options.tiers,
          track_mode: options.track_mode,
          organization: options.organization,
          sort_by: options.sort_by,
          handles: options.handles,
          filename: project?.name || 'export',
          media_folder: options.media_folder,
          selected_clips: allClips,
        }),
      });

      if (response.download_url) {
        showToast('XML exportado!');
        return response.download_url;
      } else if (response.error) {
        showToast('Error: ' + response.error);
      }
    } catch (err) {
      console.error('Error exporting:', err);
      showToast('Error al exportar');
    }
    return null;
  }, [api, currentProjectId, projects, showToast]);

  // Polling for analysis status
  useEffect(() => {
    let interval;
    if (analysisRunning) {
      interval = setInterval(async () => {
        const finished = await checkAnalysisStatus();
        if (finished && interval) {
          clearInterval(interval);
        }
      }, 800);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [analysisRunning, checkAnalysisStatus]);

  // Initial load
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const value = {
    // State
    projects,
    currentProjectId,
    currentProject,
    pendingVideos,
    analyzedVideos,
    selectedVideos,
    currentFilter,
    searchQuery,
    analysisRunning,
    loading,
    toast,
    hideGarbage,
    // Advanced filters state
    activeTagFilters,
    showOnlyWithFaces,
    showOnlyKeyMoments,
    selectedSceneGroup,

    // Actions
    loadProjects,
    selectProject,
    createProject,
    renameProject,
    deleteProject,
    uploadFiles,
    startAnalysis,
    toggleVideoSelection,
    toggleSelectAll,
    setCurrentFilter,
    setSearchQuery,
    setHideGarbage,
    getFilteredVideos,
    exportVideos,
    showToast,
    checkPendingVideos,
    // Advanced filter actions
    getAllTags,
    getAllSceneGroups,
    toggleTagFilter,
    setShowOnlyWithFaces,
    setShowOnlyKeyMoments,
    setSelectedSceneGroup,
    clearAdvancedFilters,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}

// Helper to generate project name
function generateProjectName() {
  const now = new Date();
  const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  return `${now.getDate()} ${months[now.getMonth()]} ${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`;
}

export default AppContext;
