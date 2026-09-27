#!/usr/bin/env python3
"""
Chatbot del Chatbot Corporativo (Demo)
Entry point principal - Ejecuta el chatbot en modo interactivo.

Uso:
    python main.py
    # o
    .venv/bin/python main.py
"""

if __name__ == "__main__":
    from src.cli.interactive import main
    import asyncio
    
    asyncio.run(main())
