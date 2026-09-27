#!/usr/bin/env python3
"""
Script para generar automáticamente un diccionario de datasets.

Extrae el código y título de cada archivo de metadata en json/metadata/
y genera un diccionario Python con la estructura:
{
    "C001": "Carga nacional transportada en modo aéreo",
    "C002": "Título del dataset C002",
    ...
}
"""

import json
from pathlib import Path


def generar_diccionario_datasets(metadata_dir: str = "json/metadata") -> dict:
    """
    Genera un diccionario con código y título de cada dataset.
    
    Args:
        metadata_dir: Ruta al directorio de metadata
        
    Returns:
        Diccionario {codigo: titulo}
    """
    metadata_path = Path(metadata_dir)
    datasets_dict = {}
    
    # Verificar que el directorio existe
    if not metadata_path.exists():
        raise FileNotFoundError(f"Directorio no encontrado: {metadata_dir}")
    
    # Procesar cada archivo JSON en el directorio
    archivos_metadata = sorted(metadata_path.glob("*_metadata.json"))
    
    print(f"📂 Procesando {len(archivos_metadata)} archivos de metadata...\n")
    
    for archivo in archivos_metadata:
        try:
            # Cargar metadata
            with open(archivo, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Extraer código y título
            codigo = metadata.get("codigo", "").upper()
            titulo = metadata.get("titulo", "Sin título")
            
            if codigo:
                datasets_dict[codigo] = titulo
                print(f"✓ {codigo}: {titulo}")
            else:
                print(f"⚠️  {archivo.name}: No se encontró código")
                
        except Exception as e:
            print(f"✗ Error procesando {archivo.name}: {e}")
    
    return datasets_dict


def guardar_como_python(datasets_dict: dict, output_file: str = "datasets_dict.py"):
    """
    Guarda el diccionario como un archivo Python ejecutable.
    
    Args:
        datasets_dict: Diccionario a guardar
        output_file: Nombre del archivo de salida
    """
    output_path = Path(output_file)
    
    # Generar contenido del archivo
    contenido = '''"""
Diccionario de datasets del Chatbot Corporativo.

Generado automáticamente desde json/metadata/
Código de dataset -> Título
"""

DATASETS = {
'''
    
    # Agregar cada entrada del diccionario
    for codigo in sorted(datasets_dict.keys()):
        titulo = datasets_dict[codigo]
        # Escapar comillas en el título
        titulo_escaped = titulo.replace('"', '\\"')
        contenido += f'    "{codigo}": "{titulo_escaped}",\n'
    
    contenido += '''}


def get_dataset_name(codigo: str) -> str | None:
    """
    Obtiene el nombre de un dataset por su código.
    
    Args:
        codigo: Código del dataset (ej: 'C001', 'P040')
        
    Returns:
        Nombre del dataset o None si no existe
    """
    return DATASETS.get(codigo.upper())


def get_all_codes() -> list:
    """Retorna lista de todos los códigos de datasets."""
    return list(DATASETS.keys())


def get_datasets_by_category(prefix: str) -> dict:
    """
    Obtiene datasets filtrados por prefijo de categoría.
    
    Args:
        prefix: Prefijo de categoría (ej: 'C', 'P', 'M')
        
    Returns:
        Diccionario filtrado
    """
    return {k: v for k, v in DATASETS.items() if k.startswith(prefix.upper())}


def get_code_from_name(nombre: str) -> str | None:
    """
    Obtiene el código de un dataset a partir de su nombre.
    
    Args:
        nombre: Nombre del dataset (completo o parcial)
        
    Returns:
        Código del dataset o None si no se encuentra
    """
    # Normalizar nombre de entrada
    nombre_normalizado = nombre.lower().strip()
    
    # Buscar coincidencia exacta
    for codigo, titulo in DATASETS.items():
        if titulo.lower().strip() == nombre_normalizado:
            return codigo
    
    # Si no hay coincidencia exacta, buscar coincidencia parcial
    for codigo, titulo in DATASETS.items():
        if nombre_normalizado in titulo.lower():
            return codigo
    
    return None


if __name__ == "__main__":
    # Ejemplo de uso
    print(f"Total de datasets: {len(DATASETS)}")
    print(f"\\nEjemplos:")
    for codigo in list(DATASETS.keys())[:3]:
        print(f"  {codigo}: {DATASETS[codigo]}")
'''
    
    # Guardar archivo
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(contenido)
    
    print(f"\n💾 Diccionario guardado en: {output_path}")


def guardar_como_json(datasets_dict: dict, output_file: str = "datasets_dict.json"):
    """
    Guarda el diccionario como JSON.
    
    Args:
        datasets_dict: Diccionario a guardar
        output_file: Nombre del archivo de salida
    """
    output_path = Path(output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(datasets_dict, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Diccionario guardado en: {output_path}")


if __name__ == "__main__":
    print("=" * 70)
    print("GENERADOR DE DICCIONARIO DE DATASETS")
    print("=" * 70)
    print()
    
    # Generar diccionario
    datasets_dict = generar_diccionario_datasets()
    
    print("\n" + "=" * 70)
    print(f"📊 RESUMEN: {len(datasets_dict)} datasets procesados")
    print("=" * 70)
    
    # Guardar en ambos formatos
    print("\n💾 Guardando archivos...\n")
    guardar_como_python(datasets_dict, "datasets_dict.py")
    guardar_como_json(datasets_dict, "datasets_dict.json")
    
    print("\n✅ Proceso completado exitosamente!")
    print("\nArchivos generados:")
    print("  - datasets_dict.py   (módulo Python)")
    print("  - datasets_dict.json (formato JSON)")
