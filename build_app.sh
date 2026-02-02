#!/bin/bash
# =============================================================================
# Script de Build para Video Analyzer Pro
# Ejecutar en Mac: ./build_app.sh
# =============================================================================

set -e  # Salir si hay error

echo "=========================================="
echo "  Video Analyzer Pro - Build Script"
echo "=========================================="
echo ""

cd "$(dirname "$0")"
ROOT_DIR=$(pwd)

# -----------------------------------------------------------------------------
# PASO 1: Verificar dependencias del sistema
# -----------------------------------------------------------------------------
echo "[1/5] Verificando dependencias del sistema..."

# Verificar Homebrew
if ! command -v brew &> /dev/null; then
    echo "  ❌ Homebrew no encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "  ✓ Homebrew OK"

# Verificar librsvg (para convertir SVG a PNG)
if ! command -v rsvg-convert &> /dev/null; then
    echo "  ⏳ Instalando librsvg..."
    brew install librsvg
fi
echo "  ✓ librsvg OK"

# Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "  ❌ Python3 no encontrado. Por favor instálalo."
    exit 1
fi
echo "  ✓ Python3 OK"

# Verificar Node.js
if ! command -v node &> /dev/null; then
    echo "  ❌ Node.js no encontrado. Por favor instálalo."
    exit 1
fi
echo "  ✓ Node.js OK"

echo ""

# -----------------------------------------------------------------------------
# PASO 2: Crear ícono .icns
# -----------------------------------------------------------------------------
echo "[2/5] Creando ícono de la aplicación..."

cd "$ROOT_DIR/resources"

# Crear iconset
mkdir -p icon.iconset

# Generar diferentes tamaños
for size in 16 32 64 128 256 512; do
    rsvg-convert -w $size -h $size icon.svg > icon.iconset/icon_${size}x${size}.png
    rsvg-convert -w $((size*2)) -h $((size*2)) icon.svg > icon.iconset/icon_${size}x${size}@2x.png
done

# Crear .icns
iconutil -c icns icon.iconset -o icon.icns

# Limpiar
rm -rf icon.iconset

echo "  ✓ Ícono creado: resources/icon.icns"
echo ""

# -----------------------------------------------------------------------------
# PASO 3: Instalar dependencias Python y crear ejecutable
# -----------------------------------------------------------------------------
echo "[3/5] Empaquetando backend Python..."

cd "$ROOT_DIR/python"

# Crear virtual environment si no existe
if [ ! -d "venv" ]; then
    echo "  ⏳ Creando virtual environment..."
    python3 -m venv venv
fi

# Activar venv
source venv/bin/activate

# Instalar dependencias
echo "  ⏳ Instalando dependencias Python..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Crear ejecutable con PyInstaller
echo "  ⏳ Creando ejecutable del backend (esto puede tardar unos minutos)..."
pyinstaller --clean --noconfirm build_backend.spec

# Mover ejecutable a la ubicación correcta
if [ -f "dist/backend" ]; then
    mv dist/backend ./backend_executable
    echo "  ✓ Backend empaquetado: python/backend_executable"
else
    echo "  ❌ Error creando el ejecutable"
    exit 1
fi

# Limpiar archivos temporales
rm -rf build dist __pycache__ *.spec 2>/dev/null || true

# Desactivar venv
deactivate

echo ""

# -----------------------------------------------------------------------------
# PASO 4: Instalar dependencias Node.js
# -----------------------------------------------------------------------------
echo "[4/5] Instalando dependencias Node.js..."

cd "$ROOT_DIR"

npm install

echo "  ✓ Dependencias Node.js instaladas"
echo ""

# -----------------------------------------------------------------------------
# PASO 5: Build de Electron
# -----------------------------------------------------------------------------
echo "[5/5] Creando aplicación Electron..."

npm run build:mac

echo ""
echo "=========================================="
echo "  ✅ BUILD COMPLETADO"
echo "=========================================="
echo ""
echo "Tu aplicación está en: $ROOT_DIR/release/"
echo ""
ls -la "$ROOT_DIR/release/"*.dmg 2>/dev/null || echo "(Busca el archivo .dmg en la carpeta release/)"
echo ""
echo "Para instalar:"
echo "  1. Abre el archivo .dmg"
echo "  2. Arrastra 'Video Analyzer Pro' a Aplicaciones"
echo "  3. Abre desde Aplicaciones"
echo ""
