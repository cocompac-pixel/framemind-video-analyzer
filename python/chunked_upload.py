"""
Chunked Upload Manager
Maneja uploads de archivos grandes por chunks para evitar memory issues.
"""

import os
import uuid
import shutil
import asyncio
from pathlib import Path
from werkzeug.utils import secure_filename


class ChunkedUploadManager:
    """Maneja uploads de archivos grandes por chunks"""
    
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    MAX_CONCURRENT = 2        # Límite de uploads simultáneos
    
    def __init__(self, upload_folder):
        self.upload_folder = Path(upload_folder)
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self.active_uploads = {}
        
    async def handle_upload(self, file_stream, filename, progress_callback=None):
        """
        Procesa upload con progress tracking
        
        Args:
            file_stream: Stream del archivo
            filename: Nombre original del archivo
            progress_callback: Función callback(bytes_leidos, total_bytes)
        
        Returns:
            Path: Ruta final del archivo subido
        """
        async with self.semaphore:
            # Crear archivo temporal único
            temp_id = str(uuid.uuid4())
            temp_path = self.upload_folder / f".tmp_{temp_id}"
            
            # Asegurar que el directorio existe
            self.upload_folder.mkdir(parents=True, exist_ok=True)
            
            bytes_read = 0
            try:
                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = file_stream.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        bytes_read += len(chunk)
                        
                        # Llamar callback de progreso si existe
                        if progress_callback:
                            progress_callback(bytes_read)
                
                # Mover atómicamente al destino final
                final_filename = secure_filename(filename)
                final_path = self.upload_folder / final_filename
                
                # Si ya existe, agregar número único
                counter = 1
                original_final = final_path
                while final_path.exists():
                    stem = original_final.stem
                    suffix = original_final.suffix
                    final_path = self.upload_folder / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                shutil.move(str(temp_path), str(final_path))
                
                return final_path
                
            except Exception as e:
                # Limpiar archivo temporal en caso de error
                if temp_path.exists():
                    temp_path.unlink()
                raise e
    
    def handle_upload_sync(self, file_stream, filename, progress_callback=None):
        """Versión síncrona del upload"""
        import threading
        
        result = None
        error = None
        
        def run_async():
            nonlocal result, error
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.handle_upload(file_stream, filename, progress_callback)
                )
                loop.close()
            except Exception as e:
                error = e
        
        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join()
        
        if error:
            raise error
        
        return result


class UploadProgressTracker:
    """Tracker de progreso para uploads"""
    
    def __init__(self, total_size, callback=None):
        self.total_size = total_size
        self.bytes_read = 0
        self.callback = callback
        self.percentage = 0
        
    def update(self, bytes_read):
        """Actualizar progreso"""
        self.bytes_read = bytes_read
        if self.total_size > 0:
            self.percentage = int((bytes_read / self.total_size) * 100)
        
        if self.callback:
            self.callback(self.percentage, bytes_read, self.total_size)
    
    def get_progress(self):
        """Obtener progreso actual"""
        return {
            'percentage': self.percentage,
            'bytes_read': self.bytes_read,
            'total_bytes': self.total_size
        }
