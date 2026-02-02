import { useState, useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import Sidebar from './components/Sidebar';
import MainContent from './components/MainContent';
import UpdateNotification from './components/UpdateNotification';
import './styles/global.css';

function AppContent() {
  const { toast } = useApp();
  const [updateInfo, setUpdateInfo] = useState(null);

  // Setup update listeners
  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onUpdateAvailable?.((info) => {
        setUpdateInfo({ type: 'available', ...info });
      });

      window.electronAPI.onUpdateDownloaded?.((info) => {
        setUpdateInfo({ type: 'downloaded', ...info });
      });
    }
  }, []);

  const handleInstallUpdate = () => {
    if (window.electronAPI) {
      window.electronAPI.installUpdate?.();
    }
  };

  return (
    <div className="app">
      <Sidebar />
      <MainContent />

      {/* Update notification */}
      {updateInfo && (
        <UpdateNotification
          info={updateInfo}
          onInstall={handleInstallUpdate}
          onDismiss={() => setUpdateInfo(null)}
        />
      )}

      {/* Toast notification */}
      {toast && (
        <div className="toast show">
          {toast}
        </div>
      )}

      <style>{`
        .toast {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%) translateY(100px);
          background: #18181B;
          color: white;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 500;
          opacity: 0;
          transition: all 0.3s ease;
          z-index: 1000;
        }

        .toast.show {
          transform: translateX(-50%) translateY(0);
          opacity: 1;
        }
      `}</style>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
