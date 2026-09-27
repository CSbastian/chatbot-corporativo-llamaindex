"""
Utilidades para el ReAct Workflow.
Funciones auxiliares para parseo de metadata y detección de tipos de resultado.
"""

import re
import json
from typing import Dict, Any


def parse_tool_metadata(description: str) -> Dict[str, str]:
    """
    Parsea la descripción del tool para extraer campos estructurados.

    La metadata viene en formato:
    "Titulo: X. Descripcion: Y. Categoria: Z. ..."

    Args:
        description: Texto de metadata del tool

    Returns:
        Diccionario con campos extraídos

    Example:
        >>> desc = "Titulo: Carga en puertos. Descripcion: Datos de carga..."
        >>> parse_tool_metadata(desc)
        {'titulo': 'Carga en puertos', 'descripcion': 'Datos de carga...'}
    """
    metadata = {}

    # Patterns comunes en metadata
    patterns = {
        "titulo": r"Titulo:\s*([^.]+)\.",
        "descripcion": r"Descripcion:\s*([^.]+)\.",
        "categoria": r"Categoria:\s*([^.]+)\.",
        "unidad": r"Unidad de medida:\s*([^.]+)\.",
        "escala_numerica": r"Escala numerica:\s*([^.]+)\.",
        "cobertura_temporal": r"Cobertura temporal:\s*([^.]+)\.",
        "palabras_claves": r"Palabras claves:\s*([^.]+)\."
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()
        else:
            metadata[key] = "N/A"

    return metadata


def detect_result_type(result_str: str) -> str:
    """
    Detecta el tipo de resultado retornado por PandasQueryEngine.

    Args:
        result_str: String del resultado

    Returns:
        Tipo detectado: "number", "table", "list", "text"

    Examples:
        >>> detect_result_type("42356.789")
        'number'
        >>> detect_result_type("Puerto | Carga\\nValpo | 1000\\nSA | 2000")
        'table'
        >>> detect_result_type("Item1, Item2, Item3")
        'list'
    """
    # Remover espacios al inicio/fin
    result_clean = result_str.strip()

    # Detectar número único
    try:
        # Intentar parsear como float (acepta formatos con comas)
        float(result_clean.replace(",", "").replace(".", "", result_clean.count(".") - 1))
        return "number"
    except (ValueError, AttributeError):
        pass

    # Detectar tabla (tiene múltiples líneas con separadores típicos)
    if "\n" in result_clean and any(sep in result_clean for sep in ["|", "\t", "  "]):
        return "table"

    # Detectar lista (múltiples líneas o muchas comas)
    if "\n" in result_clean or (", " in result_clean and result_clean.count(",") > 2):
        return "list"

    return "text"


def format_tool_results_as_json(tool_results: list) -> str:
    """
    Formatea los resultados de tools como JSON estructurado.

    Args:
        tool_results: Lista de diccionarios con resultados de tools

    Returns:
        String con JSON formateado y legible
    """
    formatted_results = []

    for tr in tool_results:
        if not tr.get("success", False):
            continue

        formatted_results.append({
            "dataset": tr.get("metadata", {}).get("titulo", "N/A"),
            "codigo": tr.get("dataset_code", "N/A"),
            "categoria": tr.get("metadata", {}).get("categoria", "N/A"),
            "resultado_tipo": tr.get("result_type", "text"),
            "resultado": tr.get("result", ""),
            "unidad": tr.get("metadata", {}).get("unidad", "N/A"),
            "escala_numerica": tr.get("metadata", {}).get("escala_numerica", "N/A"),
            "cobertura_temporal": tr.get("metadata", {}).get("cobertura_temporal", "N/A"),
            "codigo_pandas": tr.get("pandas_code", "N/A"),
            "subconsulta": tr.get("subquery_text", "")
        })

    return json.dumps(formatted_results, indent=2, ensure_ascii=False)


def build_memory_context(history: list, max_messages: int = 6) -> str:
    """
    Construye contexto de memoria para prompts.

    Args:
        history: Lista de ChatMessage de la memoria
        max_messages: Máximo de mensajes a incluir

    Returns:
        String formateado con el historial
    """
    if not history or len(history) == 0:
        return "Sin historial previo"

    # Tomar últimos N mensajes
    recent_history = history[-max_messages:]

    context_lines = []
    for msg in recent_history:
        role = "Usuario" if msg.role == "user" else "Asistente"
        # Limitar longitud de cada mensaje
        content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
        context_lines.append(f"{role}: {content}")

    return "\n".join(context_lines)


def parse_column_descriptions(ol_name: str, ol_descr: str) -> str:
    """
    Parsea las descripciones de columnas separadas por tilde (~) y las formatea.

    Args:
        ol_name: Nombres de columnas separados por comas (ej: "Año, Puerto, Carga")
        ol_descr: Descripciones separadas por tilde (ej: "año~puerto~cantidad de carga")

    Returns:
        String formateado con columnas y descripciones

    Example:
        >>> parse_column_descriptions(
        ...     "Año, Puerto, Carga",
        ...     "año~puerto donde opera~cantidad de carga en toneladas"
        ... )
        "  • Año: año\\n  • Puerto: puerto donde opera\\n  • Carga: cantidad de carga en toneladas"
    """
    if ol_name == "N/A" or ol_descr == "N/A":
        return "No disponible"

    # Separar nombres y descripciones
    nombres = [n.strip() for n in ol_name.split(",")]
    descripciones = [d.strip() for d in ol_descr.split("~")]

    # Validar que tengan la misma cantidad
    if len(nombres) != len(descripciones):
        # Fallback: mostrar nombres sin descripción
        return ", ".join(nombres)

    # Formatear como lista con bullet points
    formatted_lines = []
    for nombre, desc in zip(nombres, descripciones):
        formatted_lines.append(f"  • {nombre}: {desc}")

    return "\n".join(formatted_lines)


def truncate_note(nota: str, max_length: int = 300) -> str:
    """
    Trunca notas largas con elipsis si exceden el límite.

    Args:
        nota: Texto de la nota
        max_length: Longitud máxima (default 300 chars)

    Returns:
        Nota truncada o completa

    Example:
        >>> truncate_note("Esta es una nota muy larga..." * 20, 50)
        "Esta es una nota muy larga...Esta es una nota ..."
    """
    if not nota or nota == "N/A":
        return "Sin notas"

    nota_clean = nota.strip()
    if len(nota_clean) <= max_length:
        return nota_clean

    return nota_clean[:max_length].strip() + "..."
