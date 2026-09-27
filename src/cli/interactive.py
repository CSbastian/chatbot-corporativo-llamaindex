"""
Chatbot del Chatbot Corporativo - 100% LlamaIndex Architecture
Punto de entrada principal usando ReAct Workflow.
"""

import asyncio
from dotenv import load_dotenv

from src.core.index_manager import get_tools_object_index
from src.core.telemetry import setup_telemetry
from src.core.database import init_db
from src.workflow.workflow import CorporateReActWorkflow
from src.core.config import WORKFLOW_TIMEOUT

from llama_index.core import set_global_handler

# Cargar variables de entorno
load_dotenv()

# Configurar telemetría
setup_telemetry()


async def main():
    """
    Función principal del chatbot con soporte de memoria conversacional.
    """
    print("\n" + "="*70)
    print("🇨🇱  CHATBOT CHATBOT CORPORATIVO")
    print("    Arquitectura: 100% LlamaIndex ReAct Workflow")
    print("    🧠 Memoria conversacional: ACTIVADA")
    print("    💾 Base de datos: ACTIVADA")
    print("="*70 + "\n")

    # NUEVO: Inicializar base de datos
    print("Inicializando sistema...")
    try:
        init_db()
        print("✓ Base de datos inicializada correctamente")
    except Exception as e:
        print(f"⚠️  Error inicializando DB: {e}")
    
    # Cargar ObjectIndex con todas las herramientas
    object_index = get_tools_object_index()
    print(f"✓ Sistema inicializado correctamente\n")

    # Crear instancia del workflow (UNA VEZ para toda la sesión)
    workflow = CorporateReActWorkflow(object_index=object_index, timeout=WORKFLOW_TIMEOUT)

    print("="*70)
    print("💬 Modo interactivo activado")
    print("   Comandos disponibles:")
    print("   • 'salir' / 'exit' / 'quit' - Terminar sesión")
    print("   • 'reset' / 'limpiar' - Limpiar memoria conversacional")
    print("   • 'historia' - Ver historial de conversación")
    print("="*70 + "\n")

    # Bucle de conversación
    while True:
        try:
            # Solicitar pregunta al usuario
            user_input = input("👤 Tu pregunta: ").strip()

            if not user_input:
                continue

            # Comandos de salida
            if user_input.lower() in ["salir", "exit", "quit", "q"]:
                print("\n👋 ¡Hasta luego! (memoria eliminada)\n")
                break
            
            # Comando para limpiar memoria
            if user_input.lower() in ["reset", "limpiar", "borrar", "clear"]:
                workflow.reset_memory()
                print("✓ Memoria conversacional limpiada. Nueva conversación iniciada.\n")
                continue
            
            # Comando para ver historial
            if user_input.lower() in ["historia", "historial", "history"]:
                history = workflow.get_chat_history()
                if len(history) == 0:
                    print("\n📝 No hay historial conversacional aún.\n")
                else:
                    print(f"\n📜 Historial ({len(history)//2} intercambio(s)):")
                    print("="*60)
                    for msg in history:
                        role = "👤 Usuario" if msg.role == "user" else "🤖 Asistente"
                        preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        print(f"{role}: {preview}")
                    print("="*60 + "\n")
                continue

            # Ejecutar workflow (mantiene memoria entre llamadas)
            result = await workflow.run(user_question=user_input)

            # Mostrar resultado
            if result and isinstance(result, dict):
                answer = result.get("answer", "No se pudo generar respuesta")
                sources = result.get("sources", [])
                success = result.get("success", False)

                if success:
                    print(f"\n🤖 Respuesta:\n{answer}\n")
                    if sources:
                        print(f"📚 Fuentes: {', '.join(sources)}\n")
                else:
                    print(f"\n⚠️  {answer}\n")
            else:
                print("\n⚠️  Error: No se recibió respuesta del workflow\n")

            print("-" * 70 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego! (memoria eliminada)\n")
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {str(e)}\n")
            import traceback
            traceback.print_exc()
            print("\nIntenta con otra pregunta.\n")


def run_single_query(question: str):
    """
    Ejecuta una sola consulta (útil para testing).

    Args:
        question: Pregunta del usuario

    Returns:
        dict con la respuesta
    """
    async def _run():
        object_index = get_tools_object_index()
        workflow = CorporateReActWorkflow(object_index=object_index, timeout=WORKFLOW_TIMEOUT)
        result = await workflow.run(user_question=question)
        return result

    return asyncio.run(_run())


if __name__ == "__main__":
    asyncio.run(main())
