#!/bin/bash
# Script para crear el DMG de Video Analyzer Pro
# Ejecutar en Terminal de macOS

echo "🎬 Video Analyzer Pro - Build DMG"
echo "=================================="

# Ir al directorio del proyecto
cd "$(dirname "$0")"

# Limpiar builds anteriores
echo "🧹 Limpiando builds anteriores..."
rm -rf release/* dist/* node_modules/.cache

# Reinstalar dependencias (necesario para la arquitectura correcta)
echo "📦 Reinstalando dependencias..."
rm -rf node_modules package-lock.json
npm install

# Verificar que todo esté correcto
echo "✅ Verificando archivos..."
if [ ! -f "python/backend_executable" ]; then
    echo "❌ Error: No se encontró python/backend_executable"
    exit 1
fi

if [ ! -f "resources/icon.icns" ]; then
    echo "❌ Error: No se encontró resources/icon.icns"
    exit 1
fi

if [ ! -f "resources/ffmpeg/ffmpeg" ]; then
    echo "❌ Error: No se encontró resources/ffmpeg/ffmpeg"
    exit 1
fi

echo "✅ Todos los archivos necesarios están presentes"

# Dar permisos de ejecución a los binarios
echo "🔐 Configurando permisos..."
chmod +x python/backend_executable
chmod +x resources/ffmpeg/ffmpeg
chmod +x resources/ffmpeg/ffprobe

# Construir el frontend
echo "🔨 Construyendo frontend (Vite)..."
npm run build:mac

echo ""
echo "=================================="
echo "✅ ¡Build completado!"
echo ""
echo "El archivo DMG está en: release/"
ls -la release/*.dmg 2>/dev/null || echo "Buscando en release/..."
ls -la release/

echo ""
echo "Para instalar:"
echo "1. Abre el archivo .dmg"
echo "2. Arrastra 'Video Analyzer Pro' a Applications"
echo "3. La primera vez, haz clic derecho > Abrir (por Gatekeeper)"
