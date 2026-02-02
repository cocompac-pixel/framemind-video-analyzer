import { useState, useCallback, useRef } from 'react';
import { Upload, FolderOpen } from 'lucide-react';

function DropZone({ onFilesAdded }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files).filter(file =>
      /\.(mp4|mov|avi|mxf|mkv|m4v)$/i.test(file.name)
    );

    if (files.length > 0) {
      setIsUploading(true);
      await onFilesAdded(files);
      setIsUploading(false);
    }
  }, [onFilesAdded]);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileSelect = useCallback(async (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      setIsUploading(true);
      await onFilesAdded(files);
      setIsUploading(false);
    }
    // Reset input
    e.target.value = '';
  }, [onFilesAdded]);

  // Usar diálogo nativo de Electron si está disponible
  const handleNativeSelect = useCallback(async () => {
    if (window.electronAPI) {
      const files = await window.electronAPI.selectVideos();
      if (files.length > 0) {
        // Convertir paths a File-like objects
        setIsUploading(true);
        // TODO: Implementar subida desde paths nativos
        console.log('Selected files:', files);
        setIsUploading(false);
      }
    } else {
      handleClick();
    }
  }, [handleClick]);

  return (
    <div
      className={`drop-zone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".mp4,.mov,.avi,.mxf,.mkv,.m4v"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />

      <div className="drop-zone-content">
        {isUploading ? (
          <>
            <div className="icon spin">⏳</div>
            <p className="main-text">Subiendo videos...</p>
          </>
        ) : (
          <>
            <Upload className="icon" size={48} strokeWidth={1.5} />
            <p className="main-text">
              Arrastra videos aquí o haz clic para seleccionar
            </p>
            <p className="formats">MP4, MOV, AVI, MXF, MKV, M4V</p>
          </>
        )}
      </div>

      <style>{`
        .drop-zone {
          border: 2px dashed var(--border-hover);
          border-radius: var(--radius-md);
          padding: 50px 20px;
          text-align: center;
          cursor: pointer;
          transition: all var(--transition-normal);
          margin-bottom: 20px;
          background: var(--bg-secondary);
        }

        .drop-zone:hover,
        .drop-zone.dragging {
          border-color: var(--accent);
          background: var(--bg-tertiary);
        }

        .drop-zone.dragging {
          transform: scale(1.01);
        }

        .drop-zone.uploading {
          pointer-events: none;
          opacity: 0.7;
        }

        .drop-zone-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
        }

        .drop-zone .icon {
          color: var(--text-muted);
          opacity: 0.8;
        }

        .drop-zone .main-text {
          color: var(--text-secondary);
          font-size: 0.95em;
        }

        .drop-zone .formats {
          font-size: 0.8em;
          color: var(--text-muted);
        }
      `}</style>
    </div>
  );
}

export default DropZone;
