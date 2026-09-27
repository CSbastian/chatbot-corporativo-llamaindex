"""
Módulo de configuración de prompts y ejemplos few-shot.

Este módulo proporciona:
- FewShotPromptLoader: Carga ejemplos few-shot desde JSON
- get_prompt_loader(): Función helper para obtener el loader singleton
"""

from .prompt_loader import FewShotPromptLoader, get_prompt_loader

__all__ = [
    "FewShotPromptLoader",
    "get_prompt_loader"
]
