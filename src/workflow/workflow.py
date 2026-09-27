"""
ReAct Workflow para el Chatbot Corporativo usando 100% LlamaIndex.
Reemplaza la arquitectura anterior de LangGraph + LangChain.
"""

import json
import asyncio
import uuid
import time
from joblib import Memory
from llama_index.core.workflow import (
    Workflow,
    step,
    StartEvent,
    StopEvent
)
from llama_index.core.objects import ObjectIndex
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import Memory


from src.workflow.events import (
    PrepareEvent,
    IntentClassificationEvent,
    BusquedaEvent,
    QuerySplittingEvent,
    ToolRetrievalEvent,
    ToolCallEvent,
    DecisionEvent,
    FinalAnswerEvent
)

from src.utils.helpers import (
    parse_tool_metadata,
    detect_result_type,
    format_tool_results_as_json,
    build_memory_context
)

from src.core.config import (
    get_llm_intent,
    get_llm_splitting,
    get_llm_agent,
    get_llm_answer,
    WORKFLOW_CONFIG,
    SYSTEM_PROMPT,
    CONVERSATIONAL_RESPONSE,
)
from src.core.database import log_chat_interaction

from src.workflow.agent import  execute_agent_for_subquery
from typing import Optional, Tuple, List
from src.config import get_prompt_loader



def _extract_token_usage_from_response(response) -> dict:
    """Extrae conteo de tokens desde la respuesta del LLM si está disponible.

    La estructura exacta de `response.raw` puede variar según la versión de
    LlamaIndex / cliente OpenAI, por lo que esta función es deliberadamente
    tolerante a errores y simplemente retorna un dict con posibles claves:
    - tokens_input
    - tokens_output
    - tokens_total
    """
    usage_info: dict = {}

    try:
        raw = getattr(response, "raw", None)

        # Caso 1: raw ya es un dict con usage
        if isinstance(raw, dict):
            usage_dict = raw.get("usage") or raw
        else:
            # Caso 2: raw es un objeto con atributo `usage`
            usage_attr = getattr(raw, "usage", None)
            if usage_attr is None:
                usage_dict = None
            elif isinstance(usage_attr, dict):
                usage_dict = usage_attr
            else:
                # Podría ser un objeto tipo OpenAIUsage con atributos
                usage_dict = {
                    "prompt_tokens": getattr(usage_attr, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_attr, "completion_tokens", None),
                    "total_tokens": getattr(usage_attr, "total_tokens", None),
                }

        if not usage_dict:
            return usage_info

        tokens_input = usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens")
        tokens_output = usage_dict.get("completion_tokens") or usage_dict.get("output_tokens")
        tokens_total = usage_dict.get("total_tokens")

        usage_info["tokens_input"] = tokens_input
        usage_info["tokens_output"] = tokens_output
        usage_info["tokens_total"] = tokens_total

    except Exception:
        # En caso de cualquier problema simplemente retornamos dict vacío
        return {}

    return usage_info


class CorporateReActWorkflow(Workflow):
    """
    Workflow ReAct para el chatbot del Chatbot Corporativo.

    Pasos del workflow:
    1. prepare: Inicializa contexto y prepara la pregunta
    2. classify_intent: Clasifica intención (CONVERSACIONAL, BUSQUEDA, ANALÍTICA_SIMPLE, ANALÍTICA_DATOS)
    3. handle_busqueda: Maneja búsqueda de datasets disponibles (nuevo)
    4. query_splitting: Detecta si requiere múltiples datasets y divide en subconsultas
    5. retrieve_tools: Búsqueda semántica directa en ObjectIndex con la pregunta del usuario
    6. call_tools: Ejecuta las herramientas recuperadas (con subconsultas específicas)
    7. decide_next: Decide si necesita más herramientas o puede responder
    8. final_answer: Genera respuesta profesional (consolida resultados multi-dataset)

    FLUJOS POSIBLES:
    - CONVERSACIONAL: prepare → classify_intent → StopEvent (mensaje predefinido)
    - BUSQUEDA: prepare → classify_intent → handle_busqueda → StopEvent (lista datasets)
    - ANALÍTICA_SIMPLE: prepare → classify_intent → StopEvent (usa solo memoria)
    - ANALÍTICA_DATOS: prepare → classify_intent → query_splitting → retrieve_tools → call_tools → decide_next → final_answer

    EVENTOS DEL WORKFLOW:
    - PrepareEvent: Inicialización de la consulta
    - IntentClassificationEvent: Resultado de clasificación de intención
    - BusquedaEvent: Búsqueda de datasets disponibles
    - QuerySplittingEvent: Input para descomposición de consultas
    - ToolRetrievalEvent: Output de query_splitting, input para retrieve_tools (rompe bucle)
    - ToolCallEvent: Ejecución de herramientas
    - DecisionEvent: Decisión de continuar/terminar
    - FinalAnswerEvent: Respuesta final
    """

    def __init__(self, object_index: ObjectIndex, **kwargs):
        super().__init__(**kwargs)
        self.object_index = object_index
        # LLMs especializados por etapa del workflow
        self.llm_intent = get_llm_intent()
        self.llm_splitting = get_llm_splitting()
        self.llm_agent = get_llm_agent()
        self.llm_answer = get_llm_answer()
        self.max_iterations = WORKFLOW_CONFIG["max_iterations"]
        self.top_k_tools = WORKFLOW_CONFIG["top_k"]
        self.enable_query_splitting = WORKFLOW_CONFIG["enable_query_splitting"]
        self.splitting_top_k = WORKFLOW_CONFIG["splitting_top_k"]
        self.max_subqueries = WORKFLOW_CONFIG["max_subqueries"]

        # Inicializar memoria conversacional short-term
        self.enable_memory = WORKFLOW_CONFIG.get("enable_memory", True)
        if self.enable_memory:
            self.memory = Memory.from_defaults(
                token_limit=WORKFLOW_CONFIG.get("memory_token_limit", 6000)
            )
        else:
            self.memory = None

        # NUEVO: Session ID único y tracking de tiempo
        self.session_id = str(uuid.uuid4())
        self.start_time = None  # Se setea en prepare()

        print(f"🆔 Session ID: {self.session_id}")

    def reset_memory(self, verbose: bool = True):
        """Limpia la memoria conversacional (para nueva sesión o comando reset)."""
        if self.memory:
            self.memory.reset()
            if verbose:
                print("🧹 Memoria conversacional reiniciada\n")

    def get_chat_history(self) -> List[ChatMessage]:
        """Obtiene el historial de chat actual."""
        if self.memory:
            return self.memory.get_all()
        return []

    @step
    async def prepare(self, ev: StartEvent) -> IntentClassificationEvent:
        """
        Paso inicial: prepara el contexto y la pregunta del usuario.
        Integra memoria conversacional para mantener contexto entre preguntas.
        """
        # NUEVO: Capturar tiempo de inicio
        self.start_time = time.time()

        user_question = ev.get("user_question")

        if not user_question:
            raise ValueError("Se requiere 'user_question' en el evento de inicio")

        print(f"\n{'='*60}")
        print(f"📝 Pregunta del usuario: {user_question}")

        # Mostrar contexto de memoria si existe
        if self.enable_memory and self.memory:
            history = self.get_chat_history()
            if len(history) > 0:
                num_intercambios = len(history) // 2
                print(f"💭 Contexto previo: {num_intercambios} intercambio(s) anterior(es)")

        print(f"{'='*60}\n")

        # Agregar pregunta del usuario a la memoria
        if self.enable_memory and self.memory:
            self.memory.put(ChatMessage(role="user", content=user_question))

        # Pasar a clasificación de intención (nuevo step)
        return IntentClassificationEvent(
            user_question=user_question,
            intent_type="",  # Se determinará en classify_intent()
            justification="",
            requires_tools=True  # Default, se actualizará
        )


    @step
    async def classify_intent(self, ev: IntentClassificationEvent) -> QuerySplittingEvent | BusquedaEvent | StopEvent:
        """
        Clasifica la intención de la pregunta del usuario en 4 categorías:

        1. CONVERSACIONAL: Saludos, agradecimientos, preguntas sobre el sistema
           → Responde con mensaje predefinido institucional

        2. BUSQUEDA: Usuario busca datasets disponibles sin consultar datos
           → Deriva a búsqueda de datasets

        3. ANALÍTICA_SIMPLE: Requiere razonamiento sobre resultados previos
           → Usa memoria conversacional para responder sin nuevos datos

        4. ANALÍTICA_DATOS: Requiere consultar datasets específicos
           → Procede con búsqueda de herramientas
        """
        user_question = ev.user_question

        print(f"🧠 Clasificando intención de la pregunta...\n")

        # Construir contexto de memoria
        memory_context = ""
        if self.enable_memory and self.memory:
            history = self.get_chat_history()
            if len(history) > 2:  # Más de solo la pregunta actual
                memory_context = build_memory_context(history[:-1], max_messages=6)

        # Cargar ejemplos few-shot
        prompt_loader = get_prompt_loader()
        intent_examples = prompt_loader.format_intent_examples_for_prompt(max_per_category=3)

        # Prompt de clasificación
        classification_prompt = f"""# PROMPT DE CLASIFICACIÓN DE INTENCIONES - CHATBOT CORPORATIVO

**Tarea:** Analiza la consulta del usuario y clasifícala en una de las cuatro categorías del sistema. El foco principal es el **Ecosistema de Logística, Transporte, Infraestructura y Economía del país**.

---

### 1. CONTEXTO DE LA CONSULTA:
- **MEMORIA DE CONVERSACIÓN:** {memory_context if memory_context else "Sin historial previo"}
- **PREGUNTA DEL USUARIO:** {user_question}

---

### 2. DEFINICIÓN DEL ALCANCE (Scope Logístico-Económico)
Antes de clasificar, considera que los siguientes temas **SÍ pertenecen al ecosistema del proyecto** y NO deben marcarse como CONVERSACIONAL:
* **Macroeconomía y Precios:** Valor del dólar, IPC, TPM, precio de combustibles (diésel, petróleo, GNL), inflación y costos operativos.
* **Infraestructura y Territorio:** Puertos, aeropuertos, carreteras, pasos fronterizos, vías férreas, centros logísticos, comunas y regiones del país.
* **Comercio Exterior:** Exportaciones, importaciones, aranceles, aduanas, flujos de carga internacional.
* **Sostenibilidad y Capital Humano:** Emisiones de CO2, eficiencia energética, empleo en el sector transporte, brechas de género en logística.

---

### 3. CATEGORÍAS DE CLASIFICACIÓN:

#### **A. ANALÍTICA_DATOS (Consultas a base de datos)**
- **Criterio:** El usuario busca **datos específicos, cifras numéricas, estadísticas o métricas** que requieren consultar datasets externos.
- **Ejemplos:** "¿Cuál fue el movimiento de carga en 2023?", "¿A cuánto está el dólar hoy?", "¿Cuánto combustible se consumió en el Biobío?", "¿Qué región exporta más fruta?".
- **Palabras clave:** Cuánto, cuál es la cifra, ranking, evolución, tendencia, promedio, valor exacto.

#### **B. BUSQUEDA (Exploración de metadatos)**
- **Criterio:** El usuario quiere saber **qué información existe** o qué datasets hay disponibles, sin pedir el dato numérico todavía.
- **Ejemplos:** "¿Tienes datos de puertos?", "¿Qué información hay sobre exportaciones?", "¿Puedo ver estadísticas de camiones?".
- **Clave:** Pregunta por "disponibilidad", "catálogo" o "qué sabes sobre...".

#### **C. ANALÍTICA_SIMPLE (Uso de memoria)**
- **Criterio:** Preguntas que dependen **estrictamente del historial** de la conversación o de datos ya mostrados previamente.
- **Ejemplos:** "¿Y en el caso de Valparaíso?" (continuando una cifra previa), "¿Puedes graficar los datos que me diste?", "¿Cuál de esos dos años fue el mayor?".
- **Clave:** Usa pronombres o referencias contextuales ("eso", "aquello", "estos datos").

#### **D. CONVERSACIONAL (Fuera de Ámbito)**
- **Criterio:** Consultas sociales, saludos o temas totalmente ajenos a la logística y economía.
- **Ejemplos:** "Hola", "Gracias", "¿Quién eres?", "¿Cómo está el clima?", "¿Quién ganó el mundial?".
- **Regla Crítica:** Si la pregunta menciona indicadores económicos (Dólar, IPC) o transporte, **NUNCA** es conversacional.

---

### 4. INSTRUCCIONES DE SALIDA:
Responde **únicamente** en el siguiente formato, sin texto adicional:

CATEGORÍA: [ANALÍTICA_DATOS | BUSQUEDA | ANALÍTICA_SIMPLE | CONVERSACIONAL]
JUSTIFICACIÓN: [Breve explicación de 1 línea de por qué se asignó esta categoría, mencionando la relación con el ecosistema logístico si aplica]
"""


        # Llamar al LLM para clasificación
        response = await self.llm_intent.achat([
            ChatMessage(role="system", content="Eres un clasificador experto de intenciones de usuario."),
            ChatMessage(role="user", content=classification_prompt)
        ])

        classification_text = response.message.content.strip()

        # Parsear respuesta
        intent_type = "ANALÍTICA_DATOS"  # Default si falla el parseo
        justification = "No se pudo determinar"

        for line in classification_text.split("\n"):
            if line.startswith("CATEGORÍA:"):
                intent_raw = line.replace("CATEGORÍA:", "").strip()
                # Extraer solo la categoría (sin caracteres extra)
                if "CONVERSACIONAL" in intent_raw:
                    intent_type = "CONVERSACIONAL"
                elif "BUSQUEDA" in intent_raw or "BÚSQUEDA" in intent_raw:
                    intent_type = "BUSQUEDA"
                elif "ANALÍTICA_SIMPLE" in intent_raw:
                    intent_type = "ANALÍTICA_SIMPLE"
                elif "ANALÍTICA_DATOS" in intent_raw:
                    intent_type = "ANALÍTICA_DATOS"
            elif line.startswith("JUSTIFICACIÓN:"):
                justification = line.replace("JUSTIFICACIÓN:", "").strip()

        print(f"🎯 Categoría detectada: {intent_type}")
        print(f"💡 Justificación: {justification}\n")

        # CASO 1: CONVERSACIONAL - Mensaje predefinido institucional
        if intent_type == "CONVERSACIONAL":
            print(f"💬 Pregunta conversacional - Usando mensaje predefinido institucional\n")

            final_answer = CONVERSATIONAL_RESPONSE

            # Guardar en memoria
            if self.enable_memory and self.memory:
                self.memory.put(ChatMessage(role="assistant", content=final_answer))

            print(f"✅ Respuesta: {final_answer}\n")

            # NUEVO: Guardar log en base de datos
            latency_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
            try:
                log_chat_interaction(
                    session_id=self.session_id,
                    user_input=user_question,
                    bot_output=final_answer,
                    latency_ms=latency_ms,
                    intent_type="CONVERSACIONAL",
                    sources=[],
                    tool_results=[],
                    agent_stats={},
                    success=True,
                    error_message=None
                )
            except Exception as log_error:
                print(f"⚠️  Error logging to DB: {log_error}")

            return StopEvent(result={
                "answer": final_answer,
                "sources": [],
                "success": True,
                "intent_type": "CONVERSACIONAL",
                "tool_results": []
            })

        # CASO 2: BUSQUEDA - Derivar a búsqueda de datasets
        elif intent_type == "BUSQUEDA":
            print(f"🔎 Búsqueda de datasets - Derivando a búsqueda\n")

            return BusquedaEvent(
                user_question=user_question,
                search_query=user_question,
                search_results=[]
            )

        # CASO 3: ANALÍTICA_SIMPLE - Usar memoria sin nuevos datos
        elif intent_type == "ANALÍTICA_SIMPLE":
            print(f"🔍 Pregunta analítica simple - Usando memoria conversacional\n")

            # Verificar que haya historial
            if not self.enable_memory or not self.memory or len(self.get_chat_history()) <= 2:
                print(f"⚠️ No hay suficiente contexto previo - Cambiando a ANALÍTICA_DATOS\n")
                intent_type = "ANALÍTICA_DATOS"
            else:
                # Generar respuesta usando solo memoria
                history = self.get_chat_history()
                context_text = build_memory_context(history[:-1], max_messages=10)

                analytical_prompt = f"""Responde basándote EXCLUSIVAMENTE en el contexto de la conversación previa:

CONTEXTO DE CONVERSACIÓN:
{context_text}

PREGUNTA ACTUAL: {user_question}

INSTRUCCIONES:
1. Usa SOLO la información del contexto conversacional
2. NO inventes datos ni hagas suposiciones
3. Si falta información crítica, pide aclaración
4. Sé preciso y conciso
5. Formatea números legiblemente"""

                messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

                # Incluir historial completo (sin la pregunta actual)
                for msg in history[:-1]:
                    messages.append(msg)

                # Agregar prompt analítico
                messages.append(ChatMessage(role="user", content=analytical_prompt))

                analytical_response = await self.llm_answer.achat(messages)
                final_answer = analytical_response.message.content

                # Guardar en memoria
                if self.enable_memory and self.memory:
                    self.memory.put(ChatMessage(role="assistant", content=final_answer))

                print(f"✅ Respuesta: {final_answer}\n")

                # NUEVO: Guardar log en base de datos
                latency_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
                try:
                    log_chat_interaction(
                        session_id=self.session_id,
                        user_input=user_question,
                        bot_output=final_answer,
                        latency_ms=latency_ms,
                        intent_type="ANALÍTICA_SIMPLE",
                        sources=[],
                        tool_results=[],
                        agent_stats={},
                        success=True
                    )
                except Exception as log_error:
                    print(f"⚠️  Error logging to DB: {log_error}")

                return StopEvent(result={
                    "answer": final_answer,
                    "sources": [],
                    "success": True,
                    "intent_type": "ANALÍTICA_SIMPLE",
                    "tool_results": []
                })

        # CASO 4: ANALÍTICA_DATOS - Proceder con query splitting y tools
        print(f"📊 Pregunta analítica con datos - Procediendo a buscar datasets\n")

        return QuerySplittingEvent(
            user_question=user_question,
            subqueries=[{"query": user_question}],
            num_subqueries=1
        )


    @step
    async def handle_busqueda(self, ev: BusquedaEvent) -> StopEvent:
        """
        Maneja búsqueda de datasets sin ejecutar consultas de datos.
        Busca en el ObjectIndex y retorna lista de datasets relevantes con metadata.

        Este paso se ejecuta cuando el usuario quiere explorar qué datasets
        están disponibles, SIN consultar datos específicos.
        """
        user_question = ev.user_question

        print(f"🔎 Buscando datasets relevantes en el catálogo...\n")

        # Usar ObjectIndex para buscar herramientas relevantes (top 3)
        retriever = self.object_index.as_retriever(similarity_top_k=3)
        retrieved_objs = retriever.retrieve(user_question)

        search_results = []
        for obj in retrieved_objs:
            tool = obj
            tech_meta = tool.technical_metadata

            search_results.append({
                "codigo": tech_meta["codigo"],
                "nombre": tool.metadata.name,
                "titulo": tech_meta["titulo"],
                "categoria": tech_meta["categoria"],
                "descripcion": tech_meta["descripcion"],
                "cobertura_temporal": tech_meta["cobertura_temporal"],
                "palabras_claves": tech_meta["palabras_claves"],
                "unidad": tech_meta["unidad"],
                "columnas_formateadas": parse_column_descriptions(
                    tech_meta["columnas"],
                    tech_meta["descripcion_columnas"]
                ),
                "fuente": tech_meta["fuente"],
                "enlace_fuente": tech_meta["enlace_fuente"],
                "frecuencia_actualizacion": tech_meta["frecuencia_actualizacion"],
                "desagregacion_espacial": tech_meta["desagregacion_espacial"],
                "desagregacion_temporal": tech_meta["desagregacion_temporal"],
                "nota": truncate_note(tech_meta["nota"], max_length=300)
            })

            print(f"  ✓ Encontrado: {tech_meta['titulo']}")

        print(f"\n📦 Total: {len(search_results)} datasets encontrados\n")

        # Generar respuesta con lista estructurada de datasets
        search_prompt = f"""Basándote en la siguiente búsqueda de datasets del Chatbot Corporativo, presenta los resultados de forma clara y profesional CON FORMATO ENRIQUECIDO.

BÚSQUEDA DEL USUARIO: {user_question}

DATASETS ENCONTRADOS (en orden de relevancia):
{json.dumps(search_results, indent=2, ensure_ascii=False)}

INSTRUCCIONES DE FORMATO:
1. Presenta los datasets en lista numerada (máximo 3)
2. Para cada dataset usa EXACTAMENTE este formato con emojis:

**[N]. [CODIGO] - [TITULO]**

📋 **Descripción**: [descripcion]

📊 **Estructura de datos**:
- **Columnas**:
[columnas_formateadas con indentación preservada]

📅 **Cobertura**:
- Temporal: [cobertura_temporal] ([desagregacion_temporal])
- Espacial: [cobertura_espacial] ([desagregacion_espacial])
- Unidad: [unidad]

🏢 **Fuente**: [fuente]
- Actualización: [frecuencia_actualizacion]
- Enlace: [enlace_fuente]

ℹ️ **Nota**: [nota] (solo si hay nota relevante y no es "Sin notas")

---

3. Usa un tono institucional y profesional
4. Al final, invita al usuario a consultar datos específicos
5. NO inventes información que no esté en el JSON
6. Preserva la indentación de las columnas formateadas
7. Si un campo es "N/A" o vacío, omite esa línea
8. Si la nota es "Sin notas", omite la sección completa de Nota

Ejemplo del formato esperado:

**1. C018 - Carga transferida en puertos por tipo de carga y región**

📋 **Descripción**: Toneladas transferidas en los puertos del país, por tipo de carga y operación...

📊 **Estructura de datos**:
- **Columnas**:
  • Puerto: puerto
  • Operación: tipo de operación
  • Año: año de la operación
  • Tipo de Carga: tipo de carga
  • Carga: cantidad de carga en toneladas
  • Región: región del país donde se ubica el puerto

📅 **Cobertura**:
- Temporal: Desde 2007, desfase de 8 meses (Años)
- Espacial: Nacional / Local (Puerto)
- Unidad: Tonelada

🏢 **Fuente**: FUENTE_FICTICIA
- Actualización: Anual
- Enlace: https://fuente-ficticia.local/...

ℹ️ **Nota**: La fuente no publicó esta información en la última edición...

---

¿Desea consultar algún dato específico de estos datasets?

Genera tu respuesta ahora siguiendo ESTRICTAMENTE este formato:
"""

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=search_prompt)
        ]

        response = await self.llm_splitting.achat(messages)
        final_answer = response.message.content

        # Guardar en memoria
        if self.enable_memory and self.memory:
            self.memory.put(ChatMessage(role="assistant", content=final_answer))

        print(f"✅ Respuesta de búsqueda generada:\n{final_answer}\n")

        # NUEVO: Guardar log en base de datos
        latency_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        try:
            log_chat_interaction(
                session_id=self.session_id,
                user_input=user_question,
                bot_output=final_answer,
                latency_ms=latency_ms,
                intent_type="BUSQUEDA",
                sources=[r["nombre"] for r in search_results],
                tool_results=[],
                agent_stats={},
                success=True
            )
        except Exception as log_error:
            print(f"⚠️  Error logging to DB: {log_error}")

        return StopEvent(result={
            "answer": final_answer,
            "sources": [r["nombre"] for r in search_results],
            "success": True,
            "intent_type": "BUSQUEDA",
            "search_results": search_results,
            "tool_results": []
        })


    @step
    async def query_splitting(self, ev: QuerySplittingEvent) -> ToolRetrievalEvent:
        """
        Descompone la pregunta en subconsultas (1 a n).
        Solo se ejecuta si query_splitting está habilitado.
        """
        user_question = ev.user_question

        # Si feature está desactivada, pasar directamente a retrieve_tools
        if not self.enable_query_splitting:
            print(f"🔀 Query splitting desactivado, usando consulta única\n")
            return ToolRetrievalEvent(
                user_question=user_question,
                subqueries=[{"query": user_question}],
                num_subqueries=1
            )

        print(f"🔀 Descomponiendo pregunta en subconsultas...\n")

        # Cargar ejemplos few-shot para splitting
        prompt_loader = get_prompt_loader()

        # Construir contexto conversacional si existe
        context_info = ""
        if self.enable_memory and self.memory:
            history = self.get_chat_history()
            # Excluir la última pregunta (que ya está en user_question)
            if len(history) > 2:
                recent_history = history[-7:-1]  # Últimos 3 intercambios (sin incluir pregunta actual)
                if recent_history:
                    context_info = "\n\nCONTEXTO DE CONVERSACIÓN PREVIA:\n"
                    for msg in recent_history:
                        role = "Usuario" if msg.role == "user" else "Asistente"
                        preview = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
                        context_info += f"{role}: {preview}\n"
                    context_info += "\n"

        splitting_prompt = f"""Analiza la siguiente pregunta del usuario sobre logística:
{context_info}
PREGUNTA ACTUAL: {user_question}

Tu tarea: Descomponer la pregunta en subconsultas independientes y específicas.

REGLAS:
1. Si la pregunta es SIMPLE (un solo aspecto):
   - Devuelve 1 subconsulta con la pregunta original reformulada de forma clara

2. Si la pregunta es COMPLEJA (múltiples aspectos/datasets):
   - Divide en N subconsultas independientes (una por dataset necesario)
   - Cada subconsulta debe ser específica, clara y autocontenida
   - Máximo {self.max_subqueries} subconsultas

3. REGLA DE TRANSPORTE MULTIMODAL:
   - Solo descompón en subconsultas de (Terrestre, Aéreo, Marítimo) cuando la pregunta sea de VOLUMEN, FLUJO o CAPACIDAD de carga genérica.
   - NO apliques esta división si la consulta es sobre normativas, accidentes generales, infraestructura compartida o indicadores macroeconómicos.



FORMATO DE RESPUESTA OBLIGATORIO:
NÚMERO_SUBCONSULTAS: [número]

SUBCONSULTA_1:
Texto: [pregunta específica]

SUBCONSULTA_2:
Texto: [pregunta específica]

(continuar si hay más)

Genera tu análisis ahora:
"""

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=splitting_prompt)
        ]

        response = await self.llm_answer.achat(messages)
        splitting_text = response.message.content

        print(f"🧩 Análisis de división:\n{splitting_text}\n")

        # Parsear respuesta
        num_subqueries = 1
        subqueries = []

        try:
            lines = splitting_text.split('\n')

            # Extraer número de subconsultas
            for line in lines:
                if "NÚMERO_SUBCONSULTAS:" in line or "NUMERO_SUBCONSULTAS:" in line:
                    num_str = line.split(":")[-1].strip()
                    try:
                        num_subqueries = int(num_str)
                    except:
                        num_subqueries = 1
                    break

            # Extraer subconsultas
            current_subquery = None
            for line in lines:
                line = line.strip()

                if line.startswith("SUBCONSULTA_"):
                    if current_subquery and current_subquery.get("query"):
                        subqueries.append(current_subquery)
                    current_subquery = {"query": ""}

                elif line.startswith("Texto:") and current_subquery is not None:
                    current_subquery["query"] = line.split("Texto:", 1)[1].strip()

            # Agregar última subconsulta
            if current_subquery and current_subquery.get("query"):
                subqueries.append(current_subquery)

            # Validación: Si no se parseó correctamente, usar pregunta original
            if not subqueries or num_subqueries == 0:
                print("⚠️  Error en parsing, usando pregunta original\n")
                num_subqueries = 1
                subqueries = [{"query": user_question}]

            # Limitar número de subconsultas
            if len(subqueries) > self.max_subqueries:
                print(f"⚠️  Limitando subconsultas de {len(subqueries)} a {self.max_subqueries}\n")
                subqueries = subqueries[:self.max_subqueries]
                num_subqueries = self.max_subqueries

        except Exception as e:
            print(f"⚠️  Error parseando división: {str(e)}, usando pregunta original\n")
            num_subqueries = 1
            subqueries = [{"query": user_question}]

        # Logging
        print(f"✓ {num_subqueries} subconsulta(s)")
        if num_subqueries > 1:
            for idx, sq in enumerate(subqueries):
                print(f"  {idx+1}. {sq['query']}")

        print()

        return ToolRetrievalEvent(
            user_question=user_question,
            subqueries=subqueries,
            num_subqueries=num_subqueries
        )

    @step
    async def retrieve_tools(self, ev: ToolRetrievalEvent) -> ToolCallEvent:
        """
        Recupera herramientas relevantes del ObjectIndex usando búsqueda semántica.

        Retorna:
            tools: dict[int, List[Tool]] - Diccionario donde:
                - Llave: número de subconsulta (0, 1, 2, ...)
                - Valor: lista de objetos herramienta recuperados para esa subconsulta
        """
        user_question = ev.user_question
        subqueries = ev.subqueries
        num_subqueries = ev.num_subqueries

        tools = {}  # Estructura principal: {0: [tool1, tool2], 1: [tool3]}

        print(f"🔍 Buscando herramientas para {num_subqueries} subconsulta(s)\n")

        for idx, subquery_data in enumerate(subqueries):
            subquery_text = subquery_data["query"]

            # Determinar top_k según número de subconsultas
            if num_subqueries == 1:
                current_top_k = self.top_k_tools  # top_k normal para consulta simple
            else:
                current_top_k = self.splitting_top_k  # top_k más pequeño para múltiples

            if num_subqueries > 1:
                print(f"  Subconsulta {idx+1}: '{subquery_text}'")

            # Recuperar herramientas del ObjectIndex
            retriever = self.object_index.as_retriever(similarity_top_k=current_top_k)
            retrieved_objs = retriever.retrieve(subquery_text)

            # Almacenar herramientas para esta subconsulta
            #este bloque es necesario?
            subquery_tools = []
            for obj in retrieved_objs:
                tool = obj
                tool_name = tool.metadata.name
                subquery_tools.append(tool)
                print(f"    ✓ {tool_name}")

            # Guardar en dict con índice numérico
            tools[idx] = subquery_tools

            if num_subqueries > 1:
                print()

        return ToolCallEvent(
            user_question=user_question,
            subqueries=subqueries,
            tools=tools
        )

    @step
    async def call_tools(self, ev: ToolCallEvent) -> DecisionEvent:
        """
        Ejecuta las herramientas recuperadas usando FunctionAgents.

        - Crea un FunctionAgent por cada subquery
        - Cada agente respeta WORKFLOW_CONFIG['max_iterations'] para razonamiento iterativo
        - Los agentes se ejecutan en paralelo usando asyncio.gather
        - Cada agente recibe un system_prompt dinámico según su subquery
        - Manejo robusto de errores: éxito parcial permitido

        Args:
            ev: ToolCallEvent con subqueries y tools

        Returns:
            DecisionEvent con resultados consolidados
        """
        user_question = ev.user_question
        tools = ev.tools  # dict[int: List[Tool]]
        subqueries = ev.subqueries
        num_subqueries = len(subqueries)

        print(f"⚙️  Ejecutando {num_subqueries} agente(s) en paralelo...\n")

        # Verbose según configuración
        verbose = WORKFLOW_CONFIG.get("verbose", True)

        # tareas asíncronas para cada subquery
        tasks = []
        for idx, subquery_data in enumerate(subqueries):
            # Obtener tools para esta subquery usando el índice
            subquery_tools = tools.get(idx, [])

            # Crear tarea asíncrona para este agente
            task = execute_agent_for_subquery(
                subquery_data=subquery_data,
                subquery_index=idx,
                tools=subquery_tools,
                user_question=user_question,
                llm=self.llm_agent,
                verbose=verbose,
                num_subqueries=num_subqueries
            )
            tasks.append(task)

        # Ejecutar todos los agentes en paralelo
        print(f"🚀 Iniciando ejecución paralela de agentes...\n")
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar excepciones si las hay
        processed_results = []
        for idx, result in enumerate(tool_results):
            if isinstance(result, Exception):
                # Si gather retornó una excepción
                processed_results.append({
                    "tool": "N/A",
                    "dataset_code": "N/A",
                    "result": f"Excepción no capturada: {str(result)}",
                    "result_type": "text",
                    "metadata": {},
                    "pandas_code": "Error",
                    "success": False,
                    "subquery_index": idx,
                    "subquery_text": subqueries[idx]["query"],
                    "agent_iterations": 0,
                    "agent_scratchpad": [str(result)],
                    "tools_used": []
                })
            else:
                processed_results.append(result)

        tool_results = processed_results

        if num_subqueries > 1:
            print()  # Línea en blanco después de múltiples agentes

        # Consolidar observaciones
        observations = []
        successful_count = 0
        for tr in tool_results:
            if tr.get("success", False):
                successful_count += 1

            if num_subqueries > 1:
                observations.append(
                    f"[Subconsulta {tr['subquery_index']+1}] "
                    f"Dataset {tr['tool']}: {tr['result']}"
                )
            else:
                observations.append(f"Dataset {tr['tool']}: {tr['result']}")

        all_observations = "\n\n".join(observations)

        print(f"📊 Resultados consolidados:")
        print(f"   ✓ Exitosos: {successful_count}/{num_subqueries}")
        print(f"   ✗ Fallidos: {num_subqueries - successful_count}/{num_subqueries}")
        print(f"   📝 Observaciones: {all_observations[:300]}...\n")

        return DecisionEvent(
            user_question=user_question,
            tool_results=tool_results,
            all_observations=all_observations
        )

    @step
    async def decide_next(self, ev: DecisionEvent) -> FinalAnswerEvent:
        """
        Procesa los resultados de las herramientas y decide si generar respuesta final.
        Nota: En esta versión simplificada, siempre generamos respuesta con los datos obtenidos.
        """
        print(f"🤔 Procesando resultados...\n")

        # Verificar si tenemos resultados exitosos
        successful_results = [r for r in ev.tool_results if r.get("success", False)]

        if len(successful_results) > 0:
            print(f"✓ Se obtuvieron {len(successful_results)} resultados exitosos\n")
        else:
            print("⚠️  No se obtuvieron resultados exitosos, generando respuesta con la información disponible\n")

        return FinalAnswerEvent(
            user_question=ev.user_question,
            tool_results=ev.tool_results,
            final_answer=""  # Se generará en el siguiente paso
        )

    @step
    async def final_answer(self, ev: FinalAnswerEvent) -> StopEvent:
        """
        Genera la respuesta final en lenguaje natural profesional.
        Usa contexto JSON estructurado con metadata enriquecida.
        """
        user_question = ev.user_question
        tool_results = ev.tool_results

        print(f"✍️  Generando respuesta final...\n")

        # Detectar número de subconsultas
        num_subqueries = len(set(tr.get("subquery_index", 0) for tr in tool_results))

        # Consolidar fuentes
        sources = []
        for tr in tool_results:
            if tr.get("success", False):
                dataset_code = tr.get("dataset_code", tr.get("tool", "N/A"))
                sources.append(dataset_code)

        # Verificar que tengamos resultados
        successful_results = [r for r in tool_results if r.get("success", False)]
        if not successful_results:
            error_msg = "Lo siento, no pude encontrar información relevante para responder tu pregunta. Por favor, reformula tu consulta o verifica que los datos estén disponibles."

            # NUEVO: Guardar log de error en base de datos
            latency_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
            try:
                log_chat_interaction(
                    session_id=self.session_id,
                    user_input=user_question,
                    bot_output=error_msg,
                    latency_ms=latency_ms,
                    intent_type="ANALÍTICA_DATOS",
                    sources=[],
                    tool_results=tool_results,
                    agent_stats={},
                    success=False,
                    error_message="No successful tool results"
                )
            except Exception as log_error:
                print(f"⚠️  Error logging to DB: {log_error}")

            return StopEvent(result={
                "answer": error_msg,
                "sources": [],
                "success": False,
                "tool_results": tool_results
            })

        # Generar contexto JSON estructurado
        context_json = format_tool_results_as_json(tool_results)

        # Cargar ejemplos few-shot para generación de respuestas
        prompt_loader = get_prompt_loader()
        response_examples = prompt_loader.format_response_examples_for_prompt(max_examples=2)

        # Prompt según número de subconsultas
        if num_subqueries == 1:
            answer_prompt = f"""Basándote en los siguientes datos del Chatbot Corporativo (Demo) (en formato JSON estructurado), responde la pregunta del usuario de forma clara, precisa y profesional.

PREGUNTA DEL USUARIO:
{user_question}

DATOS OBTENIDOS (JSON ESTRUCTURADO):
{context_json}

CAMPOS IMPORTANTES DEL JSON:
- dataset: Código del dataset fuente
- titulo: Nombre descriptivo del dataset
- categoria: Categoría temática
- resultado_tipo: Tipo de dato (number, table, list, text)
- resultado: El valor o datos obtenidos
- unidad: Unidad de medida del resultado
- escala_numerica: Escala numérica aplicable
- cobertura_temporal: Período temporal de los datos

INSTRUCCIONES:
1. Responde SOLO con la información proporcionada en el JSON
2. Usa el campo "resultado_tipo" para formatear apropiadamente:
   - Si es "number": formatea con separadores de miles (ej: 1.234.567)
   - Si es "table": presenta en formato estructurado
   - Si es "list": presenta como lista ordenada
3. Menciona la "unidad" cuando sea relevante (ej: "toneladas", "TEU")
4. Usa la "escala_numerica" si es pertinente (ej: "millones de USD")
5. Si hay "cobertura_temporal", menciónala cuando sea importante
6. Usa un lenguaje profesional pero accesible
7. Menciona las fuentes de datos al final usando el campo "dataset"
8. NO inventes información que no esté en el JSON
9. Si los datos son insuficientes, indícalo claramente

Genera tu respuesta ahora:
"""
        else:
            answer_prompt = f"""Basándote en los siguientes datos del Chatbot Corporativo (Demo) (en formato JSON estructurado), responde la pregunta del usuario de forma clara, precisa y profesional.

PREGUNTA ORIGINAL DEL USUARIO:
{user_question}

DATOS OBTENIDOS (JSON ESTRUCTURADO - {num_subqueries} subconsultas):
{context_json}

CAMPOS IMPORTANTES DEL JSON:
- dataset: Titulo del dataset fuente
- subconsulta: Pregunta específica para este dataset
- resultado_tipo: Tipo de dato (number, table, list, text)
- resultado: El valor o datos obtenidos
- unidad: Unidad de medida del resultado
- escala_numerica: Escala numérica aplicable
- cobertura_temporal: Período temporal de los datos

INSTRUCCIONES:
1. INTEGRA los datos de TODAS las subconsultas en una respuesta coherente y unificada
2. Si la pregunta pide comparación, compara claramente los datos
3. Si la pregunta pide relación, explica cómo se relacionan los datos
4. Usa el campo "resultado_tipo" para formatear apropiadamente cada dato
5. Menciona "unidad" y "escala_numerica" cuando sean relevantes
6. Si hay "cobertura_temporal", úsala para dar contexto temporal
7. Usa un lenguaje profesional pero accesible
8. Menciona las fuentes de datos al final usando el campo "dataset"
9. NO inventes información que no esté en el JSON
10. Estructura tu respuesta de forma lógica y fácil de seguir

Genera tu respuesta ahora:
"""

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT)
        ]

        # Incluir historial conversacional (sin la pregunta actual que ya está en answer_prompt)
        if self.enable_memory and self.memory:
            history = self.get_chat_history()
            # Incluir solo mensajes previos (excluyendo la pregunta actual que es la última)
            if len(history) > 1:
                for msg in history[:-1]:
                    messages.append(msg)

        # Agregar el prompt de respuesta actual
        messages.append(ChatMessage(role="user", content=answer_prompt))

        response = await self.llm_answer.achat(messages)
        final_answer = response.message.content

        # Extraer uso de tokens del LLM (si está disponible en la respuesta)
        token_usage = _extract_token_usage_from_response(response)
        tokens_input = token_usage.get("tokens_input")
        tokens_output = token_usage.get("tokens_output")
        tokens_total = token_usage.get("tokens_total")

        # Guardar respuesta del asistente en memoria
        if self.enable_memory and self.memory:
            self.memory.put(ChatMessage(role="assistant", content=final_answer))

        print(f"{'='*60}")
        print(f"✅ RESPUESTA FINAL:")
        print(f"{'='*60}")
        print(final_answer)
        print(f"{'='*60}")
        print(f"📚 Fuentes: {', '.join(set(sources))}")
        print(f"{'='*60}\n")

        # Extraer código pandas ejecutado del primer resultado exitoso
        pandas_code = "No disponible"
        for tr in tool_results:
            if tr.get("success", False) and tr.get("pandas_code"):
                pandas_code = tr.get("pandas_code", "No disponible")
                break

        # Extraer estadísticas de agentes (incluyendo tokens si están disponibles)
        agent_stats = {
            "total_agents": len(tool_results),
            "successful_agents": len([r for r in tool_results if r.get("success", False)]),
            "total_iterations": sum(r.get("agent_iterations", 0) for r in tool_results),
            "tools_used": list(set([
                tool for r in tool_results
                for tool in r.get("tools_used", [])
            ])),
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens_total": tokens_total,
        }

        # NUEVO: Guardar log en base de datos (ANALÍTICA_DATOS exitoso)
        latency_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        try:
            log_chat_interaction(
                session_id=self.session_id,
                user_input=user_question,
                bot_output=final_answer,
                latency_ms=latency_ms,
                intent_type="ANALÍTICA_DATOS",
                sources=list(set(sources)),
                tool_results=tool_results,
                agent_stats=agent_stats,
                success=True
            )
        except Exception as log_error:
            print(f"⚠️  Error logging to DB: {log_error}")

        return StopEvent(result={
            "answer": final_answer,
            "sources": list(set(sources)),
            "success": True,
            "pandas_code": pandas_code,
            "tool_results": tool_results,  # Para debugging/testing
            "agent_stats": agent_stats  # Estadísticas de agentes
        })
