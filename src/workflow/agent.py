from llama_index.core.agent import FunctionAgent
from typing import List



def create_agent_system_prompt(
    subquery: str,
    tool_metadata: dict,
    user_question: str,
    dataset_codes: list = None
) -> str:
    """
    Crea un system prompt dinámico para el FunctionAgent según la subquery.

    Args:
        subquery: Texto de la subconsulta específica
        tool_metadata: Metadata de las tools asignadas
        user_question: Pregunta original del usuario
        dataset_codes: Lista de códigos de datasets disponibles (nuevo)

    Returns:
        System prompt personalizado
    """
    categoria = tool_metadata.get('categoria', 'General')
    unidad = tool_metadata.get('unidad', 'N/A')
    titulo = tool_metadata.get('titulo', 'datos')
    dataset_id = tool_metadata.get('codigo', 'desconocido')

    # Construir sección de datasets disponibles
    if dataset_codes:
        codes_str = ", ".join(f"'{code}'" for code in dataset_codes)
        datasets_info = f"""DATASETS DISPONIBLES:
- Códigos: {codes_str}
- Dataset principal para esta subconsulta: '{dataset_id}'"""
    else:
        datasets_info = f"Dataset principal: '{dataset_id}'"

    prompt = f"""Eres un asistente especializado en análisis de datos del Chatbot Corporativo (Demo).

CONTEXTO:
- Pregunta original del usuario: "{user_question}"
- Tu tarea específica: {subquery}
- Categoría de datos: {categoria}
- Dataset: {titulo}
- Unidad de medida esperada: {unidad}

{datasets_info}

HERRAMIENTAS DISPONIBLES:
1. **analizar_dataset(codigo)**: Obtiene la estructura detallada de un dataset
   - ÚSALA PRIMERO para conocer columnas, tipos de datos y ejemplos
   - Input: código del dataset ('{dataset_id}' para esta subconsulta)
   - Output: JSON con estructura completa, ejemplos de datos, y metadata

2. **Herramienta(s) de consulta**: Ejecutan consultas sobre el dataset asignado
   - Úsalas DESPUÉS de conocer la estructura
   - Si la primera consulta falla, reformula basándote en la estructura real

PROTOCOLO DE EJECUCIÓN OBLIGATORIO:

PASO 1: INSPECCIÓN (CRÍTICO)
→ Llama a analizar_dataset('{dataset_id}') para conocer:
  • Nombres EXACTOS de columnas
  • Tipos de datos
  • Valores únicos disponibles (regiones, años, categorías, etc.)
  • Ejemplos de registros

PASO 2: CONSULTA
→ Usa la herramienta de consulta con los nombres de columnas EXACTOS obtenidos en PASO 1

PASO 3: VALIDACIÓN
→ Si falla o datos insuficientes:
  • Revisa la estructura del PASO 1
  • Ajusta filtros según valores únicos disponibles
  • Reintenta con consulta corregida
  • Máximo 2 reintentos

REGLAS CRÍTICAS:
- Usa SOLO las herramientas proporcionadas (NO uses conocimiento previo)
- NUNCA asumas nombres de columnas sin verificar
- Si después de 2 intentos no hay datos, explica claramente el problema
- Formatea números: 1.234.567 (punto para miles, coma para decimales)
- Siempre menciona la unidad: {unidad}
- Prioriza datos más recientes salvo indicación contraria

FORMATO DE RESPUESTA:
- Directo y conciso
- Incluye cifras numéricas cuando sean relevantes
- Menciona período temporal analizado
- Si no hay datos: "Tras analizar el dataset {dataset_id}, no se encontró información para [parámetro]"

Tu respuesta será consolidada con otras subconsultas, enfócate solo en TU parte.
"""
    return prompt


async def execute_agent_for_subquery(
    subquery_data: dict,
    subquery_index: int,
    tools: List,
    user_question: str,
    llm,
    verbose: bool,
    num_subqueries: int
) -> dict:
    """
    Crea y ejecuta un FunctionAgent para una subconsulta específica.

    Args:
        subquery_data: dict con {"query": "..."}
        subquery_index: índice de la subconsulta (0, 1, 2, ...)
        tools: Lista de herramientas para esta subconsulta
        user_question: Pregunta original del usuario
        llm: Instancia del LLM
        verbose: Control de logging
        num_subqueries: Total de subconsultas

    Returns:
        Diccionario con resultado estructurado o error
    """
    from src.utils.helpers import parse_tool_metadata, detect_result_type
    from src.core.config import WORKFLOW_CONFIG
    from src.tools.dataset_analysis_tool import crear_dataset_analysis_tool_contextual

    subquery_text = subquery_data["query"]

    max_agent_iterations = int(WORKFLOW_CONFIG.get("max_iterations", 3))

    # Logging inicial
    if num_subqueries > 1:
        print(f"  📋 Subconsulta {subquery_index+1}: '{subquery_text}'")

    if not tools:
        print(f"     ⚠️  No hay herramientas asignadas")
        return {
            "tool": "N/A",
            "dataset_code": "N/A",
            "result": "No se asignaron herramientas para esta subconsulta",
            "result_type": "text",
            "metadata": {},
            "pandas_code": "N/A",
            "success": False,
            "subquery_index": subquery_index,
            "subquery_text": subquery_text,
            "agent_iterations": 0,
            "agent_scratchpad": [],
            "tools_used": []
        }

    # Extraer metadata del primer tool para el prompt
    tool_metadata = {}
    tool_names = []
    dataset_names = []  # Nombres descriptivos de los datasets
    for tool in tools:
        tool_name = tool.metadata.name
        tool_names.append(tool_name)
        # Extraer nombre descriptivo del dataset desde technical_metadata
        if hasattr(tool, 'technical_metadata'):
            dataset_name = tool.technical_metadata.get('titulo', 'Dataset')
            dataset_names.append(dataset_name)
        if not tool_metadata:  # Tomar metadata del primer tool
            desc = tool.metadata.description if hasattr(tool.metadata, 'description') else ""
            tool_metadata = parse_tool_metadata(desc)
            # Si tenemos technical_metadata, usar directamente
            if hasattr(tool, 'technical_metadata'):
                tool_metadata = tool.technical_metadata

    if num_subqueries > 1:
        for i, tn in enumerate(tool_names):
            dataset_display = dataset_names[i] if i < len(dataset_names) else tn
            print(f"     🔧 Dataset: {dataset_display}")

    # NUEVO: Agregar herramienta de análisis de datasets contextual
    # Extraer códigos de los datasets recuperados para pasarlos a la herramienta
    dataset_codes = []
    for tool in tools:
        if hasattr(tool, 'technical_metadata'):
            codigo = tool.technical_metadata.get('codigo', '').upper()
            if codigo:
                dataset_codes.append(codigo)

    # Crear herramienta de análisis contextual con los códigos disponibles
    analysis_tool = crear_dataset_analysis_tool_contextual(dataset_codes)
    enhanced_tools = tools + [analysis_tool]

    if verbose and num_subqueries == 1:
        codes_display = ", ".join(dataset_codes) if dataset_codes else "N/A"
        print(f"     🔧 Herramienta adicional: analizar_dataset (códigos: {codes_display})")

    # Crear system prompt dinámico con códigos de datasets disponibles
    system_prompt = create_agent_system_prompt(
        subquery=subquery_text,
        tool_metadata=tool_metadata,
        user_question=user_question,
        dataset_codes=dataset_codes  # NUEVO: Pasar códigos al prompt
    )

    # Crear FunctionAgent
    try:
        agent = FunctionAgent(
            name=f"Agent_Subquery_{subquery_index+1}",
            description=f"Agente para responder: {subquery_text}",
            system_prompt=system_prompt,
            tools=enhanced_tools,  # Usar tools con análisis incluido
            llm=llm,
            verbose=verbose,
            timeout=60.0,  # Timeout por agente
            allow_parallel_tool_calls=False  # Ejecutar tools secuencialmente
        )

        if verbose:
            print(f"     ✓ Agente creado (max_iterations={max_agent_iterations})")

        # Ejecutar agente
        if num_subqueries > 1:
            print(f"     🤖 Ejecutando agente...")
        else:
            print(f"  🤖 Ejecutando agente para consulta...")

        # Ejecutar con max_iterations explícito
        handler = agent.run(
            user_msg=subquery_text,
            max_iterations=max_agent_iterations
        )

        # Await final result
        result = await handler

        # Extraer información del agente
        final_answer = result.response if hasattr(result, 'response') else str(result)

        # Intentar extraer scratchpad/reasoning
        agent_scratchpad = []
        if hasattr(result, 'sources') and result.sources:
            agent_scratchpad = [str(s) for s in result.sources]

        # Extraer código pandas si está disponible
        pandas_code = "No disponible"
        for tool in tools:
            try:
                if hasattr(tool, 'query_engine'):
                    qe = tool.query_engine
                    if hasattr(qe, 'last_pandas_code'):
                        pandas_code = qe.last_pandas_code or "No disponible"
                        break
                    elif hasattr(qe, '_last_pandas_code'):
                        pandas_code = qe._last_pandas_code or "No disponible"
                        break
            except:
                pass

        # Extraer nombre del dataset desde technical_metadata
        dataset_name = "Dataset desconocido"
        dataset_code = "N/A"
        if tools and hasattr(tools[0], 'technical_metadata'):
            dataset_name = tools[0].technical_metadata.get('titulo', 'Dataset desconocido')
            dataset_code = tools[0].technical_metadata.get('codigo', 'N/A')
        elif dataset_names:
            dataset_name = dataset_names[0]

        # Detectar tipo de resultado
        result_type = detect_result_type(str(final_answer))

        if num_subqueries > 1:
            print(f"        ✓ OK ({len(str(final_answer))} chars, tipo: {result_type})")
        else:
            print(f"     ✓ Resultado obtenido ({len(str(final_answer))} caracteres, tipo: {result_type})")

        return {
            "tool": ", ".join(dataset_names) if dataset_names else ", ".join(tool_names),
            "dataset_code": dataset_code,
            "dataset_name": dataset_name,
            "result": str(final_answer),
            "result_type": result_type,
            "metadata": tool_metadata,
            "pandas_code": pandas_code,
            "success": True,
            "subquery_index": subquery_index,
            "subquery_text": subquery_text,
            "agent_iterations": max_agent_iterations,
            "agent_scratchpad": agent_scratchpad,
            "tools_used": dataset_names if dataset_names else tool_names
        }

    except Exception as e:
        error_msg = f"Error en agente: {str(e)}"

        if num_subqueries > 1:
            print(f"        ✗ Error: {str(e)}")
        else:
            print(f"     ✗ Error: {str(e)}")

        return {
            "tool": ", ".join(dataset_names) if dataset_names else ", ".join(tool_names) if tool_names else "N/A",
            "dataset_code": "N/A",
            "dataset_name": dataset_names[0] if dataset_names else "Dataset desconocido",
            "result": error_msg,
            "result_type": "text",
            "metadata": tool_metadata,
            "pandas_code": "Error",
            "success": False,
            "subquery_index": subquery_index,
            "subquery_text": subquery_text,
            "agent_iterations": 0,
            "agent_scratchpad": [error_msg],
            "tools_used": dataset_names if dataset_names else tool_names
        }

