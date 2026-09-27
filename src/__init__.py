"""
Chatbot del Chatbot Corporativo (Demo) - Arquitectura ReAct Workflow

Esta arquitectura implementa un flujo de trabajo ReAct explícito usando
LlamaIndex Workflow con 7 pasos secuenciales:

1. prepare: Inicialización de la consulta
2. classify_intent: Clasificación de intención (CONVERSACIONAL/BUSQUEDA/ANALÍTICA_SIMPLE/ANALÍTICA_DATOS)
3. query_splitting: Descomposición en subconsultas (1-n)
4. retrieve_tools: Búsqueda semántica de herramientas
5. call_tools: Ejecución de QueryEngineTools
6. decide_next: Validación de resultados
7. final_answer: Generación de respuesta

Características:
- Control granular de cada fase
- Eventos tipados para trazabilidad
- Trazabilidad completa con telemetría OpenTelemetry + Phoenix
- Todas las consultas procesadas uniformemente como 1-n subconsultas
- Memoria conversacional volátil

Uso:
    python main.py
    # o
    python -m src.cli.interactive

Tests:
    python run_tests.py
    # o
    python -m tests.test_poolDS --dataset tests/test_consultas.json
"""

from src.workflow.workflow import CorporateReActWorkflow
from src.workflow.events import (
    PrepareEvent,
    QuerySplittingEvent,
    ToolRetrievalEvent,
    ToolCallEvent,
    DecisionEvent,
    FinalAnswerEvent,
    IntentClassificationEvent,
    BusquedaEvent
)

__all__ = [
    'CorporateReActWorkflow',
    'PrepareEvent',
    'IntentClassificationEvent',
    'QuerySplittingEvent',
    'ToolRetrievalEvent',
    'ToolCallEvent',
    'DecisionEvent',
    'FinalAnswerEvent',
    'BusquedaEvent',
]
