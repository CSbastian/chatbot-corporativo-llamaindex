#!/usr/bin/env python3
"""
Script para generar descripciones LLM de datasets del Chatbot Corporativo.

Este script permite:
1. Generar descripciones para todos los datasets
2. Generar descripción para un dataset específico
3. Regenerar solo datasets modificados
4. Forzar regeneración completa

Uso:
    # Generar todas las descripciones (solo nuevas y modificadas)
    python scripts/generar_descripciones_llm.py

    # Generar solo un dataset específico
    python scripts/generar_descripciones_llm.py --codigo C001

    # Forzar regeneración de todas las descripciones
    python scripts/generar_descripciones_llm.py --force-all

    # Modo silencioso (sin verbose)
    python scripts/generar_descripciones_llm.py --quiet

    # Desactivar detección de modificados
    python scripts/generar_descripciones_llm.py --no-regenerar-modificados

Ejemplos:
    python scripts/generar_descripciones_llm.py
    python scripts/generar_descripciones_llm.py --codigo P048
    python scripts/generar_descripciones_llm.py --force-all --quiet
"""

import sys
import os
import json
import glob
import argparse
from pathlib import Path

# Agregar directorio raíz al path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# Importaciones directas para evitar dependencias circulares
os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))

# Importar solo después de configurar el path
import importlib.util

def lazy_import_generator():
    """Importa el módulo generador de forma lazy para evitar dependencias circulares."""
    spec = importlib.util.spec_from_file_location(
        "llm_description_generator",
        BASE_DIR / "src" / "tools" / "llm_description_generator.py"
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError("No se pudo cargar el módulo llm_description_generator")

# Definir directorios directamente
METADATA_DIR = BASE_DIR / "json" / "metadata"
LLM_DESCRIPTIONS_FILE = BASE_DIR / "json" / "llm_descriptions.json"


def generar_un_dataset(codigo: str, verbose: bool = True):
    """
    Genera la descripción para un dataset específico.
    
    Args:
        codigo: Código del dataset (ej: 'C001', 'P048')
        verbose: Si True, muestra información detallada
    """
    # Lazy import
    gen = lazy_import_generator()
    
    # Normalizar código a mayúsculas
    codigo = codigo.upper()
    
    # Buscar archivo de metadata
    metadata_file = METADATA_DIR / f"{codigo.lower()}_metadata.json"
    
    if not metadata_file.exists():
        print(f"❌ Error: No se encontró metadata para el dataset '{codigo}'")
        print(f"   Ruta buscada: {metadata_file}")
        return False
    
    try:
        # Cargar metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"🎯 Generando descripción para dataset {codigo}")
            print(f"{'='*70}")
            print(f"📄 Título: {metadata.get('titulo', 'Sin título')}")
            print(f"📂 Categoría: {metadata.get('categoria', 'N/A')}")
            print(f"{'='*70}\n")
        
        # Cargar datos del dataset
        df = gen.cargar_dataset_por_codigo(codigo, verbose=verbose)
        
        # Generar descripción
        descripcion = gen.generar_descripcion_dataset(
            codigo=codigo,
            metadata=metadata,
            df=df,
            verbose=verbose
        )
        
        # Cargar descripciones existentes o crear nuevo dict
        if LLM_DESCRIPTIONS_FILE.exists():
            with open(LLM_DESCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            from datetime import datetime
            data = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "llm_model": "gpt-4o",
                    "temperature": 0.3,
                    "target_words": 300,
                    "total_datasets": 0,
                    "version": "1.0"
                },
                "descriptions": {}
            }
        
        # Actualizar descripción
        data["descriptions"][codigo] = descripcion
        data["metadata"]["total_datasets"] = len(data["descriptions"])
        
        # Guardar
        LLM_DESCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LLM_DESCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"✅ DESCRIPCIÓN GENERADA EXITOSAMENTE")
            print(f"{'='*70}")
            print(f"\n{descripcion}\n")
            print(f"{'='*70}")
            print(f"💾 Guardado en: {LLM_DESCRIPTIONS_FILE}")
            print(f"📊 Total de descripciones: {data['metadata']['total_datasets']}")
            print(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generando descripción para {codigo}: {str(e)}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description="Genera descripciones LLM para datasets del Chatbot Corporativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s                                    # Generar todas (nuevas y modificadas)
  %(prog)s --codigo C001                      # Solo dataset C001
  %(prog)s --force-all                        # Regenerar todas forzadamente
  %(prog)s --quiet                            # Modo silencioso
  %(prog)s --no-regenerar-modificados         # No detectar modificados
        """
    )
    
    parser.add_argument(
        '--codigo',
        type=str,
        help='Código del dataset específico a procesar (ej: C001, P048, M003)'
    )
    
    parser.add_argument(
        '--force-all',
        action='store_true',
        help='Forzar regeneración de todas las descripciones (ignora cache)'
    )
    
    parser.add_argument(
        '--no-regenerar-modificados',
        action='store_true',
        help='No regenerar descripciones de datasets modificados'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Modo silencioso (menos output)'
    )
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    # Verificar que existe OPENAI_API_KEY
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: No se encontró la variable de entorno OPENAI_API_KEY")
        print("   Por favor, configura tu API key de OpenAI en el archivo .env")
        return 1
    
    # Caso 1: Generar solo un dataset específico
    if args.codigo:
        success = generar_un_dataset(args.codigo, verbose=verbose)
        return 0 if success else 1
    
    # Caso 2: Generar todos los datasets
    regenerar_modificados = not args.no_regenerar_modificados
    
    try:
        # Lazy import
        gen = lazy_import_generator()
        
        stats = gen.generar_todas_las_descripciones(
            verbose=verbose,
            regenerar_modificados=regenerar_modificados,
            force_all=args.force_all
        )
        
        return 0 if stats['errores'] == 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        return 130
    
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
        import traceback
        if verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
