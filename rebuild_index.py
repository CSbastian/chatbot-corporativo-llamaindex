#!/usr/bin/env python3
"""
Script para regenerar el ObjectIndex de herramientas sin ejecutar el chatbot.

Útil para:
- Actualizaciones periódicas de datasets
- Agregar nuevos datasets
- Cambiar configuración de embeddings
- Mantenimiento programado

Uso:
    python rebuild_index.py                # Regenerar forzando
    python rebuild_index.py --check        # Solo verificar sin regenerar
    python rebuild_index.py --verbose      # Modo detallado
"""

import os
import sys
import argparse
import shutil
from pathlib import Path

# Agregar src/ al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.index_manager import get_tools_object_index
from src.core.config import PERSIST_DIR_TOOLS


def rebuild_index(force: bool = True, verbose: bool = True):
    """
    Regenera el ObjectIndex completo.

    Args:
        force: Si True, elimina el índice existente antes de regenerar
        verbose: Mostrar logs detallados
    """

    if force and os.path.exists(PERSIST_DIR_TOOLS):
        print(f"🗑️  Eliminando índice existente en {PERSIST_DIR_TOOLS}")
        shutil.rmtree(PERSIST_DIR_TOOLS)

    print("🔄 Regenerando ObjectIndex...")
    print("=" * 60)

    try:
        object_index = get_tools_object_index(verbose=verbose)

        # Verificar cuántas herramientas se cargaron
        # ObjectIndex usa object_node_mapping para acceder a las herramientas
        from src.tools.tools_factory import crear_todas_las_tools
        tools = crear_todas_las_tools(verbose=False)
        num_tools = len(tools)
        print(f"📁 Ubicación: {PERSIST_DIR_TOOLS}")

        return True

    except Exception as e:
        print("=" * 60)
        print(f"❌ Error al regenerar ObjectIndex: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_index_status():
    """Verifica el estado del índice sin modificarlo."""

    print("🔍 Verificando estado del ObjectIndex...")
    print("=" * 60)

    if not os.path.exists(PERSIST_DIR_TOOLS):
        print(f"⚠️  No existe índice en {PERSIST_DIR_TOOLS}")
        print("   Ejecuta con regeneración para crearlo.")
        return False

    try:
        # Cargar índice existente
        from src.tools.tools_factory import crear_todas_las_tools
        from llama_index.core.objects import ObjectIndex, SimpleToolNodeMapping

        tools = crear_todas_las_tools(verbose=False)
        tool_mapping = SimpleToolNodeMapping.from_objects(tools)

        object_index = ObjectIndex.from_persist_dir(
            persist_dir=str(PERSIST_DIR_TOOLS),
            object_node_mapping=tool_mapping
        )

        # El número de herramientas viene del tool_mapping cargado
        num_tools = len(tools)
        # Listar archivos del índice
        print("\n📦 Archivos del índice:")
        for file in sorted(os.listdir(PERSIST_DIR_TOOLS)):
            filepath = os.path.join(PERSIST_DIR_TOOLS, file)
            size = os.path.getsize(filepath) / 1024  # KB
            print(f"   - {file} ({size:.1f} KB)")

        return True

    except Exception as e:
        print(f"❌ Error al verificar índice: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Regenerar ObjectIndex de herramientas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python rebuild_index.py                 # Regenerar forzando
  python rebuild_index.py --check         # Solo verificar
  python rebuild_index.py --no-force      # Regenerar sin eliminar
  python rebuild_index.py -v              # Modo verbose
        """
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Solo verificar el estado del índice sin regenerar"
    )

    parser.add_argument(
        "--no-force",
        action="store_true",
        help="No eliminar el índice existente antes de regenerar"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=True,
        help="Mostrar logs detallados (default: True)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso (desactiva verbose)"
    )

    args = parser.parse_args()

    # Determinar verbose
    verbose = args.verbose and not args.quiet

    # Verificar API key
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: No se encontró OPENAI_API_KEY en .env")
        sys.exit(1)

    # Ejecutar operación
    if args.check:
        success = check_index_status()
    else:
        force = not args.no_force
        success = rebuild_index(force=force, verbose=verbose)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
