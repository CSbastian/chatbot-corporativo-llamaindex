from email.headerregistry import UniqueAddressHeader
import json
import os
import pandas as pd
from pathlib import Path

from llama_index.core import Document
from src.core.config import RAW_METADATA_DIR, METADATA_DIR, DATA_DIR, METADATA_SAMPLE_LIMIT

def _extraer_metadata_de_lista(data_list, nombre_archivo):
    """
    Convierte la lista de atributos en un diccionario plano.
    Extrae todos los parámetros desde titulo hasta ol_descr.

    Args:
        data_list (list): Lista de diccionarios con metadata raw
        nombre_archivo (str): Nombre del archivo original

    Returns:
        dict: Metadata limpia
    """
    # 1. Diccionario base obligatorio
    meta_limpia = {
        "filename": nombre_archivo,
    }

    # 2. Iteramos sobre la lista para cazar los valores
    for item in data_list:
        tipo_variable = item.get("variable", "")
        codigo_key = next((k for k in item.keys() if k not in ["Descripcion", "variable"]), None)
        valor = item.get(codigo_key, "") if codigo_key else ""

        # Si es la fila header, extraer el código antes de saltar
        if tipo_variable == "variable" and codigo_key:
            meta_limpia["codigo"] = codigo_key  # ← El código está en la clave, no en el valor
            continue

        # Si no hay variable definida, saltamos
        if not tipo_variable:
            continue

        # Mapeamos todas las variables de la metadata
        if tipo_variable == "titulo":
            meta_limpia["titulo"] = valor
        elif tipo_variable == "categoria":
            meta_limpia["categoria"] = valor
        elif tipo_variable == "tipo_elemento":
            meta_limpia["tipo_elemento"] = valor
        elif tipo_variable == "palabras_claves":
            meta_limpia["palabras_claves"] = valor
        elif tipo_variable == "descripcion":
            meta_limpia["descripcion"] = valor
        elif tipo_variable == "unidad":
            meta_limpia["unidad"] = valor
        elif tipo_variable == "escala_numerica":
            meta_limpia["escala_numerica"] = valor
        elif tipo_variable == "creador":
            meta_limpia["creador"] = valor
        elif tipo_variable == "obtencion":
            meta_limpia["obtencion"] = valor
        elif tipo_variable == "formato_original":
            meta_limpia["formato_original"] = valor
        elif tipo_variable == "enlace_fuente":
            meta_limpia["enlace_fuente"] = valor
        elif tipo_variable == "frecuencia_actualizacion_fuente":
            meta_limpia["frecuencia_actualizacion_fuente"] = valor
        elif tipo_variable == "idioma":
            meta_limpia["idioma"] = valor
        elif tipo_variable == "responsable_interno":
            meta_limpia["responsable_interno"] = valor
        elif tipo_variable == "fecha_incorporacion":
            meta_limpia["fecha_incorporacion"] = valor
        elif tipo_variable == "frecuencia_actualizacion":
            meta_limpia["frecuencia_actualizacion"] = valor
        elif tipo_variable == "fecha_proxima_actualizacion":
            meta_limpia["fecha_proxima_actualizacion"] = valor
        elif tipo_variable == "fecha_ultima_actualizacion":
            meta_limpia["fecha_ultima_actualizacion"] = valor
        elif tipo_variable == "cobertura_espacial":
            if item.get(codigo_key, "")== "País":
                valor="Nacional / Local"
            elif item.get(codigo_key, "")== "Mundial":
                valor= "Mundial / Internacional"
            else:
                valor = ""
            meta_limpia["cobertura_espacial"] = valor
        elif tipo_variable == "desagregacion_espacial":
            meta_limpia["desagregacion_espacial"] = valor
        elif tipo_variable == "cobertura_temporal":
            meta_limpia["cobertura_temporal"] = valor
        elif tipo_variable == "desagregacion_temporal":
            meta_limpia["desagregacion_temporal"] = valor
        elif tipo_variable == "nota":
            meta_limpia["nota"] = valor
        elif tipo_variable == "db_name":
            valor = valor.replace(",",", ")
            meta_limpia["db_name"] = valor
        elif tipo_variable == "ol_name":
            valor = valor.replace(",",", ")
            meta_limpia["ol_name"] = valor
        elif tipo_variable == "ol_descr":
            meta_limpia["ol_descr"] = valor

    return meta_limpia


def extraer_metadata_limpia(input_dir=None, output_dir=None):
    """
    Procesa todos los archivos JSON de metadata raw desde un directorio de entrada
    y guarda los archivos de metadata limpia en el directorio de salida.

    Args:
        input_dir (str): Directorio con los archivos JSON de metadata raw (usa config si es None)
        output_dir (str): Directorio donde se guardarán los archivos de metadata limpia (usa config si es None)

    Returns:
        dict: Diccionario con estadísticas del procesamiento
    """
    # Usar valores de config por defecto
    if input_dir is None:
        input_dir = str(RAW_METADATA_DIR)
    if output_dir is None:
        output_dir = str(METADATA_DIR)

    # Crear directorio de salida si no existe
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"El directorio de entrada no existe: {input_dir}")

    print(f"📂 Procesando metadata raw desde: {input_dir}")
    print(f"💾 Guardando metadata limpia en: {output_dir}\n")

    procesados = 0
    errores = 0
    archivos_generados = []

    # Procesar todos los archivos JSON en el directorio de entrada
    for nombre_archivo in os.listdir(input_dir):
        if not nombre_archivo.endswith(".json"):
            continue

        ruta_entrada = os.path.join(input_dir, nombre_archivo)

        try:
            # Cargar el JSON raw
            with open(ruta_entrada, 'r', encoding='utf-8') as f:
                json_crudo = json.load(f)

            # Extraer la lista de datos
            if isinstance(json_crudo, list):
                data_list = json_crudo
            elif isinstance(json_crudo, dict) and "data" in json_crudo:
                data_list = json_crudo["data"]
            else:
                print(f"⚠️  Formato desconocido en {nombre_archivo}, saltando...")
                errores += 1
                continue

            # Extraer metadata limpia
            meta_limpia = _extraer_metadata_de_lista(data_list, nombre_archivo)

            # Generar nombre del archivo de salida
            codigo = meta_limpia.get("codigo", "UNKNOWN")
            if codigo != "UNKNOWN":
                output_filename = f"{codigo.lower()}_metadata.json"
            else:
                output_filename = nombre_archivo.replace(".json", "_metadata.json")

            output_path = os.path.join(output_dir, output_filename)

            # Guardar metadata limpia
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(meta_limpia, f, ensure_ascii=False, indent=2)

            archivos_generados.append(output_filename)
            procesados += 1
            print(f"✓ {nombre_archivo} → {output_filename}")

        except Exception as e:
            print(f"❌ Error procesando {nombre_archivo}: {str(e)}")
            errores += 1

    # Resumen
    print(f"\n{'='*60}")
    print(f"📊 RESUMEN:")
    print(f"   Archivos procesados: {procesados}")
    print(f"   Errores: {errores}")
    print(f"   Archivos generados en: {output_dir}")
    print(f"{'='*60}\n")

    return {
        "procesados": procesados,
        "errores": errores,
        "archivos_generados": archivos_generados,
        "output_dir": output_dir
    }

def obtener_muestras_representativas(df, limite=None):
    """
    Extrae valores únicos de columnas de texto para dar contexto real al vector.

    Args:
        df: DataFrame con los datos
        limite: Límite de muestras por columna (usa config si es None)
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

def crear_documento_desde_metadata(ruta_completa, nombre_archivo, data_dir=None):
    """
    Crea un documento LlamaIndex a partir de un archivo JSON de metadata.

    Args:
        ruta_completa (str): Ruta completa al archivo JSON de metadata
        nombre_archivo (str): Nombre del archivo (para logging y metadata)
        data_dir (str): Directorio donde están los archivos de datos (usa config si es None)

    Returns:
        Document: Objeto Document de LlamaIndex, o None si hay error
    """
    # Usar valor de config por defecto
    if data_dir is None:
        data_dir = str(DATA_DIR)

    # Cargar el JSON de metadata
    with open(ruta_completa, "r", encoding="utf-8") as f:
        json_crudo = json.load(f)
    metadata = json_crudo

    # Extraer valores únicos del archivo de datos correspondiente
    contexto_extra = ""
    codigo = metadata.get('codigo', '').lower()

    if codigo:
        # Buscar el archivo de datos correspondiente
        import glob
        pattern = os.path.join(data_dir, f"{codigo}_*.json")
        archivos_datos = glob.glob(pattern)

        if archivos_datos:
            try:
                with open(archivos_datos[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Crear DataFrame desde el archivo de datos
                if isinstance(data, list):
                    df_datos = pd.DataFrame(data)
                elif isinstance(data, dict) and "data" in data:
                    df_datos = pd.DataFrame(data['data'])
                else:
                    df_datos = pd.DataFrame()

                # Extraer muestras representativas de valores únicos
                if not df_datos.empty:
                    contexto_extra = obtener_muestras_representativas(df_datos)
            except Exception as e:
                print(f"⚠️  No se pudieron extraer valores únicos de {archivos_datos[0]}: {str(e)}")

    # Crear el texto descriptivo para el vector
    texto_vector = (
        f"Titulo: {metadata.get('titulo', 'Sin título')}. "
        f"Descripcion: {metadata.get('descripcion', '')}. "
        f"Categoria: {metadata.get('categoria', 'General')}. "
        f"Palabras claves: {metadata.get('palabras_claves', '')}. "
        f"Cobertura temporal: {metadata.get('cobertura_temporal', '')}. "
        f"Cobertura espacial: {metadata.get('cobertura_espacial', '')}. "
        f"Nombre de las columnas: {metadata.get('ol_name', '')}. "
        f"Valores representativos: {contexto_extra}. "
    )
    metadata_doc = {
            'codigo': metadata.get('codigo', ''),
            'titulo': metadata.get('titulo', ''),
            'descripcion': metadata.get('descripcion', ''),
            'categoria': metadata.get('categoria', ''),
            'unidad': metadata.get('unidad', ''),
            'cobertura_temporal': metadata.get('cobertura_temporal', ''),
            'cobertura_espacial': metadata.get('cobertura_espacial', ''),
            'db_name': metadata.get('db_name', ''),
            'ol_name': metadata.get('ol_name', ''),
            'ol_descr': metadata.get('ol_descr', ''),
            }

    # Crear el documento con metadata como diccionario
    doc = Document(
        text=texto_vector,
        metadata=metadata_doc
    )

    return doc


def procesar_directorio_metadata(directorio=None, data_dir=None):
    """
    Transforma todos los archivos JSON de metadata de un directorio
    en documentos de LlamaIndex para indexación vectorial.

    Args:
        directorio (str): Ruta al directorio con los archivos JSON de metadata (usa config si es None)
        data_dir (str): Directorio donde están los archivos de datos (usa config si es None)

    Returns:
        list: Lista de objetos Document de LlamaIndex
    """
    # Usar valores de config por defecto
    if directorio is None:
        directorio = str(RAW_METADATA_DIR)
    if data_dir is None:
        data_dir = str(DATA_DIR)

    documentos = []

    if not os.path.exists(directorio):
        raise FileNotFoundError(f"El directorio no existe: {directorio}")

    print(f"📂 Transformando metadata a documentos LlamaIndex desde: {directorio}\n")

    # Listar todos los archivos JSON en el directorio
    for nombre_archivo in os.listdir(directorio):
        if not nombre_archivo.endswith(".json"):
            continue

        ruta_completa = os.path.join(directorio, nombre_archivo)

        try:
            # Crear documento LlamaIndex usando la función auxiliar
            doc = crear_documento_desde_metadata(ruta_completa, nombre_archivo, data_dir)

            if doc is not None:
                documentos.append(doc)
                print(f"✓ {nombre_archivo} → Document(id={doc.doc_id[:8]}...)")

        except Exception as e:
            print(f"❌ Error procesando {nombre_archivo}: {str(e)}")

    print(f"\n📊 Total de documentos LlamaIndex generados: {len(documentos)}")
    return documentos


