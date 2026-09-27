"""
Script temporal para extraer el texto_busqueda de un dataset específico.
Uso: python extraer_texto_busqueda.py [CODIGO_DATASET]
Ejemplo: python extraer_texto_busqueda.py P048
"""

import sys
import json
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from core.tools_factory import crear_dataset_tool
from core._internal_config import METADATA_DIR


def extraer_texto_busqueda(codigo_dataset: str):
    """
    Extrae el texto_busqueda de un dataset específico.

    Args:
        codigo_dataset: Código del dataset (ej: 'P048', 'C001')
    """
    codigo_upper = codigo_dataset.upper()
    codigo_lower = codigo_dataset.lower()

    # Buscar archivo de metadata
    metadata_file = METADATA_DIR / f"{codigo_lower}_metadata.json"

    if not metadata_file.exists():
        print(f"❌ No se encontró metadata para {codigo_upper}")
        print(f"   Buscado en: {metadata_file}")
        return

    # Cargar metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"\n{'='*80}")
    print(f"📋 EXTRAYENDO TEXTO DE BÚSQUEDA PARA: {codigo_upper}")
    print(f"{'='*80}\n")

    # Crear la herramienta (esto genera el texto_busqueda internamente)
    tool = crear_dataset_tool(codigo_upper, metadata)

    # Extraer el texto de búsqueda de la metadata de la herramienta
    texto_busqueda = tool.metadata.description

    print(f"📝 COMPONENTES DEL TEXTO DE BÚSQUEDA:")
    print(f"{'-'*80}")
    print(f"Titulo: {metadata.get('titulo', 'Sin título')}")
    print(f"Categoria: {metadata.get('categoria', 'General')}")
    print(f"Columnas: {metadata.get('ol_name', 'N/A')}")
    print(f"Palabras claves: {metadata.get('palabras_claves', 'N/A')}")
    print(f"\n{'-'*80}")
    print(f"📄 TEXTO COMPLETO DE BÚSQUEDA:")
    print(f"{'-'*80}")
    print(texto_busqueda)
    print(f"{'-'*80}\n")

    print(f"📊 ESTADÍSTICAS:")
    print(f"  - Longitud total: {len(texto_busqueda)} caracteres")
    print(f"  - Palabras: ~{len(texto_busqueda.split())} palabras")
    print(f"  - Nombre de la tool: {tool.metadata.name}")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extraer_texto_busqueda.py [CODIGO_DATASET]")
        print("\nEjemplos:")
        print("  python extraer_texto_busqueda.py P048")
        print("  python extraer_texto_busqueda.py C001")
        print("  python extraer_texto_busqueda.py M003")
        sys.exit(1)

    codigo = sys.argv[1]
    extraer_texto_busqueda(codigo)
