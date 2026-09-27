"""
Definición de eventos para el ReAct Workflow del Chatbot Corporativo.
Estos eventos coordinan la comunicación entre los diferentes pasos del workflow.
"""

from llama_index.core.workflow import Event
from typing import List, Optional, Any


class PrepareEvent(Event):
    """Evento inicial que prepara el contexto para el workflow."""
    user_question: str


class QuerySplittingEvent(Event):
    """Evento que contiene la consulta dividida en subconsultas (1 a n)."""
    user_question: str
    subqueries: List[dict]  # [{"query": "..."}, ...] - Siempre se usa (mínimo 1)
    num_subqueries: int  # len(subqueries)


class IntentClassificationEvent(Event):
    """Evento con la clasificación de intención de la pregunta del usuario."""
    user_question: str
    intent_type: str  # "CONVERSACIONAL", "ANALÍTICA_SIMPLE", "ANALÍTICA_DATOS"
    justification: str  # Explicación de la clasificación
    requires_tools: bool  # True si necesita consultar datasets


class ToolRetrievalEvent(Event):
    """Evento que indica que las subconsultas están listas para recuperar herramientas."""
    user_question: str
    subqueries: List[dict]  # [{'query': '...'}, ...]
    num_subqueries: int


class ToolCallEvent(Event):
    """
    Evento para ejecutar herramientas usando FunctionAgents.

    NUEVA ARQUITECTURA (v3.0):
    - Un FunctionAgent se crea por cada subquery
    - Los agentes se ejecutan en paralelo con asyncio.gather
    - Cada agente respeta WORKFLOW_CONFIG['max_iterations'] para razonamiento iterativo
    - System prompt dinámico según metadata de la subquery
    """
    user_question: str
    # Campos para query splitting
    subqueries: List[dict] = []  # Siempre presente
    tools: dict = {}  # dict[subquery_dict: List[Tool]] - subconsulta → [tool_objects]


class ObservationEvent(Event):
    """Evento con los resultados de ejecutar las herramientas."""
    user_question: str
    tool_results: List[dict]  # [{"tool": "C001", "result": "..."}, ...]
    all_observations: str  # Texto concatenado de todas las observaciones


class DecisionEvent(Event):
    """Evento para decidir si necesitamos más herramientas o podemos responder."""
    user_question: str
    tool_results: List[dict]
    all_observations: str
    needs_more_tools: bool = False
    iteration: int = 0


class BusquedaEvent(Event):
    """Evento para búsqueda de datasets sin consultar datos."""
    user_question: str
    search_query: str  # Query de búsqueda procesada
    search_results: List[dict]  # Resultados de la búsqueda


class FinalAnswerEvent(Event):
    """Evento final con la respuesta generada."""
    user_question: str
    tool_results: List[dict]
    final_answer: str
