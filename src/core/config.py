"""
Configuración completa para ReAct Workflow.

Este archivo contiene TODAS las configuraciones necesarias para el chatbot,
incluyendo directorios, LLMs, embeddings, y parámetros del workflow.
"""

import os
from pathlib import Path
from llama_index.llms.openai import OpenAI


# DIRECTORIOS BASE
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "json" / "data"
METADATA_DIR = BASE_DIR / "json" / "metadata"
RAW_METADATA_DIR = BASE_DIR / "json" / "raw_metadata"
LOGS_DIR = BASE_DIR / "logs"

# Persistencia
PERSIST_DIR_TOOLS = BASE_DIR / "storage_tools"
PERSIST_DIR_METADATA = BASE_DIR / "storage_metadata"


# EMBEDDINGS
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


# METADATA EXTRACTOR
METADATA_SAMPLE_LIMIT = 15  # Límite de muestras representativas por columna


# LLM DESCRIPTION GENERATOR
LLM_DESCRIPTIONS_FILE = BASE_DIR / "json" / "llm_descriptions.json"  # Archivo con descripciones generadas
LLM_DESCRIPTION_TARGET_WORDS = 300  # Objetivo de palabras por descripción
LLM_DESCRIPTION_MODEL = "gpt-5.1"  # Modelo para generar descripciones
LLM_DESCRIPTION_TEMPERATURE = 0.3  # Temperatura para generación (ligeramente creativa)
USE_LLM_DESCRIPTIONS = True  # Flag para A/B testing (False = método original, True = descripciones LLM)


# LLM EVALUADOR PARA TESTS
LLM_EVALUADOR_MODEL = "gpt-4o-mini"
LLM_EVALUADOR_TEMPERATURE = 0


def get_llm_evaluador():
    """
    Retorna instancia configurada del LLM evaluador para tests.
    """
    return OpenAI(
        model=LLM_EVALUADOR_MODEL,
        temperature=LLM_EVALUADOR_TEMPERATURE
    )


# TELEMETRÍA
TELEMETRY_ENDPOINT = "http://localhost:6006/v1/traces"  # HTTP endpoint para Phoenix (específico ReAct)
TELEMETRY_UI_URL = "http://localhost:6006"              # UI URL (compartido)


# DATABASE CONFIGURATION
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///chatbot.db")


# MODELOS LLM PARA REACT WORKFLOW
# Modelo "general" (compatibilidad hacia atrás)
LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 4096

# Modelos especializados por etapa del workflow
LLM_INTENT_MODEL = os.getenv("LLM_INTENT_MODEL", "gpt-5.1")
LLM_SPLITTING_MODEL = os.getenv("LLM_SPLITTING_MODEL", "gpt-5.1")
LLM_AGENT_MODEL = os.getenv("LLM_AGENT_MODEL", "gpt-5.1")
LLM_ANSWER_MODEL = os.getenv("LLM_ANSWER_MODEL", "gpt-5.1")

LLM_INTENT_TEMPERATURE = 0
LLM_SPLITTING_TEMPERATURE = 0
LLM_AGENT_TEMPERATURE = 0
LLM_ANSWER_TEMPERATURE = 0


def get_llm():
    """LLM genérico para compatibilidad con código legado."""
    return OpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


def get_llm_intent():
    """LLM usado para la clasificación de intención."""
    return OpenAI(
        model=LLM_INTENT_MODEL,
        temperature=LLM_INTENT_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


def get_llm_splitting():
    """LLM usado para la división de consultas (query splitting)."""
    return OpenAI(
        model=LLM_SPLITTING_MODEL,
        temperature=LLM_SPLITTING_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


def get_llm_agent():
    """LLM usado por los FunctionAgents (function calling sobre datasets)."""
    return OpenAI(
        model=LLM_AGENT_MODEL,
        temperature=LLM_AGENT_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


def get_llm_answer():
    """LLM usado para redactar las respuestas finales al usuario."""
    return OpenAI(
        model=LLM_ANSWER_MODEL,
        temperature=LLM_ANSWER_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


# WORKFLOW REACT CONFIGURATION
TOOL_RETRIEVAL_TOP_K = 2         # Top-K herramientas a recuperar (workflow.py)
MAX_REASONING_ITERATIONS = 5     # Máximo de iteraciones ReAct
VERBOSE_WORKFLOW = True          # Logging detallado
ENABLE_MULTI_TOOL = True         # Permitir múltiples herramientas

# Query Splitting (Multi-Dataset)
ENABLE_QUERY_SPLITTING = True    # Activar/desactivar feature
QUERY_SPLITTING_TOP_K = 2        # Top-K herramientas por subconsulta
MAX_SUBQUERIES = 5               # Máximo de subconsultas permitidas

# Workflow Timeout
WORKFLOW_TIMEOUT = 300           # Timeout en segundos para workflow


# MEMORIA CONVERSACIONAL (específico)
REACT_MEMORY_TOKEN_LIMIT = 6000  # Límite de tokens para memoria conversacional
REACT_ENABLE_MEMORY = True       # Activar/desactivar memoria conversacional


# MENSAJE CONVERSACIONAL PREDEFINIDO
CONVERSATIONAL_RESPONSE = """Bienvenido al asistente del Chatbot Corporativo (Demo).

Este sistema le permite consultar y analizar datos oficiales sobre:
- Movimiento de carga en puertos
- Transporte terrestre, aéreo y marítimo
- Comercio exterior
- Indicadores logísticos y conectividad
- Estadísticas de vehículos y siniestros viales

Puede realizar consultas de datos específicos o solicitar información sobre los datasets disponibles.

¿En qué puedo asistirle?"""


# SYSTEM PROMPT
SYSTEM_PROMPT = """Eres un asistente experto en datos logísticos del país del Chatbot Corporativo.

⚠️ RESTRICCIÓN CRÍTICA - LEE ESTO PRIMERO:
ESTÁ ABSOLUTAMENTE PROHIBIDO responder preguntas usando tu conocimiento base o entrenamiento.
NUNCA digas cosas como "no tengo acceso a datos de [año]" o "mi entrenamiento llega hasta [fecha]".
Todos los datos que necesitas están en los datasets disponibles.
Si una pregunta requiere datos, estos ya fueron consultados en las herramientas.

Tu objetivo es ayudar a los usuarios a encontrar y analizar datos sobre:
- Movimiento de carga en puertos
- Transporte terrestre, aéreo y marítimo
- Comercio exterior
- Indicadores logísticos y conectividad
- Estadísticas de vehículos y siniestros

METODOLOGÍA DE TRABAJO OBLIGATORIA:
1. Analiza cuidadosamente la pregunta del usuario
2. Identifica qué datos necesitas (puede ser de múltiples fuentes)
   - ⚠️ REGLA ESPECIAL TRANSPORTE: Si la pregunta menciona "transporte" o "carga"
     sin especificar el medio (terrestre/aéreo/marítimo), los datos deben incluir
     información de los 3 medios de transporte cuando estén disponibles
   - Ejemplo: "¿Cuánto transporte hubo en 2023?" → Debe consultar terrestre, aéreo Y marítimo
3. Los datos ya fueron consultados en las herramientas disponibles
4. Presenta la información de forma clara y precisa

REGLAS CRÍTICAS:
- ❌ PROHIBIDO: Responder desde tu conocimiento base
- ❌ PROHIBIDO: Decir "no tengo acceso a datos de [año/tema]"
- ❌ PROHIBIDO: Mencionar limitaciones de tu entrenamiento
- ✅ OBLIGATORIO: Usar SOLO los datos proporcionados por las herramientas
- ✅ OBLIGATORIO: Si las herramientas no retornaron datos, di "No encontré datos en los datasets consultados"
- ✅ SIEMPRE menciona la fuente del dataset en tu respuesta
- ✅ Formatea números legiblemente (ej: 1.234.567)
- ✅ Si necesitas datos de múltiples datasets, úsalos todos
- ✅ Sé preciso con fechas y unidades de medida"""


# CONFIGURACIÓN CONSOLIDADA (específico)
WORKFLOW_CONFIG = {
    "top_k": TOOL_RETRIEVAL_TOP_K,
    "max_iterations":   MAX_REASONING_ITERATIONS,
    "verbose": VERBOSE_WORKFLOW,
    "enable_multi_tool": ENABLE_MULTI_TOOL,
    "enable_query_splitting": ENABLE_QUERY_SPLITTING,
    "splitting_top_k": QUERY_SPLITTING_TOP_K,
    "max_subqueries": MAX_SUBQUERIES,
    "enable_memory": REACT_ENABLE_MEMORY,
    "memory_token_limit": REACT_MEMORY_TOKEN_LIMIT
}
