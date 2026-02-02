#!/usr/bin/env python3
"""
Script para crear el ícono de Video Analyzer Pro
Genera un PNG que luego se convierte a .icns en Mac
"""

import subprocess
from pathlib import Path

# Crear SVG del ícono
svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="1024" height="1024" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#3B82F6"/>
      <stop offset="100%" style="stop-color:#1E40AF"/>
    </linearGradient>
    <linearGradient id="shineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:rgba(255,255,255,0.3)"/>
      <stop offset="50%" style="stop-color:rgba(255,255,255,0.1)"/>
      <stop offset="100%" style="stop-color:rgba(255,255,255,0)"/>
    </linearGradient>
  </defs>

  <!-- Fondo con bordes redondeados (estilo macOS) -->
  <rect x="40" y="40" width="944" height="944" rx="180" ry="180" fill="url(#bgGrad)"/>

  <!-- Brillo sutil -->
  <rect x="40" y="40" width="944" height="472" rx="180" ry="180" fill="url(#shineGrad)"/>

  <!-- Texto VA -->
  <text x="512" y="620"
        font-family="SF Pro Display, -apple-system, BlinkMacSystemFont, Helvetica Neue, Arial, sans-serif"
        font-size="420"
        font-weight="700"
        fill="white"
        text-anchor="middle"
        letter-spacing="-20">VA</text>

  <!-- Línea decorativa inferior (representa video/timeline) -->
  <rect x="200" y="720" width="624" height="8" rx="4" fill="rgba(255,255,255,0.6)"/>
  <rect x="200" y="720" width="380" height="8" rx="4" fill="rgba(255,255,255,0.9)"/>

  <!-- Pequeños indicadores de análisis -->
  <circle cx="220" y="760" r="12" fill="#22C55E"/>
  <circle cx="260" y="760" r="12" fill="#22C55E"/>
  <circle cx="300" y="760" r="12" fill="#EAB308"/>
  <circle cx="340" y="760" r="12" fill="#22C55E"/>
</svg>
'''

# Guardar SVG
resources_dir = Path(__file__).parent / 'resources'
resources_dir.mkdir(exist_ok=True)

svg_path = resources_dir / 'icon.svg'
with open(svg_path, 'w') as f:
    f.write(svg_content)

print(f"SVG creado en: {svg_path}")
print()
print("Para convertir a .icns en tu Mac, ejecuta:")
print()
print("  # Instalar herramientas si no las tienes:")
print("  brew install librsvg")
print()
print("  # Crear iconset:")
print("  mkdir -p resources/icon.iconset")
print()
print("  # Generar diferentes tamaños:")
print("  for size in 16 32 64 128 256 512; do")
print("    rsvg-convert -w $size -h $size resources/icon.svg > resources/icon.iconset/icon_${size}x${size}.png")
print("    rsvg-convert -w $((size*2)) -h $((size*2)) resources/icon.svg > resources/icon.iconset/icon_${size}x${size}@2x.png")
print("  done")
print()
print("  # Crear .icns:")
print("  iconutil -c icns resources/icon.iconset -o resources/icon.icns")
print()
print("  # Limpiar:")
print("  rm -rf resources/icon.iconset resources/icon.svg")
