#!/usr/bin/env python3
"""
Script para consultar logs del chatbot en la base de datos.
"""

import argparse
import json
from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker
from src.core.database import ChatLog, get_engine
from tabulate import tabulate


def format_json_field(json_str):
    """Formatea campos JSON para mejor legibilidad."""
    if not json_str:
        return "N/A"
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return f"{len(data)} items"
        elif isinstance(data, dict):
            return f"{len(data)} keys"
        return str(data)
    except:
        return str(json_str)[:50]


def query_logs(limit=10, session_id=None):
    """
    Consulta logs de la base de datos.
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Construir query
    query = session.query(ChatLog)

    if session_id:
        query = query.filter(ChatLog.session_id == session_id)
        print(f"\n📊 Logs para sesión: {session_id}")
    else:
        print(f"\n📊 Últimos {limit} logs:")

    # Ordenar por timestamp descendente y limitar
    logs = query.order_by(desc(ChatLog.timestamp)).limit(limit).all()

    if not logs:
        print("\n⚠️  No se encontraron logs")
        session.close()
        return

    # Preparar datos para tabla
    table_data = []
    for log in logs:
        table_data.append([
            log.id,
            log.session_id[:8] + "...",
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.user_input[:40] + "..." if len(log.user_input) > 40 else log.user_input,
            f"{log.latency_ms}ms",
            log.intent_type or "N/A",
            "✅" if log.success else "❌",
            format_json_field(log.sources)
        ])

    # Mostrar tabla
    headers = ["ID", "Session", "Timestamp", "User Input", "Latency", "Intent", "Success", "Sources"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))

    session.close()


def show_log_detail(log_id):
    """
    Muestra detalles completos de un log específico.
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    log = session.query(ChatLog).filter(ChatLog.id == log_id).first()

    if not log:
        print(f"\n⚠️  No se encontró log con ID {log_id}")
        session.close()
        return

    print(f"\n{'='*70}")
    print(f"📝 Log ID: {log.id}")
    print(f"{'='*70}")
    print(f"\n🆔 Session ID: {log.session_id}")
    print(f"🕒 Timestamp: {log.timestamp}")
    print(f"⏱️  Latency: {log.latency_ms}ms")
    print(f"🎯 Intent Type: {log.intent_type}")
    print(f"{'✅ Success' if log.success else '❌ Failed'}")

    if log.error_message:
        print(f"\n⚠️  Error: {log.error_message}")

    print(f"\n👤 User Input:\n   {log.user_input}")
    print(f"\n🤖 Bot Output:\n   {log.bot_output}")

    session.close()


def main():
    parser = argparse.ArgumentParser(description="Consultar logs del chatbot")
    parser.add_argument("--limit", type=int, default=10, help="Número de logs a mostrar (default: 10)")
    parser.add_argument("--session", type=str, help="Filtrar por session_id")
    parser.add_argument("--detail", type=int, help="Mostrar detalles de un log específico (ID)")

    args = parser.parse_args()

    if args.detail:
        show_log_detail(args.detail)
    else:
        query_logs(limit=args.limit, session_id=args.session)


if __name__ == "__main__":
    main()
