# Video Analyzer Pro

Aplicación de escritorio para análisis inteligente de video para post-producción.

## Requisitos

- Node.js 18+
- Python 3.8+
- FFmpeg

## Desarrollo

### 1. Instalar dependencias

```bash
npm install
```

### 2. Configurar Python

```bash
cd python
pip install -r requirements.txt
```

### 3. Ejecutar en modo desarrollo

```bash
npm run dev
```

Esto iniciará:
- Vite dev server (React) en `localhost:5173`
- Electron app que carga la interfaz
- Python backend en `localhost:5050`

## Build para producción

### macOS

```bash
npm run build:mac
```

El DMG se generará en `release/`.

### Windows

```bash
npm run build:win
```

### Linux

```bash
npm run build:linux
```

## Estructura del proyecto

```
video-analyzer-electron/
├── electron/           # Proceso principal de Electron
│   ├── main.js        # Entry point
│   └── preload.js     # Bridge seguro al renderer
├── src/               # Frontend React
│   ├── components/    # Componentes UI
│   ├── hooks/         # Custom hooks
│   ├── styles/        # CSS global
│   └── App.jsx        # Componente principal
├── python/            # Backend Python (Flask)
│   ├── app.py         # Servidor Flask
│   ├── video_analyzer_engine.py
│   └── ...
├── resources/         # Recursos para build
│   └── ffmpeg/        # Binarios de FFmpeg
└── package.json
```

## Sistema de actualizaciones

Las actualizaciones se publican a través de GitHub Releases. Para configurar:

1. Edita `package.json` y cambia:
   - `build.publish.owner` → Tu usuario de GitHub
   - `build.publish.repo` → Nombre del repositorio

2. Crea un release en GitHub con el tag de la versión (ej: `v1.0.1`)

3. Sube los archivos de build:
   - `Video Analyzer Pro-1.0.1.dmg`
   - `latest-mac.yml`

La app verificará automáticamente si hay actualizaciones al iniciar.

## Licencia

MIT
