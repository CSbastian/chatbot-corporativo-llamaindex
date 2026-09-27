"""
Generador de descripciones de datasets usando LLM.

Crea descripciones naturales y optimizadas para búsqueda semántica,
permitiendo comparación A/B con el método de concatenación actual.
"""

import os
import json
import glob
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
from tqdm import tqdm

from llama_index.llms.openai import OpenAI

# Configuración inline para evitar importaciones circulares
BASE_DIR = Path(__file__).parent.parent.parent
METADATA_DIR = BASE_DIR / "json" / "metadata"
DATA_DIR = BASE_DIR / "json" / "data"
LLM_DESCRIPTIONS_FILE = BASE_DIR / "json" / "llm_descriptions.json"
LLM_DESCRIPTION_TARGET_WORDS = 300
LLM_DESCRIPTION_MODEL = "gpt-4o-mini"
LLM_DESCRIPTION_TEMPERATURE = 0.3
METADATA_SAMPLE_LIMIT = 15


def obtener_muestras_representativas(df, limite=None):
    """
    Extrae valores únicos de columnas de texto para dar contexto real al vector.

    Args:
        df: DataFrame con los datos
        limite: Límite de muestras por columna
    """
    if limite is None:
        limite = METADATA_SAMPLE_LIMIT

    contexto_extra = []

    # Identificamos columnas de tipo texto (object)
    cols_texto = df.select_dtypes(include=['object']).columns

    for col in cols_texto:
        # Obtenemos valores únicos, filtramos nulos y tomamos los primeros N
        valores = df[col].dropna().unique().tolist()

        # Si la columna tiene muchos valores (ej. Ciudades), tomamos una muestra
        if valores:
            # Limitar la cantidad de valores únicos
            valores_unicos = valores[:limite]
            muestra = ", ".join(map(str, valores_unicos))
            contexto_extra.append(f"{col}: {muestra}")

    return "; ".join(contexto_extra)


# Prompt para generar descripciones optimizadas
DESCRIPTION_GENERATION_PROMPT = """Eres un experto en logística y datos de transporte del país que trabaja para el Chatbot Corporativo.

Tu tarea es generar una descripción NATURAL y OPTIMIZADA para búsqueda semántica del siguiente dataset.

METADATA DEL DATASET:
- Título: {titulo}
- Categoría: {categoria}
- Descripción técnica: {descripcion}
- Columnas disponibles: {columnas}
- Descripción de columnas: {descripcion_columnas}
- Cobertura temporal: {cobertura_temporal}
- Cobertura espacial: {cobertura_espacial}
- Desagregación espacial: {desagregacion_espacial}
- Desagregación temporal: {desagregacion_temporal}
- Unidad de medida: {unidad}
- Fuente: {fuente}
- Valores representativos: {valores_representativos}
- Notas adicionales: {nota}

INSTRUCCIONES PARA LA DESCRIPCIÓN:

1. **Contenido del Dataset**: Describe QUÉ datos contiene usando lenguaje natural y claro
2. **Casos de Uso**: Menciona 2-3 ejemplos específicos de consultas que este dataset puede responder
   Ejemplo: "Este dataset permite responder preguntas como '¿Cuánta carga se movilizó en el puerto de Valparaíso en 2023?'"
3. **Términos Clave**: Incluye sinónimos y términos relacionados que un usuario podría usar al buscar
   Ejemplo: Si es sobre puertos, menciona: puertos, terminales portuarios, carga marítima, exportaciones, importaciones
4. **Granularidad**: Especifica claramente la desagregación temporal (mensual, anual, etc.) y espacial (regional, por puerto, etc.)
5. **Contexto Local**: Menciona regiones, ciudades, o instituciones específicas cuando sea relevante
6. **Valores Ejemplo**: Integra naturalmente algunos valores representativos para dar contexto

REQUISITOS:
- Longitud objetivo: aproximadamente {target_words} palabras
- Usa lenguaje NATURAL, como si describieras el dataset a un colega
- NO uses formato markdown, bullets, o estructura rígida
- NO repitas información innecesariamente
- Incluye vocabulario técnico Y coloquial para maximizar cobertura de búsqueda
- Escribe en español del país
- incluye valores representativos del dataset para dar contexto real, como "Región Metropolitana, Valparaíso, Asfalto, Contenedores, etc." extrayendolos de la lista de valores representativos.

FORMATO DE SALIDA:
Un único párrafo continuo en texto plano (sin saltos de línea adicionales).

Descripción:"""


def get_llm_for_descriptions() -> OpenAI:
    """
    Retorna instancia del LLM para generar descripciones.
    """
    return OpenAI(
        model=LLM_DESCRIPTION_MODEL,
        temperature=LLM_DESCRIPTION_TEMPERATURE,
        max_tokens=1000
    )


def generar_descripcion_dataset(
    codigo: str,
    metadata: dict,
    df: Optional[pd.DataFrame] = None,
    verbose: bool = False
) -> str:
    """
    Genera una descripción natural de un dataset usando LLM.

    Args:
        codigo: Código del dataset (ej: 'C001')
        metadata: Diccionario con metadata del dataset
        df: DataFrame con datos del dataset (opcional, mejora la descripción)
        verbose: Si True, muestra información de debug

    Returns:
        String con descripción optimizada para búsqueda semántica
    """
    # Extraer valores representativos del DataFrame
    valores_representativos = ""
    if df is not None and not df.empty:
        try:
            valores_representativos = obtener_muestras_representativas(df, limite=10)
        except Exception as e:
            if verbose:
                print(f"⚠️  No se pudieron extraer valores representativos: {str(e)}")
            valores_representativos = "No disponible"
    else:
        valores_representativos = "No disponible"

    # Preparar datos para el prompt
    prompt_data = {
        "titulo": metadata.get('titulo', 'Sin título'),
        "categoria": metadata.get('categoria', 'General'),
        "descripcion": metadata.get('descripcion', 'Sin descripción'),
        "columnas": metadata.get('ol_name', 'No especificadas'),
        "descripcion_columnas": metadata.get('ol_descr', 'No especificada'),
        "cobertura_temporal": metadata.get('cobertura_temporal', 'No especificada'),
        "cobertura_espacial": metadata.get('cobertura_espacial', 'No especificada'),
        "desagregacion_espacial": metadata.get('desagregacion_espacial', 'No especificada'),
        "desagregacion_temporal": metadata.get('desagregacion_temporal', 'No especificada'),
        "unidad": metadata.get('unidad', 'No especificada'),
        "fuente": metadata.get('creador', 'No especificada'),
        "valores_representativos": valores_representativos,
        "nota": metadata.get('nota', 'Ninguna'),
        "target_words": LLM_DESCRIPTION_TARGET_WORDS
    }

    # Construir prompt
    prompt = DESCRIPTION_GENERATION_PROMPT.format(**prompt_data)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Generando descripción para {codigo}: {metadata.get('titulo', '')}")
        print(f"{'='*60}")

    # Llamar al LLM
    llm = get_llm_for_descriptions()

    try:
        response = llm.complete(prompt)
        descripcion = response.text.strip()

        if verbose:
            palabras = len(descripcion.split())
            print(f"✓ Descripción generada ({palabras} palabras)")
            print(f"\nPreview: {descripcion[:200]}...")

        return descripcion

    except Exception as e:
        error_msg = f"Error al generar descripción para {codigo}: {str(e)}"
        if verbose:
            print(f"❌ {error_msg}")
        # Fallback: retornar descripción básica concatenada
        return f"{metadata.get('titulo', '')}. {metadata.get('descripcion', '')}. Categoría: {metadata.get('categoria', '')}."


def cargar_dataset_por_codigo(codigo: str, verbose: bool = False) -> Optional[pd.DataFrame]:
    """
    Carga el DataFrame de un dataset por su código.

    Args:
        codigo: Código del dataset (ej: 'C001')
        verbose: Si True, muestra información de debug

    Returns:
        DataFrame con los datos, o None si no se encuentra
    """
    try:
        codigo_lower = codigo.lower()
        pattern = os.path.join(str(DATA_DIR), f"{codigo_lower}_*.json")
        archivos_datos = glob.glob(pattern)

        if not archivos_datos:
            if verbose:
                print(f"⚠️  No se encontró archivo de datos para {codigo}")
            return None

        with open(archivos_datos[0], 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Crear DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and "data" in data:
            df = pd.DataFrame(data['data'])
        else:
            df = pd.DataFrame()

        return df if not df.empty else None

    except Exception as e:
        if verbose:
            print(f"❌ Error cargando datos de {codigo}: {str(e)}")
        return None


def cargar_descripciones_existentes() -> Tuple[dict, dict]:
    """
    Carga las descripciones LLM existentes desde el archivo JSON.

    Returns:
        Tupla (metadata, descriptions) donde:
        - metadata: dict con info del archivo (generated_at, model, etc.)
        - descriptions: dict {codigo: descripcion}
    """
    if not LLM_DESCRIPTIONS_FILE.exists():
        return {}, {}

    try:
        with open(LLM_DESCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data.get('metadata', {}), data.get('descriptions', {})

    except Exception as e:
        print(f"⚠️  Error cargando descripciones existentes: {str(e)}")
        return {}, {}


def obtener_fecha_modificacion_dataset(codigo: str) -> Optional[str]:
    """
    Obtiene la fecha de última modificación de un dataset.

    Args:
        codigo: Código del dataset

    Returns:
        Fecha en formato ISO (str) o None si no se encuentra
    """
    try:
        # Buscar archivo de datos
        codigo_lower = codigo.lower()
        pattern = os.path.join(str(DATA_DIR), f"{codigo_lower}_*.json")
        archivos_datos = glob.glob(pattern)

        if archivos_datos:
            timestamp = os.path.getmtime(archivos_datos[0])
            return datetime.fromtimestamp(timestamp).isoformat()

        return None

    except Exception:
        return None


def generar_todas_las_descripciones(
    verbose: bool = True,
    regenerar_modificados: bool = True,
    force_all: bool = False
) -> dict:
    """
    Genera descripciones LLM para todos los datasets disponibles.

    Args:
        verbose: Si True, muestra progreso detallado
        regenerar_modificados: Si True, regenera descripciones de datasets modificados
        force_all: Si True, regenera todas las descripciones (ignora cache)

    Returns:
        Diccionario con estadísticas del proceso
    """
    # Cargar descripciones existentes
    existing_metadata, existing_descriptions = cargar_descripciones_existentes()

    # Obtener todos los archivos de metadata
    metadata_files = glob.glob(str(METADATA_DIR / "*_metadata.json"))
    total_datasets = len(metadata_files)

    if verbose:
        print(f"\n{'='*70}")
        print(f"🚀 GENERADOR DE DESCRIPCIONES LLM - CHATBOT CORPORATIVO")
        print(f"{'='*70}")
        print(f"📦 Total de datasets encontrados: {total_datasets}")
        print(f"💾 Descripciones existentes: {len(existing_descriptions)}")
        print(f"🔄 Regenerar modificados: {'Sí' if regenerar_modificados else 'No'}")
        print(f"⚡ Forzar regeneración completa: {'Sí' if force_all else 'No'}")
        print(f"{'='*70}\n")

    # Contadores
    nuevas = 0
    actualizadas = 0
    omitidas = 0
    errores = 0

    descriptions = existing_descriptions.copy() if not force_all else {}

    # Iterar sobre datasets
    iterator = tqdm(metadata_files, desc="Generando descripciones") if verbose else metadata_files

    for metadata_file in iterator:
        try:
            # Cargar metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            codigo = metadata.get('codigo', '')
            if not codigo:
                if verbose:
                    print(f"⚠️  Archivo sin código: {metadata_file}")
                errores += 1
                continue

            # Decidir si procesar este dataset
            debe_generar = False

            if force_all:
                debe_generar = True
            elif codigo not in existing_descriptions:
                debe_generar = True
                nuevas += 1
            elif regenerar_modificados:
                # Verificar si el dataset fue modificado
                fecha_mod = obtener_fecha_modificacion_dataset(codigo)
                fecha_generacion = existing_metadata.get('generated_at', '')

                if fecha_mod and fecha_generacion and fecha_mod > fecha_generacion:
                    debe_generar = True
                    actualizadas += 1
                else:
                    omitidas += 1
            else:
                omitidas += 1

            if not debe_generar:
                continue

            # Cargar datos del dataset
            df = cargar_dataset_por_codigo(codigo, verbose=False)

            # Generar descripción
            descripcion = generar_descripcion_dataset(
                codigo=codigo,
                metadata=metadata,
                df=df,
                verbose=False
            )

            descriptions[codigo] = descripcion

            if verbose and not isinstance(iterator, tqdm):
                print(f"✓ {codigo}: {metadata.get('titulo', '')[:50]}...")

        except Exception as e:
            errores += 1
            if verbose:
                print(f"❌ Error procesando {metadata_file}: {str(e)}")

    # Preparar metadata del archivo
    output_metadata = {
        "generated_at": datetime.now().isoformat(),
        "llm_model": LLM_DESCRIPTION_MODEL,
        "temperature": LLM_DESCRIPTION_TEMPERATURE,
        "target_words": LLM_DESCRIPTION_TARGET_WORDS,
        "total_datasets": len(descriptions),
        "version": "1.0"
    }

    # Guardar resultado
    output_data = {
        "metadata": output_metadata,
        "descriptions": descriptions
    }

    # Crear directorio si no existe
    LLM_DESCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LLM_DESCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # Estadísticas finales
    stats = {
        "total_procesados": len(descriptions),
        "nuevas": nuevas if not force_all else len(descriptions),
        "actualizadas": actualizadas,
        "omitidas": omitidas,
        "errores": errores,
        "archivo_salida": str(LLM_DESCRIPTIONS_FILE)
    }

    if verbose:
        print(f"\n{'='*70}")
        print(f"✅ PROCESO COMPLETADO")
        print(f"{'='*70}")
        print(f"📊 Descripciones totales: {stats['total_procesados']}")
        print(f"🆕 Nuevas: {stats['nuevas']}")
        print(f"🔄 Actualizadas: {stats['actualizadas']}")
        print(f"⏭️  Omitidas: {stats['omitidas']}")
        print(f"❌ Errores: {stats['errores']}")
        print(f"💾 Archivo guardado: {stats['archivo_salida']}")
        print(f"{'='*70}\n")

    return stats


def cargar_descripcion_llm(codigo: str) -> Optional[str]:
    """
    Carga la descripción LLM de un dataset específico.

    Args:
        codigo: Código del dataset (ej: 'C001')

    Returns:
        Descripción LLM o None si no existe
    """
    _, descriptions = cargar_descripciones_existentes()
    return descriptions.get(codigo)
