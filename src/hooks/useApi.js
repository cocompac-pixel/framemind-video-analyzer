import { useState, useCallback } from 'react';

const API_BASE = 'http://127.0.0.1:5050';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = useCallback(async (endpoint, options = {}) => {
    setLoading(true);
    setError(null);

    try {
      const url = `${API_BASE}${endpoint}`;
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // API methods
  const api = {
    // Config
    getConfig: () => request('/api/config'),
    updateConfig: (config) => request('/api/config', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
    getPresets: () => request('/api/presets'),

    // Videos
    getVideos: () => request('/api/videos'),
    deleteVideo: (filename) => request(`/api/delete/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    }),
    clearVideos: () => request('/api/videos/clear', { method: 'POST' }),
    getVideoMetadata: (filename) => request(`/api/video-metadata/${encodeURIComponent(filename)}`),

    // Upload (special - uses FormData)
    uploadVideo: async (file) => {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Upload failed');
      }

      return response.json();
    },

    // Analysis
    startAnalysis: (config, projectId = null) => request('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ config, project_id: projectId }),
    }),
    getStatus: () => request('/api/status'),
    getResults: () => request('/api/results'),

    // Reports
    getReports: () => request('/api/reports'),
    getHistory: () => request('/api/history'),
    getXmlFiles: () => request('/api/xml-files'),

    // Projects
    getProjects: () => request('/api/projects'),
    createProject: (name, preset, notes) => request('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name, preset, notes }),
    }),
    getProject: (id) => request(`/api/projects/${id}`),
    updateProject: (id, updates) => request(`/api/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),
    deleteProject: (id) => request(`/api/projects/${id}`, {
      method: 'DELETE',
    }),
    getProjectBestTakes: (id) => request(`/api/projects/${id}/best-takes`),

    // Best Takes
    getBestTakes: () => request('/api/best-takes'),

    // Export
    exportXml: (options) => request('/api/export', {
      method: 'POST',
      body: JSON.stringify(options),
    }),
  };

  return { ...api, loading, error, request };
}

// Hook para polling de estado durante análisis
export function useAnalysisStatus(onUpdate) {
  const [isPolling, setIsPolling] = useState(false);
  const { getStatus } = useApi();

  const startPolling = useCallback(() => {
    setIsPolling(true);

    const poll = async () => {
      try {
        const status = await getStatus();
        onUpdate?.(status);

        if (status.running) {
          setTimeout(poll, 1000);
        } else {
          setIsPolling(false);
        }
      } catch (err) {
        console.error('Polling error:', err);
        setIsPolling(false);
      }
    };

    poll();
  }, [getStatus, onUpdate]);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
  }, []);

  return { isPolling, startPolling, stopPolling };
}

export default useApi;
