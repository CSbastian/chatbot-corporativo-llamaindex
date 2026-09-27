"""
Herramienta de análisis de datasets para function calling.
Proporciona información estructurada sobre un dataset específico.
"""
import json
from typing import Optional
from llama_index.core.tools import FunctionTool


def analizar_dataset(codigo: str) -> str:
    """
    Obtiene un análisis detallado de un dataset específico del Chatbot Corporativo.

    Útil cuando necesitas conocer la estructura, columnas, tipos de datos,
    y ejemplos de datos de un dataset antes de consultarlo.

    Args:
        codigo: Código del dataset (ej: 'C018', 'P048', 'dataset_001').
                Puede estar en mayúsculas o minúsculas.

    Returns:
        JSON string con información estructurada del dataset:
        - codigo: Código del dataset
        - titulo: Nombre descriptivo del dataset
        - categoria: Categoría temática
        - descripcion: Descripción detallada
        - filas: Número total de registros
        - columnas: Lista de nombres de columnas
        - tipos_datos: Diccionario con tipo de dato de cada columna
        - muestra_datos: Primeros 3 registros de ejemplo
        - columnas_numericas: Lista de columnas con datos numéricos
        - valores_unicos: Diccionario con conteo de valores únicos por columna (solo si < 50)
        - metadata_adicional: Información sobre cobertura, fuente, unidad, etc.

    Ejemplo de uso:
        >>> analizar_dataset("C018")
        >>> analizar_dataset("p048")
    """
    from src.core.index_manager import get_pandas_engine
    import os
    import glob
    from src.core.config import METADATA_DIR, DATA_DIR

    # Normalizar código del dataset
    codigo_normalized = codigo.upper().strip()
    codigo_lower = codigo.lower().strip()

    try:
        # 1. Obtener el motor pandas (que carga el DataFrame)
        motor = get_pandas_engine(codigo_normalized, verbose=False)
        df = motor._df

        # 2. Cargar metadata del dataset
        metadata = {}
        metadata_path = os.path.join(str(METADATA_DIR), f"{codigo_lower}_metadata.json")

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

        # 3. Análisis básico del DataFrame
        info = {
            "codigo": codigo_normalized,
            "titulo": metadata.get('titulo', 'Sin título'),
            "categoria": metadata.get('categoria', 'N/A'),
            "descripcion": metadata.get('descripcion', 'Sin descripción'),
            "filas": len(df),
            "columnas": list(df.columns),
            "tipos_datos": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "muestra_datos": df.head(3).to_dict('records'),
            "columnas_numericas": df.select_dtypes(include=['number']).columns.tolist(),
            "valores_unicos": {
                col: int(df[col].nunique())
                for col in df.columns
                if df[col].nunique() < 50  # Solo si hay menos de 50 valores únicos
            },
            "metadata_adicional": {
                "unidad": metadata.get('unidad', 'N/A'),
                "escala_numerica": metadata.get('escala_numerica', 'N/A'),
                "cobertura_temporal": metadata.get('cobertura_temporal', 'N/A'),
                "cobertura_espacial": metadata.get('cobertura_espacial', 'N/A'),
                "fuente": metadata.get('creador', 'N/A'),
                "frecuencia_actualizacion": metadata.get('frecuencia_actualizacion', 'N/A'),
                "desagregacion_temporal": metadata.get('desagregacion_temporal', 'N/A'),
                "desagregacion_espacial": metadata.get('desagregacion_espacial', 'N/A'),
                "palabras_claves": metadata.get('palabras_claves', [])
            }
        }

        # 4. Formatear respuesta como JSON legible
        return json.dumps(info, indent=2, ensure_ascii=False)

    except FileNotFoundError as e:
        error_response = {
            "error": "Dataset no encontrado",
            "codigo_buscado": codigo_normalized,
            "mensaje": f"No se encontró ningún dataset con el código '{codigo_normalized}'. Verifica que el código sea correcto.",
            "sugerencia": "Los códigos de datasets suelen tener el formato 'C001', 'P048', etc."
        }
        return json.dumps(error_response, indent=2, ensure_ascii=False)

    except Exception as e:
        error_response = {
            "error": "Error al analizar dataset",
            "codigo": codigo_normalized,
            "mensaje": str(e),
            "tipo_error": type(e).__name__
        }
        return json.dumps(error_response, indent=2, ensure_ascii=False)


def crear_dataset_analysis_tool() -> FunctionTool:
    """
    Crea la FunctionTool para análisis de datasets.

    Esta herramienta se puede agregar a los FunctionAgents para que puedan
    inspeccionar la estructura de los datasets antes de hacer consultas.

    Returns:
        FunctionTool configurada para análisis de datasets
    """
    return FunctionTool.from_defaults(
        fn=analizar_dataset,
        name="analizar_dataset",
        description=(
            "Obtiene información estructurada sobre un dataset del Chatbot Corporativo. "
            "Retorna: título, descripción, columnas, tipos de datos, ejemplos de datos, "
            "estadísticas básicas, metadata (unidad, cobertura temporal/espacial, fuente). "
            "Útil para conocer la estructura de un dataset antes de consultarlo. "
            "Input: código del dataset (ej: 'C018', 'P048')."
        )
    )


def crear_dataset_analysis_tool_contextual(dataset_codes: list) -> FunctionTool:
    """
    Crea una FunctionTool contextual para análisis de datasets específicos.

    Esta versión incluye en la descripción los códigos de los datasets disponibles,
    ayudando al agente a saber qué datasets puede analizar.

    Args:
        dataset_codes: Lista de códigos de datasets disponibles (ej: ['C018', 'P048'])

    Returns:
        FunctionTool configurada con contexto de datasets disponibles
    """
    if dataset_codes:
        codes_str = ", ".join(f"'{code}'" for code in dataset_codes)
        description = (
            f"Obtiene información estructurada sobre un dataset del Chatbot Corporativo. "
            f"DATASETS DISPONIBLES PARA ESTA CONSULTA: {codes_str}. "
            f"IMPORTANTE: Usa PRIMERO esta herramienta para conocer la estructura (columnas, tipos de datos, ejemplos) "
            f"ANTES de ejecutar cualquier consulta. "
            f"Retorna: título, descripción, columnas, tipos de datos, ejemplos de datos, "
            f"estadísticas básicas, metadata (unidad, cobertura temporal/espacial, fuente). "
            f"Input: código del dataset (uno de los códigos disponibles mencionados arriba)."
        )
    else:
        description = (
            "Obtiene información estructurada sobre un dataset del Chatbot Corporativo. "
            "Retorna: título, descripción, columnas, tipos de datos, ejemplos de datos, "
            "estadísticas básicas, metadata (unidad, cobertura temporal/espacial, fuente). "
            "Útil para conocer la estructura de un dataset antes de consultarlo. "
            "Input: código del dataset (ej: 'C018', 'P048')."
        )

    return FunctionTool.from_defaults(
        fn=analizar_dataset,
        name="analizar_dataset",
        description=description
    )


# Exportar tanto la función como los factories
__all__ = [
    'analizar_dataset',
    'crear_dataset_analysis_tool',
    'crear_dataset_analysis_tool_contextual'
]
