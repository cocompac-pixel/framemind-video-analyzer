"""
XML Validator for Premiere Pro
Valida que el XML generado cumpla con el schema XMEML básico.
"""

import xml.etree.ElementTree as ET
import re
from pathlib import Path


class XMEMLValidator:
    """Validador básico de archivos XMEML para Premiere Pro"""
    
    # Namespace XMEML
    NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
    
    # FPS válidos para Premiere
    VALID_FPS = [23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60]
    
    @staticmethod
    def validate(xml_string):
        """
        Valida un string XML contra reglas básicas de XMEML
        
        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        errors = []
        
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return False, [f"XML mal formado: {e}"]
        
        # Validar elemento raíz
        if root.tag != 'xmeml':
            errors.append(f"Elemento raíz debe ser 'xmeml', encontrado: {root.tag}")
        
        # Validar versión
        version = root.get('version')
        if not version:
            errors.append("Atributo 'version' requerido en elemento raíz")
        
        # Validar secuencias
        sequences = root.findall('.//sequence')
        if not sequences:
            errors.append("Debe haber al menos una secuencia")
        
        for seq in sequences:
            seq_errors = XMEMLValidator._validate_sequence(seq)
            errors.extend(seq_errors)
        
        # Validar clipeitems
        clipitems = root.findall('.//clipitem')
        for clip in clipitems:
            clip_errors = XMEMLValidator._validate_clipitem(clip)
            errors.extend(clip_errors)
        
        # Validar files
        files = root.findall('.//file')
        file_ids = set()
        for f in files:
            file_errors = XMEMLValidator._validate_file(f, file_ids)
            errors.extend(file_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_sequence(seq_elem):
        """Validar elemento sequence"""
        errors = []
        
        # Verificar que tiene name
        name = seq_elem.find('name')
        if name is None or not name.text:
            errors.append("Sequence requiere elemento 'name'")
        
        # Verificar rate (fps)
        rate = seq_elem.find('.//rate/timebase')
        if rate is not None:
            try:
                fps = float(rate.text)
                if fps not in XMEMLValidator.VALID_FPS:
                    errors.append(f"FPS {fps} no es estándar para Premiere")
            except (ValueError, TypeError):
                errors.append(f"FPS inválido: {rate.text}")
        
        return errors
    
    @staticmethod
    def _validate_clipitem(clip_elem):
        """Validar elemento clipitem"""
        errors = []
        
        # Verificar ID único
        clip_id = clip_elem.get('id')
        if not clip_id:
            errors.append("Clipitem requiere atributo 'id'")
        elif not re.match(r'^[a-zA-Z0-9_-]+$', clip_id):
            errors.append(f"ID de clipitem inválido: {clip_id}")
        
        # Verificar name
        name = clip_elem.find('name')
        if name is None or not name.text:
            errors.append(f"Clipitem {clip_id} requiere elemento 'name'")
        
        # Verificar file reference
        file_ref = clip_elem.find('file')
        if file_ref is not None:
            file_id = file_ref.get('id')
            if not file_id:
                errors.append(f"Clipitem {clip_id} tiene file sin atributo 'id'")
        
        # Verificar in/out points
        in_point = clip_elem.find('in')
        out_point = clip_elem.find('out')
        
        if in_point is not None and out_point is not None:
            try:
                in_val = int(in_point.text or 0)
                out_val = int(out_point.text or 0)
                if out_val <= in_val:
                    errors.append(f"Clipitem {clip_id}: out ({out_val}) debe ser mayor que in ({in_val})")
            except ValueError:
                errors.append(f"Clipitem {clip_id}: in/out points inválidos")
        
        return errors
    
    @staticmethod
    def _validate_file(file_elem, file_ids):
        """Validar elemento file"""
        errors = []
        
        file_id = file_elem.get('id')
        if not file_id:
            errors.append("File requiere atributo 'id'")
            return errors
        
        # Verificar ID único
        if file_id in file_ids:
            errors.append(f"File ID duplicado: {file_id}")
        else:
            file_ids.add(file_id)
        
        # Verificar pathurl o name
        pathurl = file_elem.find('pathurl')
        name = file_elem.find('name')
        
        if pathurl is None and name is None:
            errors.append(f"File {file_id} requiere 'pathurl' o 'name'")
        
        # Validar caracteres en ID
        if not re.match(r'^[a-zA-Z0-9_-]+$', file_id):
            errors.append(f"File ID contiene caracteres inválidos: {file_id}")
        
        return errors
    
    @staticmethod
    def validate_file(xml_path):
        """Validar archivo XML desde path"""
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            return XMEMLValidator.validate(xml_content)
        except Exception as e:
            return False, [f"Error leyendo archivo: {e}"]
    
    @staticmethod
    def get_xml_info(xml_string):
        """Extraer información resumida del XML"""
        try:
            root = ET.fromstring(xml_string)
            
            info = {
                'version': root.get('version', 'unknown'),
                'sequences': len(root.findall('.//sequence')),
                'clipitems': len(root.findall('.//clipitem')),
                'files': len(root.findall('.//file')),
                'tracks': len(root.findall('.//track')),
            }
            
            # Extraer FPS
            rate = root.find('.//rate/timebase')
            if rate is not None:
                info['fps'] = rate.text
            
            return info
            
        except ET.ParseError:
            return {'error': 'XML mal formado'}
