# Chatbot Corporativo (Demo)

> **Nota:** Este repositorio es una versión pública de un proyecto de portafolio. Los datos originales (48 datasets reales) han sido eliminados y reemplazados por datos sintéticos (mock data) para cumplir con políticas de confidencialidad y acuerdos de no divulgación (NDA).

Chatbot para el análisis de datos logísticos. Este archivo proporciona las instrucciones necesarias para poner en marcha el proyecto, ajustar su configuración, y llevar a cabo el testeo y la depuración de la herramienta.

## ✨ Características

- **Arquitectura ReAct Workflow**: Flujo de trabajo explícito con 8 pasos secuenciales
- **2 datasets ficticios (Mock)**: Datos sobre puertos, transporte, comercio exterior, infraestructura, etc.
- **4 tipos de clasificación**: CONVERSACIONAL, BÚSQUEDA, ANALÍTICA_SIMPLE, ANALÍTICA_DATOS
- **Memoria conversacional**: Mantiene contexto entre preguntas
- **Telemetría completa**: Trazabilidad con OpenTelemetry + Arize Phoenix
- **Agentes paralelos**: Ejecución simultánea de múltiples subconsultas
- **Base de datos**: Logging completo de interacciones en SQLite/PostgreSQL

## 📋 Requerimientos

- **Python 3.12** (recomendado, compatible con 3.10+)
- **Docker** (opcional, para telemetría Phoenix)

## 📦 Instalación

### Opción 1: Con Pipenv (Recomendado)

```bash
# Clonar repositorio
git clone <url>
cd chatbot2026

# Instalar pipenv si no lo tienes
pip install pipenv

# Instalar dependencias
pipenv install

# Configurar API key de OpenAI
cp .env.example .env  # Linux/macOS
# o copy .env.example .env  # Windows (CMD)
# Editar .env y agregar tu OPENAI_API_KEY

# Activar entorno virtual
pipenv shell
```

### Opción 2: Con venv

```bash
# Clonar repositorio
git clone <url>
cd chatbot2026

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
source .venv/bin/activate  # Linux/macOS
# o .venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar API key de OpenAI
cp .env.example .env  # Linux/macOS
# o copy .env.example .env  # Windows (CMD)
# Editar .env y agregar tu OPENAI_API_KEY
```

🔑 Detalles sobre como ingresar la OPENAI_API_KEY y más sobre las variables de entorno en la seccion de [configuraciones del sistema](#configuraciones-del-sistema).

## 🚀 Uso

### Ejecutar chatbot interactivo

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto** (`chatbot2026/`)

**Con Pipenv:**
```bash
# Opción 1: Dentro del shell de pipenv
pipenv shell
python main.py

# Opción 2: Fuera del shell
pipenv run python main.py
```

**Con venv (requirements.txt):**
```bash
# Activar entorno virtual (si no está activado)
source .venv/bin/activate  # Linux/macOS
# o .venv\Scripts\activate  # Windows

# Ejecutar chatbot
python main.py
```

**Nota**: Desde este punto, todos los comandos se asumen dentro del entorno virtual activado.

## 🔄 Regenerar Índice de Herramientas

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto** (`chatbot2026/`)

### ¿Qué es el ObjectIndex?

El **ObjectIndex** es una estructura de datos vectorial que almacena herramientas, especificamente una por cada dataset disponible las cuales contienen:
- **Embeddings de búsqueda**: Representación vectorial de las descripciones de cada dataset
- **Metadata asociada**: Información sobre columnas, periodo, fuente de datos
- Una **QueryEngineTools** la cual es la encargada de transformar una consulta a código y ejecutarlo.

Esta estructura permite realizar **búsqueda semántica** rápida: dado una consulta del usuario, el sistema encuentra automáticamente qué datasets son más relevantes sin necesidad de especificar nombres exactos.

El ObjectIndex se persiste en el directorio `storage_tools/` para evitar tener que regenerarlo en cada ejecución del chatbot.

### Regenerar el Índice

Usa el script `rebuild_index.py` cuando necesites actualizar el indice:


### Comandos Disponibles

```bash
# Regenerar índice completo (elimina y recrea)
python rebuild_index.py

# Solo verificar estado del índice
python rebuild_index.py --check

# Regenerar sin eliminar índice previo
python rebuild_index.py --no-force

# Modo silencioso
python rebuild_index.py --quiet
```

### ¿Cuándo Regenerar el Índice?

**Regeneración requerida:**
- ✅ Agregaste nuevos datasets en `json/data/`
- ✅ Modificaste metadata en `json/metadata/`
- ✅ Cambiaste `EMBEDDING_MODEL` o `EMBEDDING_DIMENSIONS` en `.env`
- ✅ Actualizaste descripciones LLM en `json/llm_descriptions.json`

**NO requiere regeneración:**
- ❌ Cambios en código Python (`src/`)
- ❌ Modificación de prompts del workflow
- ❌ Ajustes en configuración de LLM (temperatura, max_iterations)
- ❌ Actualización de datos dentro de archivos JSON existentes (el chatbot lee JSON en tiempo real)

### Automatización con Cron

> **⚠️ Importante**: Usa rutas absolutas en crontab y asegúrate de que el usuario que ejecuta el cron tenga permisos.

Para actualizaciones periódicas automáticas:

```bash
# Editar crontab
crontab -e

# Ejemplo: Regenerar índice todos los días a las 3 AM
# Reemplaza /ruta/al/proyecto con la ruta absoluta a tu instalación
0 3 * * * cd /ruta/al/proyecto && /ruta/al/proyecto/.venv/bin/python rebuild_index.py --quiet >> /ruta/al/proyecto/logs/rebuild.log 2>&1

# Ejemplo con pipenv (si usas pipenv)
0 3 * * * cd /home/usuario/chatbot2026 && /usr/local/bin/pipenv run python rebuild_index.py --quiet >> logs/rebuild.log 2>&1

# Regenerar cada hora
0 * * * * cd /ruta/al/proyecto && /ruta/al/proyecto/.venv/bin/python rebuild_index.py --quiet
```

**Tips para crontab:**
- Usa `which pipenv` para encontrar la ruta exacta de pipenv
- Usa `pwd` dentro del directorio del proyecto para obtener la ruta absoluta
- Verifica logs en `logs/rebuild.log` para debugging

### Verificación de Estado

```bash
# Ver información del índice actual
python rebuild_index.py --check
```

### Tiempo de Regeneración

- **Índice completo**: ~30-60 segundos (depende de la API de OpenAI)
- **Solo verificación**: <1 segundo

> **Nota**: La regeneración actual **NO es incremental**. Siempre recrea todo el índice desde cero, reembedding todas las descripciones de herramientas.

## 📁 Estructura del Proyecto

```
chatbot2026/
├── src/                                  # Código fuente principal
│   ├── cli/                             # Interfaz de línea de comandos
│   │   ├── interactive.py               # Chat interactivo principal
│   │   └── query_logs.py                # Gestión de logs de consultas
│   │
│   ├── config/                          # Configuración y prompts
│   │   ├── prompt_loader.py             # Cargador dinámico de prompts
│   │   └── few_shot_examples.json       # Ejemplos para prompts
│   │
│   ├── core/                            # Componentes centrales del sistema
│   │   ├── config.py                    # Configuración principal (LLMs, embeddings, workflow)
│   │   ├── database.py                  # Gestión de base de datos SQL (logging)
│   │   ├── index_manager.py             # Gestión de ObjectIndex (herramientas)
│   │   └── telemetry.py                 # Telemetría OpenTelemetry + Phoenix
│   │
│   ├── tools/                           # Herramientas del sistema
│   │   ├── dataset_analysis_tool.py     # Análisis automático de datasets
│   │   ├── llm_description_generator.py # Generación de descripciones con LLM
│   │   ├── metadata_extractor.py        # Extracción de metadata de JSON
│   │   ├── pandas_wrapper.py            # Wrapper seguro para PandasQueryEngine
│   │   └── tools_factory.py             # Factory de QueryEngineTools
│   │
│   ├── utils/                           # Utilidades generales
│   │   ├── helpers.py                   # Funciones auxiliares del workflow
│   │   └── datasets_dict.json           # Diccionario de datasets disponibles
│   │
│   ├── workflow/                        # ReAct Workflow (arquitectura principal)
│   │   ├── workflow.py                  # Workflow principal (8 pasos)
│   │   ├── agent.py                     # FunctionAgent para ejecución de tools
│   │   └── events.py                    # Eventos tipados del workflow
│   │
│   └── __init__.py                      # Exports del módulo src
│
├── json/                                 # Datasets y metadata
│   ├── data/                            # 48 archivos JSON con datos (c001-p051)
│   ├── metadata/                        # Metadata procesada (48 archivos)
│   ├── raw_metadata/                    # Metadata original extraída
│   ├── llm_descriptions.json            # Descripciones generadas por LLM
│   └── analisis.ipynb                   # Notebook de análisis de datos
│
├── tests/                                # Tests y evaluación
│   ├── test_poolDS.py                   # Test completo con golden dataset
│   ├── test_classify_intent.py          # Test de clasificación de intenciones
│   ├── test_analizar_dataset.py         # Test de análisis de datasets
│   ├── test_consultas.json              # Dataset de test principal
│   ├── test_full.json                   # Dataset de test extendido
│   └── test_preguntas_mix.json          # Dataset mixto de pruebas
│
├── scripts/                              # Scripts auxiliares de mantenimiento
│   ├── generar_descripciones_llm.py     # Generar descripciones con LLM
│   ├── generar_diccionario_datasets.py  # Generar diccionario de datasets
│   └── extraer_texto_busqueda.py        # Extraer textos para búsqueda
│
├── storage_tools/                        # ObjectIndex persistido (embeddings)
├── logs/                                 # Reportes de tests en HTML/JSON
├── phoenix_data/                         # Datos de telemetría (Phoenix)
│
├── main.py                              # Entry point principal (ejecutar chatbot)
├── rebuild_index.py                     # Script para regenerar ObjectIndex
├── test_analysis_tool.py                # Script de prueba de análisis
│
├── Pipfile                              # Dependencias (pipenv)
├── Pipfile.lock                         # Lock de versiones exactas
├── requirements.txt                     # Dependencias (pip alternativo)
│
├── .env                                 # Variables de entorno (NO en git)
├── .env.example                         # Template de variables de entorno
│
├── docker-compose.yml                   # Configuración Phoenix (telemetría)
├── chatbot.db                           # Base de datos SQLite (logs de chat)
│
├── README.md                            # Esta documentación
└── AGENTS.md                            # Guía técnica detallada para agentes
```

### Descripción de Módulos Clave

#### `src/workflow/workflow.py`
Implementa el **ReAct Workflow** de 8 pasos:
1. **prepare**: Inicializa la consulta
2. **classify_intent**: Clasifica en CONVERSACIONAL/BÚSQUEDA/ANALÍTICA_SIMPLE/ANALÍTICA_DATOS
3. **handle_busqueda**: Maneja búsquedas de datasets (solo para BÚSQUEDA)
4. **query_splitting**: Divide consultas complejas en subconsultas
5. **retrieve_tools**: Recupera herramientas relevantes (búsqueda semántica)
6. **call_tools**: Ejecuta QueryEngineTools con PandasQueryEngine
7. **decide_next**: Valida resultados y decide si continuar
8. **final_answer**: Genera respuesta final en lenguaje natural

#### `src/core/index_manager.py`
Gestiona el **ObjectIndex** de LlamaIndex que contiene 48 QueryEngineTools. Usa embeddings para búsqueda semántica de herramientas relevantes.

#### `src/tools/tools_factory.py`
Crea QueryEngineTools a partir de archivos JSON. Cada tool incluye:
- PandasQueryEngine para consultas en lenguaje natural
- Metadata descriptiva (nombre, periodo, columnas)
- Descripción generada por LLM (300 palabras)

#### `src/workflow/agent.py`
Implementa **FunctionAgent** de LlamaIndex que ejecuta tools de forma iterativa usando razonamiento ReAct (Reason + Act).

#### `src/core/database.py`
Logging de todas las interacciones en base de datos SQL:
- Consultas y respuestas
- Latencia y métricas
- Clasificación de intenciones
- Fuentes utilizadas
- Estadísticas de agentes

## 🔄 Arquitectura: ReAct Workflow

El chatbot usa un flujo de trabajo explícito de **8 pasos** con **4 tipos de clasificación de intenciones**:

### Flujo del Workflow

```
┌────────────────────────────────────────────────────────────────┐
│  1. PREPARE                                                    │
│     ▸ Inicializar consulta del usuario                        │
│     ▸ Preparar estado inicial del workflow                    │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  2. CLASSIFY_INTENT                                            │
│     ▸ Clasificar intención en 4 categorías:                   │
│       • CONVERSACIONAL: Saludos, info del sistema             │
│       • BÚSQUEDA: Explorar datasets disponibles               │
│       • ANALÍTICA_SIMPLE: Usar memoria conversacional         │
│       • ANALÍTICA_DATOS: Consultar datasets específicos       │
└────────────────────────────────────────────────────────────────┘
         │
         ├──[CONVERSACIONAL]────→ StopEvent (mensaje institucional)
         │
         ├──[BÚSQUEDA]──────────→ 3. HANDLE_BÚSQUEDA → StopEvent (lista datasets)
         │
         ├──[ANALÍTICA_SIMPLE]──→ StopEvent (usa solo memoria)
         │
         └──[ANALÍTICA_DATOS]───→ Continúa al paso 4
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  4. QUERY_SPLITTING                                            │
│     ▸ Descomponer pregunta en 1-n subconsultas                │
│     ▸ N=1 para preguntas simples, N>1 para complejas          │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  5. RETRIEVE_TOOLS                                             │
│     ▸ Búsqueda semántica en ObjectIndex                       │
│     ▸ Recuperar tools para cada subconsulta                   │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  6. CALL_TOOLS                                                 │
│     ▸ Ejecutar QueryEngineTools (PandasQueryEngine)           │
│     ▸ Ejecución paralela de agentes                           │
│     ▸ Generar código Python por cada subconsulta              │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  7. DECIDE_NEXT                                                │
│     ▸ Validar si los resultados son suficientes               │
│     ▸ Decidir: generar respuesta o reintentar                 │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  8. FINAL_ANSWER                                               │
│     ▸ Generar respuesta final en lenguaje natural             │
│     ▸ Integrar datos de todas las subconsultas                │
│     ▸ Incluir fuentes utilizadas                              │
└────────────────────────────────────────────────────────────────┘
```

### Clasificación de Intenciones (4 Categorías)

#### 1. **CONVERSACIONAL**
- **Uso**: Saludos, despedidas, preguntas sobre el sistema
- **Respuesta**: Mensaje predefinido institucional
- **Ejemplos**: "Hola", "¿Qué puedes hacer?", "Gracias"
- **Flujo**: `prepare → classify_intent → StopEvent`

#### 2. **BÚSQUEDA**
- **Uso**: Usuario busca datasets disponibles sin consultar datos
- **Respuesta**: Lista de hasta 3 datasets relevantes con metadata
- **Ejemplos**: "¿Qué datasets tienes sobre puertos?", "Muéstrame datos de transporte"
- **Flujo**: `prepare → classify_intent → handle_busqueda → StopEvent`

#### 3. **ANALÍTICA_SIMPLE**
- **Uso**: Preguntas respondibles con información en memoria
- **Respuesta**: Usa solo contexto conversacional previo
- **Ejemplos**: "¿Qué es el LPI?", "Explica el indicador anterior"
- **Flujo**: `prepare → classify_intent → StopEvent`

#### 4. **ANALÍTICA_DATOS**
- **Uso**: Requiere consultar datasets específicos
- **Respuesta**: Ejecuta consultas en datasets y retorna resultados
- **Ejemplos**: "¿Cuánta carga en Valparaíso 2023?", "Top 5 puertos por TEUs"
- **Flujo**: `prepare → classify_intent → ... → final_answer` (workflow completo)

## Configuraciones del sistema

### Variables de Entorno (.env)

```bash
# Requerido
OPENAI_API_KEY=sk-...

# Opcional
OPENAI_MODEL=gpt-4o              # Default: gpt-4o
EMBEDDING_MODEL=text-embedding-3-small  # Default: text-embedding-3-small
```

### Modificar Configuración

Editar `src/core/config.py` para ajustar:
- Modelos de LLM y embeddings
- Timeouts del workflow
- Parámetros de temperatura
- Top-K de herramientas
- Configuración de telemetría

### Parámetros Configurables (src/core/config.py)

#### Modelos LLM Especializados

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `LLM_INTENT_MODEL` | `gpt-5.1` | Modelo para clasificación de intenciones (paso 2) |
| `LLM_SPLITTING_MODEL` | `gpt-5.1` | Modelo para división de consultas (paso 4) |
| `LLM_AGENT_MODEL` | `gpt-5.1` | Modelo para agentes que consultan datasets (paso 6) |
| `LLM_ANSWER_MODEL` | `gpt-5.1` | Modelo para redacción de respuestas finales (paso 8) |
| `LLM_EVALUADOR_MODEL` | `gpt-4o-mini` | Modelo para evaluación en tests |
| `LLM_DESCRIPTION_MODEL` | `gpt-5.1` | Modelo para generar descripciones de datasets |
| `LLM_TEMPERATURE` | `0` | Temperatura para generación (0 = determinista) |
| `LLM_MAX_TOKENS` | `4096` | Máximo de tokens en respuestas |

#### Embeddings

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Modelo de embeddings para búsqueda semántica |
| `EMBEDDING_DIMENSIONS` | `1536` | Dimensiones del vector de embeddings |

#### Workflow ReAct

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `TOOL_RETRIEVAL_TOP_K` | `2` | Número de herramientas a recuperar por subconsulta |
| `MAX_REASONING_ITERATIONS` | `5` | Máximo de iteraciones del ciclo ReAct por agente |
| `VERBOSE_WORKFLOW` | `True` | Activar logs detallados del workflow |
| `WORKFLOW_TIMEOUT` | `300` | Timeout en segundos para el workflow completo |
| `ENABLE_MULTI_TOOL` | `True` | Permitir múltiples herramientas simultáneas |
| `REACT_ENABLE_MEMORY` | `True` | Activar memoria conversacional entre preguntas |
| `REACT_MEMORY_TOKEN_LIMIT` | `6000` | Límite de tokens para historial de chat |

#### Query Splitting

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `ENABLE_QUERY_SPLITTING` | `True` | Activar división de consultas multi-dataset |
| `QUERY_SPLITTING_TOP_K` | `2` | Top-K herramientas por subconsulta |
| `MAX_SUBQUERIES` | `5` | Máximo de subconsultas permitidas |

#### Generación de Descripciones

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `USE_LLM_DESCRIPTIONS` | `True` | Usar descripciones generadas por LLM vs metadata simple |
| `LLM_DESCRIPTION_TARGET_WORDS` | `300` | Objetivo de palabras por descripción de dataset |
| `LLM_DESCRIPTION_TEMPERATURE` | `0.3` | Temperatura para generación de descripciones |

#### Base de Datos

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `DATABASE_URL` | `sqlite:///chatbot.db` | URL de conexión (soporta SQLite, PostgreSQL, MySQL) |

#### Telemetría

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `TELEMETRY_ENDPOINT` | `http://localhost:6006/v1/traces` | Endpoint HTTP para envío de traces a Phoenix |
| `TELEMETRY_UI_URL` | `http://localhost:6006` | URL de la interfaz web de Phoenix |

## 🧠 Memoria Conversacional (Short-Term)

El chatbot implementa un sistema de **memoria a corto plazo** que mantiene el contexto de la conversación entre múltiples preguntas, permitiendo un diálogo natural y coherente.

### Características de la Memoria

- **Persistencia durante la sesión**: El historial se mantiene mientras el chatbot está ejecutándose
- **No persiste entre sesiones**: El historial se elimina completamente cuando se cierra el chatbot o finaliza la sesión
- **Contexto inteligente**: Permite hacer preguntas de seguimiento sin repetir información
- **Límite de tokens configurable**: Gestiona automáticamente el historial para evitar exceder límites
- **Capacidad aproximada**: Con el límite predeterminado de 6000 tokens, se pueden mantener aproximadamente **10-15 intercambios completos** (20-30 mensajes totales entre usuario y bot), dependiendo de la complejidad de las consultas y respuestas

### Configuración de la Memoria

La memoria está controlada por dos parámetros en `src/core/config.py`:

```python
# Activar/desactivar memoria conversacional
REACT_ENABLE_MEMORY = True           # Valor actual: True (activada)

# Límite de tokens para historial de chat
REACT_MEMORY_TOKEN_LIMIT = 6000      # Valor actual: 6000 tokens
                                      # ≈ 10-15 intercambios completos
                                      # ≈ 20-30 mensajes totales (usuario + bot)
```

> **Nota**: Cuando se alcanza el límite de tokens, el sistema elimina automáticamente los mensajes más antiguos para mantener el historial dentro del límite, priorizando las interacciones más recientes.

### Comandos Útiles

```python
# En código Python

#Primero se importamos e inicializamos el chatbot
from src.workflow.workflow import CorporateReActWorkflow
workflow = CorporateReActWorkflow(object_index=object_index)

# Obtener historial actual
history = workflow.get_chat_history()
print(f"Mensajes en memoria: {len(history)}")

# Limpiar memoria manualmente
workflow.reset_memory()
print("Memoria limpiada")

# Verificar si memoria está activa
from src.core.config import REACT_ENABLE_MEMORY
print(f"Memoria activa: {REACT_ENABLE_MEMORY}")
```

## 💾 Base de Datos

### ¿Qué se Almacena?

El chatbot utiliza una base de datos SQL para registrar **todas las interacciones** con fines de análisis, debugging y mejora continua. La tabla `chat_history` almacena:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer | Identificador único autoincremental |
| `session_id` | String(36) | UUID de la sesión del chatbot |
| `timestamp` | DateTime | Momento exacto de la consulta (UTC) |
| `user_input` | Text | Pregunta formulada por el usuario |
| `bot_output` | Text | Respuesta generada por el chatbot |
| `latency_ms` | Integer | Tiempo de respuesta en milisegundos |
| `intent_type` | String(50) | Tipo de intención (CONVERSACIONAL, BUSQUEDA, ANALÍTICA_SIMPLE, ANALÍTICA_DATOS) |
| `sources` | Text (JSON) | Lista de códigos de datasets consultados |
| `tool_results` | Text (JSON) | Resultados completos de las herramientas ejecutadas |
| `agent_stats` | Text (JSON) | Estadísticas de agentes (iteraciones, tools usados) |
| `success` | Boolean | Indica si la operación fue exitosa |
| `error_message` | Text | Mensaje de error si la operación falló |

### Configuración de la Base de datos

#### SQLite (Por Defecto)

```bash
# En .env o configuración por defecto
DATABASE_URL=sqlite:///chatbot.db
```

- **Ventajas**: Sin configuración adicional, para desarrollo
- **Ubicación**: `chatbot.db` en la raíz del proyecto

#### PostgreSQL (Producción Recomendada)

```bash
# En .env
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/chatbot_db
```

#### MySQL

```bash
# En .env
DATABASE_URL=mysql://usuario:contraseña@localhost:3306/chatbot_db
```

### Consultar Logs

Los logs se pueden consultar directamente desde la base de datos:

```bash
# SQLite
sqlite3 chatbot.db "SELECT user_input, bot_output, latency_ms FROM chat_history ORDER BY timestamp DESC LIMIT 10;"

# PostgreSQL
psql -d chatbot_db -c "SELECT user_input, bot_output, latency_ms FROM chat_history ORDER BY timestamp DESC LIMIT 10;"
```

## 📊 Telemetría y Observabilidad con Arize Phoenix

### ¿Qué es Arize Phoenix?

**Arize Phoenix** es una plataforma de observabilidad de código abierto diseñada específicamente para aplicaciones de IA y LLMs. Permite visualizar y analizar en tiempo real lo siguiente:

- **Traces completos**: Flujo de ejecución del workflow ReAct paso a paso
- **Spans**: Duración de cada operación (LLM calls, tool executions, retrieval)
- **Evaluaciones**: Análisis de calidad de respuestas y detección de hallucinations
- **Costos**: Tracking de tokens consumidos por llamada a LLM
- **Errores**: Debugging visual de fallos en el workflow


### Iniciar Phoenix

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto** (`chatbot2026/`)
>
> **⚠️ Prerequisito**: Tener Docker instalado y corriendo

**Paso a paso (telemetría + trazas en Phoenix):**

1) **Activar telemetría** en `.env` (raíz del proyecto):

```bash
ENABLE_TELEMETRY=true
```

2) **Levantar Phoenix** (esto inicia el servidor que recibe traces):
Desde la raiz del proyecto:

```bash
# Terminal 1.
docker compose up
```

3) **Ejecutar el chatbot** y realizar consultas:

```bash
# Terminal 2
pipenv shell
python main.py
```

4) **Ver trazas** en la UI (puerto 6006):

- Abre `http://localhost:6006`
- Ejecuta 1 o más consultas en el chatbot
- Revisa la pestaña **Traces**: debería aparecer 1 trace por consulta

**Detener Phoenix:**
```bash
# Presionar Ctrl+C en la terminal donde corre docker compose
# O en otra terminal:
docker compose down
```

#### Vista de Traces

Visualiza el flujo completo de cada consulta:

```
Consulta: "¿Cuánta carga en 2023?"
├─ prepare (15ms)
├─ classify_intent (850ms)
│  └─ OpenAI.gpt-5.1 (845ms, 120 tokens)
├─ query_splitting (920ms)
│  └─ OpenAI.gpt-5.1 (915ms, 150 tokens)
├─ retrieve_tools (45ms)
│  └─ VectorStoreIndex.query (42ms)
├─ call_tools (1200ms)
│  └─ FunctionAgent.query (1195ms)
│     └─ PandasQueryEngine (1180ms)
└─ final_answer (980ms)
   └─ OpenAI.gpt-5.1 (975ms, 300 tokens)
```

#### Métricas Clave

- **Latencia por etapa**: Identificar cuellos de botella
- **Token usage**: Costos por consulta (input + output tokens)
- **Success rate**: % de consultas exitosas vs fallidas
- **Retrieval quality**: Relevancia de herramientas recuperadas

### Configuración Avanzada

#### Cambiar Puerto de Phoenix

Editar `docker-compose.yml`:
```yaml
services:
  phoenix:
    ports:
      - "8080:6006"  # Cambiar puerto externo
```

Luego actualizar `src/core/config.py`:
```python
TELEMETRY_ENDPOINT = "http://localhost:8080/v1/traces"
TELEMETRY_UI_URL = "http://localhost:8080"
```

#### Persistencia de Datos

Phoenix almacena todos los traces en `phoenix_data/`:
```
phoenix_data/
├── exports/          # Exportaciones manuales
├── inferences/       # Datos de inferencias
└── trace_datasets/   # Traces completos
```

Para limpiar datos antiguos:

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto**

```bash
# Detener Phoenix primero
docker compose down

# Eliminar datos
rm -rf phoenix_data/*

# Reiniciar
docker compose up
```

#### Activar Telemetría

desde .env editar ENABLE_TELEMETRY y dejarlo en true

### Acceso a la UI

Una vez iniciado Phoenix:

1. Abrir navegador en `http://localhost:6006`
2. Ejecutar consultas en el chatbot
3. Los traces aparecerán automáticamente en la UI
4. Navegar por tabs: **Traces**, **Evaluations**, **Datasets**, **Analytics**

## 🧪 Tests

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto** (`chatbot2026/`)

El proyecto incluye un sistema completo de testing para validar el comportamiento del chatbot.

### Test con Golden Dataset (test_poolDS.py)

Evalúa respuestas del chatbot contra un conjunto de preguntas con respuestas esperadas usando evaluación semántica con LLM.

#### Parámetros

| Parámetro | Opcional | Descripción | Ejemplo |
|-----------|-----------|-------------|---------|
| `--dataset` | ❌ No | Ruta al archivo JSON con el dataset de pruebas | `tests/test_consultas.json` |
| `--name` | ✅ Sí | Nombre personalizado para el archivo de reporte (sin extensión) | `mi_experimento` |

#### Uso

```bash
# Dataset por defecto (test_consultas.json)
python tests/test_poolDS.py --dataset tests/test_consultas.json

# Dataset extendido completo
python tests/test_poolDS.py --dataset tests/test_full.json

# Dataset mixto
python tests/test_poolDS.py --dataset tests/test_preguntas_mix.json

# Con nombre personalizado para el reporte
python tests/test_poolDS.py --dataset tests/test_consultas.json --name experimento_gpt5
```

#### ¿Qué hace test_poolDS?

1. **Carga el dataset**: Lee archivo JSON con preguntas y respuestas esperadas
2. **Ejecuta el workflow**: Procesa cada pregunta con el chatbot completo
3. **Evalúa respuestas**: Usa GPT-4o-mini para comparar semánticamente respuesta obtenida vs esperada
4. **Valida fuentes**: Verifica que los datasets consultados sean los correctos
5. **Calcula métricas**: Genera estadísticas de rendimiento, tokens, latencia, accuracy
6. **Genera reportes**: Crea archivos JSON en `logs/` con resultados detallados

⚠️ Se pueden editar los criterios de evaluacion editando los prompts de evaluacion dentro de test_poolDS.py.

#### ¿Qué entrega?

**Archivo de salida**: `logs/test_poolDS_<nombre>_<timestamp>.json` (o `logs/test_poolDS_<timestamp>.json` sin nombre personalizado)

**Estructura del reporte JSON:**

```json
{
  "session": "20260213_145830",
  "timestamp": "2026-02-13T14:58:30",
  "configuraciones_sistema": {S
    "llm_intent_model": "gpt-5.1",
    "llm_agent_model": "gpt-5.1",
    "embedding_model": "text-embedding-3-small",
    ...
  },
  "estadisticas": {
    "total_tests": 10,
    "puntuacion_promedio": 8.5,
    "puntuacion_maxima": 10,
    "puntuacion_minima": 6.0,
    "tests_aprobados": 9,
    "tests_fallidos": 1,
    "tasa_aprobacion": 90.0,
    "datasets_correctos": 8,
    "accuracy_dataset": 80.0,
    "tiempo_total_ejecucion": 125.5,
    "tokens_promedio_total": 3500,
    "latencia_promedio_db_ms": 12500
  },
  "resultados_detallados": [
    {
      "id_consulta": "c001",
      "pregunta": "¿Cuántos contenedores en San Antonio 2023?",
      "respuesta_esperada": "1.2 millones de TEUs",
      "respuesta_obtenida": "En 2023 se movilizaron 1.2M TEUs...",
      "puntuacion": 9.0,
      "aprobado": true,
      "justificacion": "Ambas respuestas coinciden en datos...",
      "datasets_esperados": ["p048_sielp_contenedores"],
      "datasets_usados": ["p048_sielp_contenedores"],
      "dataset_correcto": true,
      "latencia_ms": 12300,
      "tokens_total": 3200,
      "intent_type_db": "ANALÍTICA_DATOS"
    }
  ]
}
```

### Test de Clasificación de Intenciones

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto**

Verifica que la clasificación de intenciones funcione correctamente para las 4 categorías.

**Archivo:** `tests/test_classify_intent.py`

**Ejecutar:**
```bash
python tests/test_classify_intent.py
```

**Tests incluidos:**
- ✅ CONVERSACIONAL: Saludos, despedidas, charla general
- ✅ BÚSQUEDA: Búsqueda de datasets disponibles
- ✅ ANALÍTICA_SIMPLE: Preguntas conceptuales sin datos
- ✅ ANALÍTICA_DATOS: Consultas que requieren acceso a datasets

### Test de Análisis de Datasets

> **📍 Ubicación**: Ejecutar desde la **raíz del proyecto**

Prueba que la herramienta de análisis automático de datasets funcione correctamente, es decir que cargue correctamente el dataset y genere el reporte necesario (esta herramienta es usada por el agente para conocer la estructura de los datos).

**Archivo:** `tests/test_analizar_dataset.py`

**Ejecutar:**
```bash
python tests/test_analizar_dataset.py
```


## 🐛 Troubleshooting

### Problemas de Instalación

**Error: "No module named 'llama_index'"**
```bash
# Con pipenv
pipenv install

# Con pip
pip install -r requirements.txt
```

**Error: "OPENAI_API_KEY not found"**
```bash
# Crear archivo .env desde template
cp .env.example .env

# Editar .env y agregar tu API key
# OPENAI_API_KEY=sk-...
```

**Error: "Python version mismatch"**
```bash
# Verificar versión de Python
python --version  # Debe ser 3.11 o superior

# Con pipenv, especificar versión
pipenv --python 3.13
```

### Problemas de Ejecución

**Error: "ObjectIndex not found" o "storage_tools/ vacío"**
```bash
# Regenerar el índice de herramientas
python rebuild_index.py

# Si persiste, forzar regeneración
rm -rf storage_tools/
python rebuild_index.py
```

**Latencia muy alta (>30 segundos por consulta)**
- Verificar conexión a internet (llamadas a API de OpenAI)
- Considerar cambiar a modelo más rápido en `src/core/config.py`:
  ```python
  LLM_AGENT_MODEL = "gpt-4o-mini"  # Más rápido que gpt-5.1
  ```
- Reducir `MAX_REASONING_ITERATIONS` en `src/core/config.py`

**Respuestas incorrectas o incompletas**
- Verificar que el dataset relevante existe en `json/data/`
- Revisar logs del workflow (si `VERBOSE_WORKFLOW = True`)
- Aumentar `TOOL_RETRIEVAL_TOP_K` para recuperar más herramientas

### Problemas con Phoenix (Telemetría)

**Phoenix UI no se abre (http://localhost:6006)**
```bash
# Verificar que el contenedor esté corriendo
docker ps

# Si no está corriendo, iniciar Phoenix
docker compose up

# En instalaciones antiguas de Docker
docker-compose up
```

**Puerto 6006 en uso**
```bash
# Cambiar puerto en docker-compose.yml
# Editar línea: "6006:6006" → "7007:6006"

# Actualizar src/core/config.py
TELEMETRY_ENDPOINT = "http://localhost:7007/v1/traces"
TELEMETRY_UI_URL = "http://localhost:7007"
```

**Contenedor de Phoenix no inicia**
```bash
# Ver logs del contenedor
docker compose logs phoenix

# Limpiar datos corruptos
docker compose down
rm -rf phoenix_data/*
docker compose up
```

**Traces no aparecen en Phoenix UI**
- Confirmar que `setup_telemetry()` se llama en `main.py`
- Verificar que `TELEMETRY_ENDPOINT` apunte a `http://localhost:6006/v1/traces`
- Revisar logs de Docker: `docker compose logs -f`

### Problemas con Base de Datos

**Error: "Database locked" (SQLite)**
```bash
# SQLite no soporta alta concurrencia
# Solución 1: Cerrar otras conexiones al archivo chatbot.db
# Solución 2: Migrar a PostgreSQL (ver configuración en README)
```

**Error de conexión a PostgreSQL**
```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Verificar credenciales en .env
DATABASE_URL=postgresql://usuario:password@localhost:5432/nombre_db

# Verificar que la base de datos exista
psql -U usuario -c "\l"
```

### Problemas con Tests

**Tests fallan con "Timeout"**
```bash
# Aumentar timeout en src/core/config.py
WORKFLOW_TIMEOUT = 600  # 10 minutos

# O ejecutar test individual para debug
python tests/test_classify_intent.py
```

**Evaluación semántica da scores bajos**
- Normal si la redacción difiere pero el contenido es correcto
- El evaluador LLM (GPT-4o-mini) puede ser conservador
- Revisar manualmente en el reporte HTML



## 📄 Licencia

Este proyecto es parte del **Chatbot Corporativo (Demo)**.

---

**Última actualización**: 2026-02-13
