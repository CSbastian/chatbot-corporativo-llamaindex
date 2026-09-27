"""
Fábrica de QueryEngineTools para el sistema de consulta de datos.
Convierte cada dataset en una herramienta de consulta indexable.

SOPORTE A/B TESTING:
- Método original: texto_busqueda concatenado desde metadata
- Método LLM: descripciones generadas por GPT-4o

Configurable via src.core.config.USE_LLM_DESCRIPTIONS
"""
import os
import json
import glob
from pathlib import Path
from typing import List, Optional

from llama_index.core.tools import QueryEngineTool
from llama_index.core.tools.types import ToolMetadata

from src.core.config import METADATA_DIR, DATA_DIR, USE_LLM_DESCRIPTIONS


def crear_dataset_tool(codigo: str, metadata: dict, verbose: bool = False, use_llm_desc: Optional[bool] = None) -> QueryEngineTool:
    """
    Crea una QueryEngineTool para un dataset específico.

    MÉTODO DE DESCRIPCIÓN:
    - Original (default): Concatenación estructurada de metadata
    - LLM: Descripción natural generada por GPT-4o

    La descripción se usa para búsqueda semántica en el ObjectIndex.

    Args:
        codigo: Código del dataset (ej: 'C001')
        metadata: Diccionario con metadata del dataset
        verbose: Si True, muestra información de debug
        use_llm_desc: Si True, usa descripciones LLM. Si None, usa config global.

    Returns:
        QueryEngineTool configurada para este dataset
    """
    # Lazy import to avoid circular dependency
    from src.core.index_manager import get_pandas_engine

    # Determinar qué método de descripción usar
    if use_llm_desc is None:
        use_llm_desc = USE_LLM_DESCRIPTIONS

    # Cargar PandasQueryEngine para el dataset
    pandas_engine = get_pandas_engine(codigo, verbose=verbose)

    # GENERAR TEXTO DE BÚSQUEDA
    if use_llm_desc:
        # MÉTODO LLM: Cargar descripción generada
        from src.tools.llm_description_generator import cargar_descripcion_llm

        texto_busqueda = cargar_descripcion_llm(codigo)

        if texto_busqueda is None:
            # Fallback al método original si no existe descripción LLM
            if verbose:
                print(f"⚠️  No se encontró descripción LLM para {codigo}, usando método original")
            texto_busqueda = _generar_descripcion_original(codigo, metadata, verbose)
            metodo_usado = "original (fallback)"
        else:
            metodo_usado = "LLM"
            if verbose:
                print(f"✓ Usando descripción LLM para {codigo}")
    else:
        # MÉTODO ORIGINAL: Concatenación estructurada
        texto_busqueda = _generar_descripcion_original(codigo, metadata, verbose)
        metodo_usado = "original"

    if verbose:
        print(f"  [{codigo}] Método: {metodo_usado} | Longitud: {len(texto_busqueda)} chars")

    # Crear nombre descriptivo de la herramienta usando el título del dataset
    titulo = metadata.get('titulo', 'Sin título')
    # Normalizar título: remover tildes, espacios -> guiones bajos, minúsculas
    import unicodedata
    titulo_normalizado = unicodedata.normalize('NFD', titulo)
    titulo_normalizado = ''.join(c for c in titulo_normalizado if unicodedata.category(c) != 'Mn')
    titulo_normalizado = titulo_normalizado.lower().replace(' ', '_').replace('-', '_')
    # Remover caracteres especiales
    titulo_normalizado = ''.join(c for c in titulo_normalizado if c.isalnum() or c == '_')

    # Truncar si excede el límite de OpenAI (64 caracteres total)
    # Prefijo "consultar_" = 11 chars, quedan 53 para el título
    MAX_TITULO_LENGTH = 53
    if len(titulo_normalizado) > MAX_TITULO_LENGTH:
        # Truncar pero mantener palabras completas
        titulo_normalizado = titulo_normalizado[:MAX_TITULO_LENGTH].rsplit('_', 1)[0]

    tool_name = f"consultar_{titulo_normalizado}"

    # Crear herramienta con nombre descriptivo basado en el título
    tool = QueryEngineTool(
        query_engine=pandas_engine,
        metadata=ToolMetadata(
            name=tool_name,
            description=texto_busqueda,
        ),
    )

    # Agregar metadata técnica extendida como atributo personalizado
    # Este atributo NO afecta la búsqueda semántica (que usa solo 'description')
    # pero estará disponible para el workflow BUSQUEDA
    setattr(tool, 'technical_metadata', {
        "codigo": codigo,
        "titulo": metadata.get('titulo', 'Sin título'),
        "categoria": metadata.get('categoria', 'General'),
        "descripcion": metadata.get('descripcion', ''),
        "unidad": metadata.get('unidad', 'N/A'),
        "cobertura_temporal": metadata.get('cobertura_temporal', 'N/A'),
        "palabras_claves": metadata.get('palabras_claves', ''),
        "columnas": metadata.get('ol_name', 'N/A'),
        "descripcion_columnas": metadata.get('ol_descr', 'N/A'),
        "fuente": metadata.get('creador', 'N/A'),
        "enlace_fuente": metadata.get('enlace_fuente', 'N/A'),
        "frecuencia_actualizacion": metadata.get('frecuencia_actualizacion', 'N/A'),
        "desagregacion_espacial": metadata.get('desagregacion_espacial', 'N/A'),
        "formato_original": metadata.get('formato_original', 'N/A'),
        "cobertura_espacial": metadata.get('cobertura_espacial', 'N/A'),
        "nota": metadata.get('nota', ''),
        "metodo_descripcion": metodo_usado  # Para tracking de A/B testing
    })

    return tool


def _generar_descripcion_original(codigo: str, metadata: dict, verbose: bool = False) -> str:
    """
    Genera descripción usando el método original de concatenación.

    Args:
        codigo: Código del dataset
        metadata: Diccionario con metadata
        verbose: Si True, muestra debug info

    Returns:
        String con descripción concatenada
    """
    from src.tools.metadata_extractor import obtener_muestras_representativas
    import pandas as pd

    contexto_extra = ""
    try:
        # Intentar cargar datos para extraer valores representativos
        codigo_lower = codigo.lower()
        pattern = os.path.join(str(DATA_DIR), f"{codigo_lower}_*.json")
        archivos_datos = glob.glob(pattern)

        if archivos_datos:
            with open(archivos_datos[0], 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Crear DataFrame
            if isinstance(data, list):
                df_datos = pd.DataFrame(data)
            elif isinstance(data, dict) and "data" in data:
                df_datos = pd.DataFrame(data['data'])
            else:
                df_datos = pd.DataFrame()

            if not df_datos.empty:
                contexto_extra = obtener_muestras_representativas(df_datos, limite=15)
    except Exception as e:
        if verbose:
            print(f"⚠️  No se pudo extraer contexto extra para {codigo}: {str(e)}")

    texto_busqueda = (
        f"Titulo: {metadata.get('titulo', 'Sin título')}. "
        f"Descripcion: {metadata.get('descripcion', '')} "
        f"Categoria: {metadata.get('categoria', 'General')}. "
        f"Nombre de las columnas: {metadata.get('ol_name', '')}. "
        f"Valores representativos: {contexto_extra}. "
        f"Palabras claves: {metadata.get('palabras_claves', '')}. "
    )

    return texto_busqueda


def crear_todas_las_tools(verbose: bool = False, use_llm_desc: Optional[bool] = None) -> List[QueryEngineTool]:
    """
    Crea QueryEngineTools para todos los datasets disponibles.

    Args:
        verbose: Si True, muestra información de debug
        use_llm_desc: Si True, usa descripciones LLM. Si None, usa config global.

    Returns:
        Lista de QueryEngineTools (una por dataset)
    """
    # Determinar método
    if use_llm_desc is None:
        use_llm_desc = USE_LLM_DESCRIPTIONS

    tools = []
    metadata_files = glob.glob(str(METADATA_DIR / "*_metadata.json"))

    if verbose:
        metodo = "LLM" if use_llm_desc else "Original"
        print(f"📦 Creando herramientas para {len(metadata_files)} datasets...")
        print(f"🔬 Método de descripción: {metodo}")

    for metadata_file in metadata_files:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            codigo = metadata.get('codigo', '')
            if codigo:
                tool = crear_dataset_tool(codigo, metadata, verbose=verbose, use_llm_desc=use_llm_desc)
                tools.append(tool)
                if verbose:
                    titulo = metadata.get('titulo', 'Sin título')
                    print(f"  ✓ Tool creada: {tool.metadata.name}")
        except Exception as e:
            if verbose:
                print(f"  ✗ Error creando tool para {metadata_file}: {str(e)}")

    if verbose:
        print(f"\n✅ Total de herramientas creadas: {len(tools)}")
    return tools
