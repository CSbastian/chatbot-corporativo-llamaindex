"""
Test del chatbot usando un Golden Dataset.

Este módulo evalúa las respuestas del chatbot contra un conjunto de preguntas
con respuestas esperadas, usando un LLM como evaluador para determinar la
similitud semántica dado que las respuestas no son deterministas.

Uso:
    python -m tests.test_poolDS --dataset tests/test_consultas.json
    python -m tests.test_poolDS --dataset tests/test_consultas.json --name mi_test
"""

import os
import sys
import json
import csv
import time
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Agregar el directorio raíz del proyecto al path para poder importar src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import glob
from dotenv import load_dotenv

# Importar LlamaIndex para el workflow y evaluador
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage

# Importar el nuevo workflow de LlamaIndex
from src.core.index_manager import get_tools_object_index
from src.workflow.workflow import CorporateReActWorkflow
from src.core.config import (
    TELEMETRY_ENDPOINT,
    TELEMETRY_UI_URL,
    WORKFLOW_TIMEOUT,
    get_llm_evaluador,
    LOGS_DIR as CONFIG_LOGS_DIR,
    METADATA_DIR,
    # Importar configuraciones para el reporte
    LLM_INTENT_MODEL,
    LLM_SPLITTING_MODEL,
    LLM_AGENT_MODEL,
    LLM_ANSWER_MODEL,
    EMBEDDING_MODEL,
    METADATA_SAMPLE_LIMIT,
    QUERY_SPLITTING_TOP_K,
    MAX_SUBQUERIES,
    MAX_REASONING_ITERATIONS

)

from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc
from src.core.database import ChatLog, get_engine

# Telemetría con Arize Phoenix
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Cargar variables de entorno
load_dotenv()

# Directorio para logs (desde config)
LOGS_DIR = CONFIG_LOGS_DIR
LOGS_DIR.mkdir(exist_ok=True)


# Sesión de base de datos reutilizable para consultar métricas
ENGINE = get_engine()
SessionLocal = sessionmaker(bind=ENGINE)


def cargar_mapeo_titulo_codigo() -> Dict[str, str]:
    """
    Carga todos los metadatos y crea un mapeo de título normalizado → código de dataset.

    Returns:
        Dict[str, str]: Mapeo {titulo_normalizado: codigo}
    """
    mapeo = {}

    # Buscar todos los archivos de metadata
    pattern = os.path.join(str(METADATA_DIR), "*_metadata.json")
    archivos_metadata = glob.glob(pattern)

    for filepath in archivos_metadata:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            codigo = metadata.get('codigo', '')
            titulo = metadata.get('titulo', '')

            if codigo and titulo:
                # Normalizar título (lowercase, eliminar espacios extra)
                titulo_normalizado = titulo.lower().strip()
                mapeo[titulo_normalizado] = codigo.upper()
        except Exception as e:
            print(f"⚠️  Error al cargar {filepath}: {str(e)}")

    return mapeo


def obtener_configuraciones_sistema() -> Dict:
    """
    Recopila las configuraciones del sistema para incluirlas en el reporte.

    Returns:
        Dict: Diccionario con todas las configuraciones relevantes del sistema
    """
    return {
        "llm_intent_model": LLM_INTENT_MODEL,
        "llm_splitting_model": LLM_SPLITTING_MODEL,
        "llm_agent_model": LLM_AGENT_MODEL,
        "llm_answer_model": LLM_ANSWER_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "metadata_sample_limit": METADATA_SAMPLE_LIMIT,
        "query_splitting_top_k": QUERY_SPLITTING_TOP_K,
        "max_subqueries": MAX_SUBQUERIES,
        "max_reasoning_iterations": MAX_REASONING_ITERATIONS
    }


def configurar_telemetria():
    """Configura OpenTelemetry + Arize Phoenix para trackear el test."""
    print("🔭 Configurando telemetría Arize Phoenix...")

    tracer_provider = TracerProvider()
    span_processor = SimpleSpanProcessor(OTLPSpanExporter(endpoint=TELEMETRY_ENDPOINT))
    tracer_provider.add_span_processor(span_processor)

    # Instrumentar LlamaIndex
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    print(f"✅ Telemetría configurada: {TELEMETRY_ENDPOINT}")
    print(f"📊 Accede a Phoenix UI en: {TELEMETRY_UI_URL}\n")


def inicializar_sistema():
    """
    Inicializa el workflow de LlamaIndex y el LLM evaluador.

    Returns:
        Tuple[CorporateReActWorkflow, OpenAI]: Workflow y LLM evaluador
    """
    print("🚀 Inicializando sistema...")

    # Cargar ObjectIndex
    print("  📦 Cargando ObjectIndex...")
    object_index = get_tools_object_index()

    # Crear workflow
    print(f"  ⚙️  Creando workflow ReAct (timeout={WORKFLOW_TIMEOUT}s)...")
    workflow = CorporateReActWorkflow(object_index=object_index, timeout=WORKFLOW_TIMEOUT)

    # LLM evaluador desde config
    print("  🤖 Inicializando LLM evaluador desde config...")
    llm_evaluador = get_llm_evaluador()

    print("✅ Sistema inicializado correctamente\n")
    return workflow, llm_evaluador


def guardar_resumen_tests(
    resultados: List[Dict],
    estadisticas: Dict,
    session_timestamp: str,
    nombre_personalizado: Optional[str] = None
) -> Path:
    """
    Guarda un resumen de todos los tests ejecutados en formato CSV.

    Args:
        resultados: Lista de resultados de tests
        estadisticas: Diccionario con estadísticas generales
        session_timestamp: Timestamp de la sesión
        nombre_personalizado: Nombre personalizado para el archivo (opcional)

    Returns:
        Path: Ruta del archivo de resumen
    """
    # Usar nombre personalizado si se proporciona, sino usar timestamp
    if nombre_personalizado:
        resumen_file = LOGS_DIR / f"{nombre_personalizado}.csv"
    else:
        resumen_file = LOGS_DIR / f"test_report_{session_timestamp}.csv"

    # Obtener configuraciones del sistema
    configuraciones = obtener_configuraciones_sistema()

    with open(resumen_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Sección de metadatos
        writer.writerow(["# METADATA"])
        writer.writerow(["timestamp", datetime.now().isoformat()])
        writer.writerow(["session", session_timestamp])
        writer.writerow([])

        # Sección de configuraciones
        writer.writerow(["# CONFIGURACIONES"])
        for key, value in configuraciones.items():
            writer.writerow([key, value])
        writer.writerow([])

        # Sección de estadísticas
        writer.writerow(["# ESTADISTICAS"])
        for key, value in estadisticas.items():
            writer.writerow([key, value])
        writer.writerow([])

        # Sección de resultados detallados
        writer.writerow(["# RESULTADOS DETALLADOS"])

        # Definir columnas para los resultados
        columnas = [
            "test_id",
            "tipo",
            "pregunta",
            "codigo_esperado",
            "codigo_dataset_obtenido",
            "dataset_correcto",
            "respuesta_esperada",
            "respuesta_obtenida",
            "puntuacion",
            "justificacion",
            "aprobado",
            "tiempo_ejecucion",
            "latency_ms_db",
            "tokens_input",
            "tokens_output",
            "tokens_total",
            "intent_type_db"
        ]

        # Escribir encabezados
        writer.writerow(columnas)

        # Escribir cada resultado
        for resultado in resultados:
            fila = []
            for col in columnas:
                valor = resultado.get(col, "")
                # Convertir listas a string separado por punto y coma
                if isinstance(valor, list):
                    valor = "; ".join(str(v) for v in valor)
                fila.append(valor)
            writer.writerow(fila)

    return resumen_file


async def evaluar_respuesta_con_llm(
    llm: OpenAI,
    pregunta: str,
    respuesta_esperada: str,
    respuesta_obtenida: str,
    tipo_caso: str = "MONO",
    datasets_esperados: List[str] = None
) -> Tuple[float, str]:
    """
    Usa un LLM para evaluar la similitud entre la respuesta esperada y obtenida.

    Args:
        llm: El modelo de lenguaje evaluador (LlamaIndex OpenAI)
        pregunta: La pregunta original
        respuesta_esperada: La respuesta correcta del golden dataset
        respuesta_obtenida: La respuesta dada por el chatbot
        tipo_caso: Tipo de caso (MONO, MULTI, BUSQUEDA, FUERA_TOPICO, etc.)
        datasets_esperados: Lista de códigos de datasets esperados (para BUSQUEDA)

    Returns:
        Tuple[float, str]: (puntuación de 0-10, justificación)
    """
    # Construir prompt según el tipo de caso
    if tipo_caso == "BUSQUEDA":
        # Para búsquedas, verificar que se mencionen los datasets correctos
        datasets_str = ", ".join(datasets_esperados) if datasets_esperados else "N/A"
        prompt_evaluacion = f"""Eres un evaluador experto de respuestas de chatbots de búsqueda de datasets.

Pregunta: {pregunta}

Datasets Esperados: {datasets_str}

Respuesta Obtenida (Chatbot): {respuesta_obtenida}

CRITERIOS DE EVALUACIÓN PARA BÚSQUEDA:
La respuesta debe mencionar claramente los datasets relevantes que el usuario está buscando.

- 10: Menciona todos los datasets esperados con descripciones claras y útiles
- 8-9: Menciona los datasets correctos con buena descripción, pero puede faltar algún detalle menor
- 6-7: Menciona los datasets pero con descripción poco clara o incompleta
- 4-5: Menciona algunos datasets pero no todos, o descripciones confusas
- 2-3: Menciona datasets incorrectos o respuesta muy vaga
- 0-1: No menciona los datasets esperados o respuesta completamente incorrecta

IMPORTANTE: La respuesta debe incluir referencias a los códigos o nombres de los datasets (ej: C069, P051, etc.)

Responde ÚNICAMENTE en el siguiente formato JSON (sin markdown):
{{"puntuacion": <número del 0 al 10>, "justificacion": "<explicación breve>"}}"""

    elif tipo_caso == "FUERA_TOPICO":
        # Para casos fuera de tópico, verificar que se rechace correctamente
        mensaje_predefinido_esperado = "Chatbot Corporativo"
        prompt_evaluacion = f"""Eres un evaluador experto de respuestas de chatbots especializados.

Pregunta: {pregunta}

Respuesta Esperada: El chatbot debe rechazar cortésmente esta pregunta porque está FUERA DEL ÁMBITO del Chatbot Corporativo (Demo) (transporte, carga, puertos, logística).

Respuesta Obtenida (Chatbot): {respuesta_obtenida}

CRITERIOS DE EVALUACIÓN PARA PREGUNTAS FUERA DE TÓPICO:
El chatbot debe:
1. Indicar que está fuera de su ámbito de conocimiento logístico
2. Mencionar que es el asistente del Chatbot Corporativo
3. No intentar responder la pregunta con su conocimiento general

- 10: Rechaza cortésmente, menciona que es del Chatbot Corporativo, explica su ámbito
- 8-9: Rechaza adecuadamente con mensaje claro
- 6-7: Rechaza pero con mensaje poco claro o incompleto
- 4-5: Intenta responder parcialmente o mensaje confuso
- 2-3: Intenta responder la pregunta fuera de tópico
- 0-1: Responde completamente la pregunta fuera de tópico (ERROR CRÍTICO)

Responde ÚNICAMENTE en el siguiente formato JSON (sin markdown):
{{"puntuacion": <número del 0 al 10>, "justificacion": "<explicación breve>"}}"""

    else:
        # Para casos de análisis de datos (MONO, MULTI, etc.)
        prompt_evaluacion = f"""Eres un evaluador experto de respuestas de chatbots de análisis de datos. Tu tarea es comparar dos respuestas a una pregunta y asignar una puntuación de 0 a 10.

Pregunta: {pregunta}

Respuesta Esperada (Golden): {respuesta_esperada}

Respuesta Obtenida (Chatbot): {respuesta_obtenida}

CRITERIOS DE EVALUACIÓN PARA ANÁLISIS DE DATOS:
Enfócate en la precisión de los datos numéricos, métricas y conclusiones.

- 10: Respuesta perfecta, datos numéricos exactos y conclusiones correctas
- 8-9: Datos correctos con diferencias menores de formato o redacción
- 6-7: Datos aproximadamente correctos, conclusión general válida
- 4-5: Datos parcialmente correctos pero incompletos
- 2-3: Datos incorrectos o muy incompletos
- 0-1: Respuesta totalmente incorrecta o error

IMPORTANTE: Las diferencias en formato de números (1.234.567 vs 1234567) no afectan la puntuación si el valor es correcto.

Responde ÚNICAMENTE en el siguiente formato JSON (sin markdown):
{{"puntuacion": <número del 0 al 10>, "justificacion": "<explicación breve>"}}"""

    try:
        messages = [ChatMessage(role="user", content=prompt_evaluacion)]
        respuesta_llm = await llm.achat(messages)
        contenido = respuesta_llm.message.content

        # Verificar que el contenido no sea None
        if contenido is None:
            return 0.0, "Error: El LLM retornó un contenido vacío"

        contenido = contenido.strip()

        # Limpiar markdown si existe
        if contenido.startswith("```"):
            contenido = contenido.split("```")[1]
            if contenido.startswith("json"):
                contenido = contenido[4:]
            contenido = contenido.strip()

        evaluacion = json.loads(contenido)
        puntuacion = float(evaluacion.get("puntuacion", 0))
        justificacion = evaluacion.get("justificacion", "Sin justificación")

        return puntuacion, justificacion
    except Exception as e:
        print(f"⚠️  Error al evaluar con LLM: {e}")
        return 0.0, f"Error en evaluación: {str(e)}"


async def obtener_respuesta_chatbot(
    workflow: CorporateReActWorkflow,
    pregunta: str,
    mapeo_titulo_codigo: Dict[str, str]
) -> Tuple[str, List[str]]:
    """
    Obtiene la respuesta del chatbot usando el workflow de LlamaIndex.

    Args:
        workflow: Instancia del CorporateReActWorkflow
        pregunta: La pregunta a hacer
        mapeo_titulo_codigo: Mapeo de títulos normalizados a códigos de dataset

    Returns:
        Tuple[str, List[str]]: (respuesta del chatbot, lista de códigos/datasets usados)
    """
    try:
        # Ejecutar workflow (async)
        result = await workflow.run(user_question=pregunta)

        # Extraer datos del resultado
        respuesta = result.get("answer", "Sin respuesta")
        sources = result.get("sources", []) or []

        return respuesta, sources
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error al obtener respuesta: {str(e)}", []


def normalizar_codigos(caso: Dict) -> List[str]:
    """Normaliza los códigos de datasets esperados a una lista de strings."""
    codigos: List[str] = []

    if "código" in caso:
        raw = caso["código"]
    elif "codigo" in caso:
        raw = caso["codigo"]
    elif "archivo_origen" in caso:
        raw = caso["archivo_origen"]
    else:
        return []

    # Puede ser string, lista de strings o lista con strings tipo "C001, P012"
    if isinstance(raw, str):
        partes = [raw]
    else:
        partes = raw

    for p in partes:
        if not isinstance(p, str):
            continue
        texto = p.strip()
        # remover corchetes si vienen tipo "[C001, P039]"
        if texto.startswith("[") and texto.endswith("]"):
            texto = texto[1:-1]
        for token in texto.split(","):
            t = token.strip().upper()
            if t and t not in ("GENERAL", "N/A"):
                codigos.append(t)

    return codigos


def normalizar_tipo(caso: Dict) -> str:
    """Normaliza el campo tipo del caso de prueba."""
    t = (caso.get("tipo") or "").lower().strip()
    if "monodataset" in t:
        return "MONO"
    if "multidataset" in t:
        return "MULTI"
    if "busqueda" in t:
        return "BUSQUEDA"
    if "fuera de topico" in t:
        return "FUERA_TOPICO"
    if "fuera de rango" in t:
        return "FUERA_RANGO"
    return "OTRO"


def obtener_metricas_tokens_desde_db(pregunta: str) -> Dict:
    """Busca en la base de datos el último log asociado a la pregunta.

    Retorna un diccionario con:
        - latency_ms_db
        - tokens_input
        - tokens_output
        - tokens_total
        - intent_type_db
    """
    session = SessionLocal()
    try:
        log = (
            session.query(ChatLog)
            .filter(ChatLog.user_input == pregunta)
            .order_by(desc(ChatLog.timestamp))
            .first()
        )

        if not log or not log.agent_stats:
            return {
                "latency_ms_db": log.latency_ms if log else None,
                "tokens_input": None,
                "tokens_output": None,
                "tokens_total": None,
                "intent_type_db": log.intent_type if log else None,
            }

        try:
            stats = json.loads(log.agent_stats)
        except Exception:
            stats = {}

        return {
            "latency_ms_db": log.latency_ms,
            "tokens_input": stats.get("tokens_input"),
            "tokens_output": stats.get("tokens_output"),
            "tokens_total": stats.get("tokens_total"),
            "intent_type_db": log.intent_type,
        }
    finally:
        session.close()


async def ejecutar_test_golden_dataset(
    dataset: List[Dict],
    nombre_reporte: Optional[str] = None
) -> Dict:
    """
    Ejecuta el test completo del golden dataset y genera reportes en logs/.

    Args:
        dataset: Lista de diccionarios con 'código', 'pregunta', 'respuesta', 'consulta'.
        nombre_reporte: Nombre personalizado para el reporte de salida (opcional)

    Returns:
        Dict: Resultados del test con estadísticas completas
    """
    if not dataset:
        raise ValueError("El dataset no puede estar vacío. Debe proporcionar un archivo JSON con las preguntas.")

    # Configurar telemetría
    configurar_telemetria()

    # INICIO: Medir tiempo total de ejecución
    tiempo_inicio_total = time.time()

    # Generar timestamp de sesión
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print("🧪 INICIANDO TEST CON GOLDEN DATASET")
    print("=" * 80)
    print(f"📅 Sesión: {session_timestamp}")
    print(f"📊 Total de casos: {len(dataset)}\n")

    # Cargar mapeo de título → código
    print("📚 Cargando mapeo de títulos a códigos...")
    mapeo_titulo_codigo = cargar_mapeo_titulo_codigo()
    print(f"✅ Mapeo cargado: {len(mapeo_titulo_codigo)} datasets\n")

    # Inicializar sistema (workflow + evaluador)
    workflow, llm_evaluador = inicializar_sistema()

    resultados = []
    puntuaciones = []

    # Procesar cada caso del dataset
    for idx, caso in enumerate(dataset, 1):
        # INICIO: Medir tiempo individual
        tiempo_inicio_test = time.time()

        pregunta = caso["pregunta"]
        respuesta_esperada = caso.get("respuesta", "")
        tipo = normalizar_tipo(caso)
        codigos_esperados = normalizar_codigos(caso)
        caso_id = caso.get("id") or caso.get("código") or caso.get("codigo") or f"Q{idx:03d}"

        codigos_display = ", ".join(codigos_esperados) if codigos_esperados else "N/A"

        print(f"\n{'─' * 80}")
        print(f"📝 Test {idx}/{len(dataset)} - ID: {caso_id} - Código(s): {codigos_display}")
        print(f"{'─' * 80}")
        print(f"❓ Pregunta: {pregunta}")

        # Resetear memoria antes de cada test para garantizar aislamiento
        workflow.reset_memory(verbose=False)

        print(f"\n⏳ Obteniendo respuesta del chatbot usando workflow LlamaIndex...")

        # Obtener respuesta del chatbot usando el workflow
        respuesta_obtenida, datasets_obtenidos = \
            await obtener_respuesta_chatbot(workflow, pregunta, mapeo_titulo_codigo)

        # FIN: Calcular tiempo individual
        tiempo_ejecucion = round(time.time() - tiempo_inicio_test, 2)

        print(f"✅ Respuesta obtenida:\n{respuesta_obtenida}")
        datasets_obtenidos_norm = [str(c).upper() for c in datasets_obtenidos]

        print(f"📋 Datasets usados: {datasets_obtenidos_norm}")
        print(f"📋 Datasets esperados: {codigos_esperados}")
        print(f"⏱️  Tiempo de ejecución: {tiempo_ejecucion}s")

        # Verificar si los datasets seleccionados son correctos (solo para MONO/MULTI)
        dataset_correcto = None
        if tipo in ("MONO", "MULTI") and codigos_esperados:
            if tipo == "MONO":
                dataset_correcto = codigos_esperados[0] in datasets_obtenidos_norm
            else:
                faltantes = [c for c in codigos_esperados if c not in datasets_obtenidos_norm]
                dataset_correcto = len(faltantes) == 0

        if dataset_correcto is True:
            print("✅ Datasets correctos")
        elif dataset_correcto is False:
            print("❌ Datasets incorrectos")
        else:
            print(f"ℹ️  Caso sin evaluación de datasets (tipo: {tipo})")

        # Evaluar con LLM
        print(f"\n🤖 Evaluando respuesta con LLM (tipo: {tipo})...")
        puntuacion, justificacion = await evaluar_respuesta_con_llm(
            llm_evaluador,
            pregunta,
            respuesta_esperada,
            respuesta_obtenida,
            tipo_caso=tipo,
            datasets_esperados=codigos_esperados
        )

        print(f"📊 Puntuación: {puntuacion}/10")
        print(f"💬 Justificación: {justificacion}")

        # Obtener métricas de tokens y latencia desde la base de datos
        metricas_db = obtener_metricas_tokens_desde_db(pregunta)
        latency_ms_db = metricas_db.get("latency_ms_db")
        tokens_input = metricas_db.get("tokens_input")
        tokens_output = metricas_db.get("tokens_output")
        tokens_total = metricas_db.get("tokens_total")
        intent_type_db = metricas_db.get("intent_type_db")

        # Guardar resultados
        resultado = {
            "test_id": caso_id,
            "tipo": tipo,
            "pregunta": pregunta,
            "codigo_esperado": codigos_esperados,
            "codigo_dataset_obtenido": datasets_obtenidos_norm,
            "dataset_correcto": dataset_correcto,
            "respuesta_esperada": respuesta_esperada,
            "respuesta_obtenida": respuesta_obtenida,
            "puntuacion": puntuacion,
            "justificacion": justificacion,
            "aprobado": puntuacion >= 6.0,
            "tiempo_ejecucion": tiempo_ejecucion,
            "latency_ms_db": latency_ms_db,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens_total": tokens_total,
            "intent_type_db": intent_type_db,
        }
        resultados.append(resultado)
        puntuaciones.append(puntuacion)

    # FIN: Calcular tiempo total de ejecución
    tiempo_total_ejecucion = round(time.time() - tiempo_inicio_total, 2)

    # Calcular estadísticas
    promedio = sum(puntuaciones) / len(puntuaciones) if puntuaciones else 0
    aprobados = sum(1 for r in resultados if r["aprobado"])
    tasa_aprobacion = (aprobados / len(resultados)) * 100 if resultados else 0
    # Accuracy de selección de datasets (solo casos donde se evalúa dataset_correcto)
    casos_con_dataset = [r for r in resultados if r["dataset_correcto"] is not None]
    datasets_correctos = sum(1 for r in casos_con_dataset if r["dataset_correcto"] is True)
    accuracy_dataset = (datasets_correctos / len(casos_con_dataset)) * 100 if casos_con_dataset else 0

    # Métricas de tokens y latencia desde la base de datos (si están disponibles)
    tokens_totales = [r["tokens_total"] for r in resultados if r.get("tokens_total") is not None]
    latencias_db = [r["latency_ms_db"] for r in resultados if r.get("latency_ms_db") is not None]

    estadisticas = {
        "total_tests": len(resultados),
        "puntuacion_promedio": round(promedio, 2),
        "puntuacion_maxima": max(puntuaciones) if puntuaciones else 0,
        "puntuacion_minima": min(puntuaciones) if puntuaciones else 0,
        "tests_aprobados": aprobados,
        "tests_fallidos": len(resultados) - aprobados,
        "tasa_aprobacion": round(tasa_aprobacion, 2),
        "datasets_correctos": datasets_correctos,
        "datasets_incorrectos": len(casos_con_dataset) - datasets_correctos,
        "accuracy_dataset": round(accuracy_dataset, 2),
        "tiempo_total_ejecucion": tiempo_total_ejecucion,
        "tokens_promedio_total": round(sum(tokens_totales) / len(tokens_totales), 2) if tokens_totales else None,
        "latencia_promedio_db_ms": round(sum(latencias_db) / len(latencias_db), 2) if latencias_db else None,
    }

    # Guardar resumen en logs/
    resumen_file = guardar_resumen_tests(resultados, estadisticas, session_timestamp, nombre_reporte)

    # Mostrar resumen
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN DE LA EVALUACIÓN")
    print(f"{'='*80}")
    print(f"\n🎯 CALIDAD DE RESPUESTAS:")
    print(f"  Puntuación promedio: {promedio:.2f}/10")
    print(f"  Puntuación máxima: {max(puntuaciones):.2f}/10" if puntuaciones else "N/A")
    print(f"  Puntuación mínima: {min(puntuaciones):.2f}/10" if puntuaciones else "N/A")
    print(f"  Tests aprobados: {aprobados}/{len(resultados)}")
    print(f"  Tests fallidos: {len(resultados) - aprobados}/{len(resultados)}")
    print(f"  Tasa de aprobación: {tasa_aprobacion:.2f}%")
    print(f"\n📋 SELECCIÓN DE DATASETS:")
    print(f"  Datasets correctos: {datasets_correctos}/{len(resultados)}")
    print(f"  Datasets incorrectos: {len(casos_con_dataset) - datasets_correctos}/{len(casos_con_dataset)}")
    print(f"  Accuracy de dataset: {accuracy_dataset:.2f}%")
    print(f"\n⏱️  RENDIMIENTO:")
    print(f"  Tiempo total de ejecución: {tiempo_total_ejecucion:.2f}s")
    print(f"  Tiempo promedio por test: {tiempo_total_ejecucion/len(resultados):.2f}s")
    print(f"\n📈 TOKENS (según DB, si disponibles):")
    print(f"  Tokens promedio totales por consulta: {estadisticas['tokens_promedio_total']}")
    print(f"  Latencia promedio (DB): {estadisticas['latencia_promedio_db_ms']} ms")
    print(f"\n💾 Reporte guardado en: {resumen_file}")
    print(f"🔭 Trazas disponibles en: {TELEMETRY_UI_URL}")
    print(f"{'='*80}\n")

    return {
        "session": session_timestamp,
        "timestamp": datetime.now().isoformat(),
        "estadisticas": estadisticas,
        "resultados_detallados": resultados
    }


def cargar_dataset_desde_archivo(ruta_archivo: str) -> List[Dict]:
    """
    Carga un golden dataset desde un archivo JSON.

    Args:
        ruta_archivo: Ruta al archivo JSON con el dataset

    Returns:
        List[Dict]: Dataset cargado
    """
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluar chatbot con Golden Dataset usando LlamaIndex Workflow"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Ruta al archivo JSON con el dataset (REQUERIDO)"
    )
    parser.add_argument(
        "--name",
        type=str,
        required=False,
        help="Nombre personalizado para el archivo de reporte (opcional, sin extensión .json)"
    )

    args = parser.parse_args()

    # Cargar dataset desde archivo
    print(f"\n📂 Cargando dataset desde: {args.dataset}")
    try:
        dataset_custom = cargar_dataset_desde_archivo(args.dataset)

        # Ejecutar test de forma asíncrona
        asyncio.run(ejecutar_test_golden_dataset(
            dataset=dataset_custom,
            nombre_reporte=args.name
        ))
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo '{args.dataset}'")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
