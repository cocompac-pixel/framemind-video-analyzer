#!/bin/bash
# Script para reconstruir el backend Python y crear el DMG
# Ejecutar en Terminal de macOS

set -e  # Salir si hay errores

echo "🎬 Video Analyzer Pro - Rebuild & Package"
echo "=========================================="

cd "$(dirname "$0")"
PROJECT_DIR=$(pwd)

# ============================================
# PASO 1: Reconstruir el ejecutable de Python
# ============================================
echo ""
echo "📦 PASO 1: Reconstruyendo ejecutable de Python..."
cd python

# Crear/activar entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "  Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

# Instalar dependencias
echo "  Instalando dependencias..."
pip install --upgrade pip > /dev/null
pip install pyinstaller flask opencv-python-headless numpy pillow > /dev/null 2>&1

# Eliminar ejecutable anterior
rm -f backend_executable

# Crear nuevo ejecutable
echo "  Compilando ejecutable (esto puede tardar 1-2 minutos)..."
pyinstaller --onefile \
    --name backend_executable \
    --hidden-import=flask \
    --hidden-import=werkzeug \
    --hidden-import=cv2 \
    --hidden-import=numpy \
    --hidden-import=PIL \
    --hidden-import=json \
    --hidden-import=uuid \
    --hidden-import=pathlib \
    --add-data "video_analyzer_engine.py:." \
    --add-data "report_generator.py:." \
    --add-data "export_premiere.py:." \
    --noconfirm \
    --clean \
    app.py 2>&1 | grep -E "(Building|INFO|WARNING|ERROR)" || true

# Mover ejecutable
mv dist/backend_executable ./
rm -rf build dist *.spec

# Verificar
if [ -f "backend_executable" ]; then
    echo "  ✅ Ejecutable creado correctamente"
    chmod +x backend_executable
else
    echo "  ❌ Error: No se pudo crear el ejecutable"
    exit 1
fi

deactivate
cd "$PROJECT_DIR"

# ============================================
# PASO 2: Construir la app Electron + DMG
# ============================================
echo ""
echo "🔨 PASO 2: Construyendo app Electron..."

# Limpiar builds anteriores
rm -rf release/* dist/*

# Reinstalar dependencias de Node (por si cambiaron)
echo "  Verificando dependencias de Node..."
npm install > /dev/null 2>&1

# Dar permisos a binarios
chmod +x python/backend_executable
chmod +x resources/ffmpeg/ffmpeg
chmod +x resources/ffmpeg/ffprobe

# Construir
echo "  Construyendo frontend y empaquetando..."
npm run build:mac 2>&1 | grep -E "(Built|vite|electron-builder|dmg)" || true

# ============================================
# PASO 3: Verificar resultado
# ============================================
echo ""
echo "=========================================="

DMG_FILE=$(find release -name "*.dmg" -type f 2>/dev/null | head -1)

if [ -n "$DMG_FILE" ]; then
    echo "✅ ¡BUILD EXITOSO!"
    echo ""
    echo "📁 Archivo DMG:"
    ls -lh "$DMG_FILE"
    echo ""
    echo "📍 Ubicación:"
    echo "   $PROJECT_DIR/$DMG_FILE"
    echo ""
    echo "🚀 Para instalar:"
    echo "   1. Abre el archivo DMG"
    echo "   2. Arrastra 'Video Analyzer Pro' a Applications"
    echo "   3. Abre la app (clic derecho → Abrir la primera vez)"
else
    echo "❌ Error: No se encontró el archivo DMG"
    echo "Revisa los logs arriba para más detalles"
    exit 1
fi
