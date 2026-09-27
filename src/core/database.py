"""
Gestión de base de datos para logging de interacciones del chatbot.

Este módulo proporciona funcionalidad completa para almacenar logs de chat
en una base de datos SQL (SQLite por defecto, escalable a PostgreSQL/MySQL).
"""

import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.core.config import DATABASE_URL, LOGS_DIR

Base = declarative_base()


class ChatLog(Base):
    """
    Modelo para almacenar logs completos de interacciones del chatbot.

    Campos:
        id: Identificador único autoincremental
        session_id: UUID de la sesión del chatbot (un workflow instance)
        timestamp: Momento exacto de la consulta (UTC)
        user_input: Pregunta del usuario
        bot_output: Respuesta generada por el chatbot
        latency_ms: Latencia de respuesta en milisegundos
        intent_type: Tipo de intención clasificada (CONVERSACIONAL, BUSQUEDA, ANALÍTICA_SIMPLE, ANALÍTICA_DATOS)
        sources: JSON con lista de códigos de datasets consultados
        tool_results: JSON con resultados completos de herramientas ejecutadas
        agent_stats: JSON con estadísticas de agentes (iteraciones, tools usados, etc.)
        success: Indica si la operación fue exitosa
        error_message: Mensaje de error si la operación falló
    """
    __tablename__ = 'chat_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_input = Column(Text, nullable=False)
    bot_output = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False)

    # Campos de debugging enriquecido
    intent_type = Column(String(50), nullable=True)
    sources = Column(Text, nullable=True)  # JSON array
    tool_results = Column(Text, nullable=True)  # JSON completo
    agent_stats = Column(Text, nullable=True)  # JSON
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)


def get_engine():
    """
    Obtiene el engine de base de datos desde la configuración.

    Soporta múltiples backends:
    - SQLite (default): sqlite:///./logs/chatbot.db
    - PostgreSQL: postgresql://user:password@host:port/db
    - MySQL: mysql://user:password@host:port/db

    Returns:
        Engine de SQLAlchemy configurado
    """
    db_url = DATABASE_URL

    # Asegurar que el directorio logs/ existe para SQLite
    if db_url.startswith("sqlite"):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    return create_engine(db_url, echo=False)


def init_db():
    """
    Inicializa la base de datos.

    - Crea todas las tablas si no existen
    - Retorna una sesión de SQLAlchemy

    Returns:
        Sesión de SQLAlchemy configurada
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def log_chat_interaction(
    session_id: str,
    user_input: str,
    bot_output: str,
    latency_ms: int,
    intent_type: str = None,
    sources: list = None,
    tool_results: list = None,
    agent_stats: dict = None,
    success: bool = True,
    error_message: str = None
):
    """
    Guarda una interacción de chat en la base de datos.

    Esta función tiene manejo robusto de errores: NO interrumpe el workflow
    si falla el logging, solo imprime una advertencia.

    Args:
        session_id: UUID de la sesión de chatbot (generado en workflow.__init__)
        user_input: Pregunta del usuario
        bot_output: Respuesta generada por el chatbot
        latency_ms: Latencia en milisegundos (tiempo desde prepare hasta final_answer)
        intent_type: Tipo de intención clasificada (opcional)
        sources: Lista de códigos de datasets consultados (opcional)
        tool_results: Resultados completos de herramientas ejecutadas (opcional)
        agent_stats: Estadísticas de agentes (optional)
        success: Si la operación fue exitosa (default: True)
        error_message: Mensaje de error si la operación falló (opcional)

    Examples:
        >>> log_chat_interaction(
        ...     session_id="a1b2c3d4-...",
        ...     user_input="¿Cuánta carga en 2023?",
        ...     bot_output="En 2023 se movilizaron...",
        ...     latency_ms=3450,
        ...     intent_type="ANALÍTICA_DATOS",
        ...     sources=["c018_carga_puertos"],
        ...     success=True
        ... )
        💾 Log guardado (ID: 1, latencia: 3450ms)
    """
    try:
        session = init_db()

        log_entry = ChatLog(
            session_id=session_id,
            timestamp=datetime.utcnow(),
            user_input=user_input,
            bot_output=bot_output,
            latency_ms=latency_ms,
            intent_type=intent_type,
            sources=json.dumps(sources, ensure_ascii=False) if sources else None,
            tool_results=json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
            agent_stats=json.dumps(agent_stats, ensure_ascii=False) if agent_stats else None,
            success=success,
            error_message=error_message
        )

        session.add(log_entry)
        session.commit()

        # Obtener el ID ANTES de cerrar la sesión
        log_id = log_entry.id

        session.close()

        print(f"💾 Log guardado (ID: {log_id}, latencia: {latency_ms}ms)")

    except Exception as e:
        print(f"⚠️  Error guardando log en DB: {str(e)}")
        # NO propagamos la excepción para no interrumpir el workflow
