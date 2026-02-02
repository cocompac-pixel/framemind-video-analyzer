const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const log = require('electron-log');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Configurar logging
log.transports.file.level = 'info';
autoUpdater.logger = log;

// Variables globales
let mainWindow = null;
let pythonProcess = null;
let isDev = !app.isPackaged;

// Rutas
const getResourcesPath = () => {
  if (isDev) {
    return path.join(__dirname, '..');
  }
  return process.resourcesPath;
};

const getPythonPath = () => {
  const resourcesPath = getResourcesPath();
  return path.join(resourcesPath, 'python');
};

const getFFmpegPath = () => {
  const resourcesPath = getResourcesPath();
  return path.join(resourcesPath, 'ffmpeg');
};

const getDataPath = () => {
  // Carpeta para datos del usuario (videos, proyectos, etc.)
  const userDataPath = app.getPath('userData');
  const dataPath = path.join(userDataPath, 'FrameMindData');

  // Crear subcarpetas necesarias
  const folders = ['videos_raw', 'videos_analyzed', 'thumbnails', 'projects'];
  folders.forEach(folder => {
    const folderPath = path.join(dataPath, folder);
    if (!fs.existsSync(folderPath)) {
      fs.mkdirSync(folderPath, { recursive: true });
    }
  });

  return dataPath;
};

// Crear ventana principal
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: '#1a1a2e',
    titleBarStyle: 'hiddenInset', // Estilo macOS nativo
    trafficLightPosition: { x: 20, y: 20 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    },
    show: false // No mostrar hasta que esté listo
  });

  // Cargar la app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Mostrar cuando esté listo
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();

    // Verificar actualizaciones (solo en producción)
    if (!isDev) {
      autoUpdater.checkForUpdatesAndNotify();
    }
  });

  // Manejar cierre
  mainWindow.on('closed', () => {
    mainWindow = null;
    stopPythonServer();
  });
}

// Iniciar servidor Python
function startPythonServer() {
  return new Promise((resolve, reject) => {
    const pythonPath = getPythonPath();
    const ffmpegPath = getFFmpegPath();
    const dataPath = getDataPath();

    // Configurar variables de entorno
    const env = {
      ...process.env,
      PATH: `${ffmpegPath}:${process.env.PATH}`,
      VIDEO_ANALYZER_DATA_PATH: dataPath,
      FLASK_ENV: 'production'
    };

    let executable;
    let args = [];

    if (isDev) {
      // En desarrollo: usar python3 directamente
      executable = process.platform === 'win32' ? 'python' : 'python3';
      args = [path.join(pythonPath, 'app.py')];
    } else {
      // En producción: usar el ejecutable empaquetado
      executable = path.join(pythonPath, 'backend_executable');
      // En Mac, verificar si existe el ejecutable
      if (process.platform === 'darwin' && !fs.existsSync(executable)) {
        // Fallback a python3 si no existe el ejecutable
        executable = 'python3';
        args = [path.join(pythonPath, 'app.py')];
      }
    }

    log.info(`Starting Python server...`);
    log.info(`Executable: ${executable}`);
    log.info(`Args: ${args}`);
    log.info(`Data path: ${dataPath}`);
    log.info(`FFmpeg path: ${ffmpegPath}`);

    pythonProcess = spawn(executable, args, {
      cwd: pythonPath,
      env: env,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      log.info(`Python: ${output}`);

      // Detectar cuando el servidor está listo
      if (output.includes('Running on') || output.includes('5050')) {
        resolve();
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      log.error(`Python Error: ${data}`);
    });

    pythonProcess.on('error', (err) => {
      log.error('Failed to start Python:', err);
      reject(err);
    });

    pythonProcess.on('close', (code) => {
      log.info(`Python process exited with code ${code}`);
      pythonProcess = null;
    });

    // Timeout para resolver si no detectamos el mensaje de inicio
    setTimeout(() => {
      resolve();
    }, 5000);
  });
}

// Detener servidor Python
function stopPythonServer() {
  if (pythonProcess) {
    log.info('Stopping Python server...');
    pythonProcess.kill();
    pythonProcess = null;
  }
}

// IPC Handlers
ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    dataPath: getDataPath(),
    isDev: isDev
  };
});

ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('select-videos', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'Videos', extensions: ['mp4', 'mov', 'avi', 'mxf', 'mkv', 'm4v'] }
    ]
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url);
});

ipcMain.handle('open-path', async (event, filePath) => {
  await shell.openPath(filePath);
});

ipcMain.handle('show-item-in-folder', async (event, filePath) => {
  shell.showItemInFolder(filePath);
});

// Auto-updater events
autoUpdater.on('checking-for-update', () => {
  log.info('Checking for updates...');
});

autoUpdater.on('update-available', (info) => {
  log.info('Update available:', info);
  mainWindow?.webContents.send('update-available', info);
});

autoUpdater.on('update-not-available', (info) => {
  log.info('Update not available:', info);
});

autoUpdater.on('download-progress', (progress) => {
  log.info('Download progress:', progress.percent);
  mainWindow?.webContents.send('update-progress', progress);
});

autoUpdater.on('update-downloaded', (info) => {
  log.info('Update downloaded:', info);
  mainWindow?.webContents.send('update-downloaded', info);
});

autoUpdater.on('error', (err) => {
  log.error('Update error:', err);
});

ipcMain.handle('install-update', () => {
  autoUpdater.quitAndInstall();
});

ipcMain.handle('check-for-updates', async () => {
  if (!isDev) {
    return await autoUpdater.checkForUpdates();
  }
  return null;
});

// App lifecycle
app.whenReady().then(async () => {
  try {
    // Iniciar servidor Python primero
    await startPythonServer();

    // Luego crear la ventana
    createWindow();
  } catch (err) {
    log.error('Error starting app:', err);
    dialog.showErrorBox('Error', `No se pudo iniciar la aplicación: ${err.message}`);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  stopPythonServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  stopPythonServer();
});

// Manejar errores no capturados
process.on('uncaughtException', (err) => {
  log.error('Uncaught exception:', err);
});
