import os
import json
import pandas as pd
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.experimental.query_engine import PandasQueryEngine
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.objects import ObjectIndex, SimpleToolNodeMapping
from src.tools.pandas_wrapper import TrackedPandasQueryEngine
from src.core.config import (
    PERSIST_DIR_METADATA,
    PERSIST_DIR_TOOLS,
    METADATA_DIR,
    DATA_DIR,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS
)

from dotenv import load_dotenv
load_dotenv()

# Verificación api key
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("¡Error! No se cargó la API Key. Revisa que el archivo .env esté en la carpeta raíz.")

# Configurar embedding model desde config.py
Settings.embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)


def get_pandas_engine(codigo_dataset: str, verbose: bool = False):
    """Carga el JSON y devuelve el motor Pandas con metadata inyectada."""
    # Buscar archivo que empiece con el código (case-insensitive)
    import glob

    codigo_lower = codigo_dataset.lower()
    pattern = os.path.join(str(DATA_DIR), f"{codigo_lower}_*.json")
    archivos = glob.glob(pattern)

    if not archivos:
        raise FileNotFoundError(f"No se encontró ningún archivo con patrón: {pattern}")

    filepath = archivos[0]  # Tomar el primero si hay varios
    print(f"📂 Usando archivo: {os.path.basename(filepath)}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Si el JSON es una lista directa, usarla; si tiene clave "data", extraerla
    if isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, dict) and "data" in data:
        df = pd.DataFrame(data['data'])
    else:
        raise ValueError(f"Formato de JSON no soportado en {filepath}")

    if verbose:
        print(f"📊 DataFrame cargado: {len(df)} filas, {len(df.columns)} columnas")
        print(f"   Columnas: {', '.join(df.columns.tolist()[:5])}...")

    # CARGAR METADATA LIMPIA DEL DATASET
    metadata = {}
    metadata_path = os.path.join(str(METADATA_DIR), f"{codigo_lower}_metadata.json")

    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        if verbose:
            print(f"📋 Metadata cargada: {metadata.get('titulo', 'N/A')}")
    else:
        if verbose:
            print(f"⚠️  No se encontró metadata en {metadata_path}")

    # INYECTAR METADATA EN INSTRUCTION_STR
    instruction_str = f"""Estás trabajando con el DataFrame 'df' que contiene los siguientes datos:

INFORMACIÓN DEL DATASET:
- Título: {metadata.get('titulo', 'Sin título')}
- Categoría: {metadata.get('categoria', 'N/A')}
- Descripción: {metadata.get('descripcion', 'Sin descripción')}
- Unidad de medida: {metadata.get('unidad', 'N/A')}
- Escala numerica: {metadata.get('escala_numerica', 'N/A')}
- Cobertura espacial: {metadata.get('cobertura_espacial', 'N/A')}

ESTRUCTURA DEL DATAFRAME:
- Total de filas: {len(df)}
- Columnas disponibles: {', '.join(df.columns.tolist())}

INSTRUCCIONES:
1. Analiza la pregunta del usuario considerando el contexto del dataset
2. Genera SOLO código Python usando pandas que retorne el resultado
3. NO incluyas explicaciones, markdown, ni texto adicional
4. Usa los nombres EXACTOS de las columnas mostradas arriba
5. Si la pregunta menciona la unidad "{metadata.get('unidad', '')}", asegúrate de usar la columna correcta
6. Retorna SOLO el valor final (número, lista, o tabla)

Ejemplos de código:
- Filtrar: df[df['Columna'] == valor]
- Sumar: df['Columna'].sum()
- Agrupar: df.groupby('Col1')['Col2'].sum()
- Top N: df.nlargest(5, 'Columna')

Genera el código Python ahora:
"""


    return TrackedPandasQueryEngine(
        df=df,
        verbose=verbose,  # Usar verbose configurable
        instruction_str=instruction_str,
        synthesize_response=False
    )



def get_tools_object_index(verbose: bool = False):
    """
    Carga o crea el ObjectIndex con todas las herramientas de datasets.

    Args:
        verbose: Si True, muestra información de debug

    Returns:
        ObjectIndex configurado con 50+ QueryEngineTools
    """
    from src.tools.tools_factory import crear_todas_las_tools

    # Verificar si existe el índice de herramientas
    tools = crear_todas_las_tools(verbose=verbose)
    if not tools:
        raise ValueError("No se pudieron crear herramientas. Verifica los archivos de metadata.")

    tool_mapping = SimpleToolNodeMapping.from_objects(tools)

    try:
        # Cargar ObjectIndex con el índice persistido y el node mapping
        object_index = ObjectIndex.from_persist_dir(
            persist_dir=str(PERSIST_DIR_TOOLS),
            object_node_mapping=tool_mapping
        )

        if verbose:
            print(f"✓ ObjectIndex cargado con {len(tools)} herramientas")

    except Exception as e:
        if verbose:
            print(f"⚠️  Error al cargar ObjectIndex: {e}")
            print("Regenerando índice desde cero...")
            print(f"📦 Creando ObjectIndex con {len(tools)} herramientas...")

        # Crear ObjectIndex con SimpleToolNodeMapping
        object_index = ObjectIndex.from_objects(
            tools,
            index_cls=VectorStoreIndex,
        )
            # Persistir el índice
        if verbose:
            print(f"💾 Persistiendo ObjectIndex en {PERSIST_DIR_TOOLS}...")
        os.makedirs(str(PERSIST_DIR_TOOLS), exist_ok=True)
        object_index.persist(persist_dir=str(PERSIST_DIR_TOOLS))
        if verbose:
            print(f"✓ ObjectIndex guardado exitosamente")
    return object_index