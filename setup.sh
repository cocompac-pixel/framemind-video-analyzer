#!/bin/bash

# ===========================================
# Video Analyzer Pro - Setup Script
# ===========================================

echo "========================================"
echo "  Video Analyzer Pro - Setup"
echo "========================================"
echo

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verificar Node.js
echo -n "Verificando Node.js... "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}OK${NC} ($NODE_VERSION)"
else
    echo -e "${RED}NO ENCONTRADO${NC}"
    echo "  Instala Node.js desde https://nodejs.org"
    exit 1
fi

# 2. Verificar npm
echo -n "Verificando npm... "
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm -v)
    echo -e "${GREEN}OK${NC} (v$NPM_VERSION)"
else
    echo -e "${RED}NO ENCONTRADO${NC}"
    exit 1
fi

# 3. Verificar Python
echo -n "Verificando Python... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}OK${NC} ($PYTHON_VERSION)"
else
    echo -e "${RED}NO ENCONTRADO${NC}"
    echo "  Instala Python 3.8+ desde https://python.org"
    exit 1
fi

# 4. Verificar FFmpeg
echo -n "Verificando FFmpeg... "
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1)
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}NO ENCONTRADO${NC}"
    echo "  Para instalar FFmpeg:"
    echo "    Mac: brew install ffmpeg"
    echo "    Ubuntu: sudo apt install ffmpeg"
    echo ""
    echo -e "${YELLOW}NOTA: FFmpeg es necesario para el análisis de video${NC}"
fi

echo

# 5. Instalar dependencias de Node.js
echo "Instalando dependencias de Node.js..."
npm install

if [ $? -ne 0 ]; then
    echo -e "${RED}Error instalando dependencias de Node.js${NC}"
    exit 1
fi

echo

# 6. Instalar dependencias de Python
echo "Instalando dependencias de Python..."
cd python
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Advertencia: Algunos paquetes de Python no se instalaron${NC}"
fi

cd ..

echo
echo "========================================"
echo -e "  ${GREEN}Setup completado!${NC}"
echo "========================================"
echo
echo "Para ejecutar en modo desarrollo:"
echo "  npm run dev"
echo
echo "Para crear el build de producción:"
echo "  npm run build:mac"
echo
