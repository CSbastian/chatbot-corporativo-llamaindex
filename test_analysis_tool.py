"""
Script de prueba para verificar que la herramienta de análisis
recibe correctamente los códigos de datasets.
"""
import asyncio
from src.core.index_manager import get_tools_object_index
from src.workflow.workflow import CorporateReActWorkflow


async def test_analysis_tool():
    """Prueba la integración de la herramienta de análisis contextual."""

    print("=" * 80)
    print("TEST: Herramienta de análisis contextual con códigos de datasets")
    print("=" * 80)
    print()

    # Crear workflow
    print("📦 Cargando ObjectIndex...")
    object_index = get_tools_object_index()
    workflow = CorporateReActWorkflow(object_index=object_index, verbose=True)

    print("✓ Workflow creado\n")

    # Probar con pregunta que requiere análisis de datos
    test_question = "¿Cuánta carga se movilizó en el puerto de Valparaíso en 2023?"

    print(f"🔍 Pregunta de prueba: {test_question}\n")
    print("=" * 80)
    print()

    # Ejecutar workflow
    result = await workflow.run(user_question=test_question)

    print()
    print("=" * 80)
    print("📊 RESULTADO DEL TEST")
    print("=" * 80)
    print(f"Éxito: {result.get('success', False)}")
    print(f"Fuentes: {result.get('sources', [])}")
    print(f"\nRespuesta:\n{result.get('answer', 'N/A')}")
    print("=" * 80)

    return result


if __name__ == "__main__":
    asyncio.run(test_analysis_tool())
