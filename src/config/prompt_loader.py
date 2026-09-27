"""
Módulo para cargar y formatear ejemplos few-shot desde JSON.

Este módulo proporciona utilidades para:
- Cargar ejemplos few-shot desde few_shot_examples.json
- Formatear ejemplos para incluir en prompts del LLM
- Gestionar diferentes categorías de ejemplos (clasificación, splitting, etc.)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class FewShotPromptLoader:
    """
    Carga y gestiona ejemplos few-shot desde JSON.

    Uso:
        loader = FewShotPromptLoader()

        # Obtener ejemplos formateados para clasificación de intenciones
        intent_examples = loader.format_intent_examples_for_prompt()

        # Obtener ejemplos de query splitting
        splitting_examples = loader.get_splitting_examples(tipo="multi_dataset")

        # Obtener ejemplos de generación de respuestas
        response_examples = loader.format_response_examples_for_prompt()
    """

    def __init__(self, examples_path: Optional[Path] = None):
        """
        Inicializa el loader.

        Args:
            examples_path: Ruta opcional al archivo JSON. Si no se proporciona,
                          usa la ruta por defecto en src/config/few_shot_examples.json
        """
        if examples_path is None:
            config_dir = Path(__file__).parent
            examples_path = config_dir / "few_shot_examples.json"

        self.examples_path = examples_path
        self.examples = self._load_examples()

    def _load_examples(self) -> Dict:
        """Carga el archivo JSON con los ejemplos."""
        try:
            with open(self.examples_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"No se encontró el archivo de ejemplos en: {self.examples_path}"
            )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Error al parsear el archivo JSON: {e}"
            )

    def get_intent_examples(self, category: Optional[str] = None):
        """
        Obtiene ejemplos para clasificación de intenciones.

        Args:
            category: Categoría específica (CONVERSACIONAL, BUSQUEDA,
                     ANALÍTICA_SIMPLE, ANALÍTICA_DATOS). Si es None, retorna todas.

        Returns:
            Dict con ejemplos de la categoría o todas las categorías
        """
        intent_data = self.examples.get("intent_classification", {})
        examples = intent_data.get("examples", {})

        if category:
            return examples.get(category, [])
        return examples

    def get_splitting_examples(self, tipo: Optional[str] = None) -> List[Dict]:
        """
        Obtiene ejemplos para query splitting.

        Args:
            tipo: Tipo de splitting ("simple" o "multi_dataset").
                  Si es None, retorna todos.

        Returns:
            Lista de ejemplos de query splitting
        """
        splitting_data = self.examples.get("query_splitting", {})
        examples = splitting_data.get("examples", [])

        if tipo:
            return [ex for ex in examples if ex.get("tipo") == tipo]
        return examples

    def get_tool_calling_examples(self, tipo_consulta: Optional[str] = None) -> List[Dict]:
        """
        Obtiene ejemplos de llamadas a herramientas (PandasQueryEngine).

        Args:
            tipo_consulta: Tipo específico (ej: "filtro_y_suma", "agrupacion_y_ordenamiento").
                          Si es None, retorna todos.

        Returns:
            Lista de ejemplos de tool calling
        """
        tool_data = self.examples.get("tool_calling", {})
        examples = tool_data.get("examples", [])

        if tipo_consulta:
            return [ex for ex in examples if ex.get("tipo_consulta") == tipo_consulta]
        return examples

    def get_response_examples(self) -> List[Dict]:
        """
        Obtiene ejemplos de generación de respuestas.

        Returns:
            Lista de ejemplos de respuestas bien formateadas
        """
        response_data = self.examples.get("response_generation", {})
        return response_data.get("examples", [])

    def format_intent_examples_for_prompt(self, max_per_category: int = 3) -> str:
        """
        Formatea ejemplos de clasificación de intenciones para incluir en un prompt.

        Args:
            max_per_category: Máximo de ejemplos por categoría a incluir

        Returns:
            String formateado listo para incluir en el prompt del LLM
        """
        examples = self.get_intent_examples()
        formatted = []

        for category, items in examples.items():
            formatted.append(f"\n{category}:")
            for i, item in enumerate(items[:max_per_category], 1):
                pregunta = item.get("pregunta", "")
                justificacion = item.get("justificacion", "")
                formatted.append(f'   {i}. "{pregunta}" → {justificacion}')

        return "\n".join(formatted)

    def format_splitting_examples_for_prompt(self, include_both_types: bool = True) -> str:
        """
        Formatea ejemplos de query splitting para incluir en un prompt.

        Args:
            include_both_types: Si True, incluye ejemplo simple y multi_dataset.
                               Si False, solo incluye multi_dataset.

        Returns:
            String formateado listo para incluir en el prompt del LLM
        """
        examples = self.get_splitting_examples()
        formatted = []


        for i, ex in enumerate(examples, 1):
            formatted.append(f"\nEJEMPLO {i}:")
            formatted.append(f'Pregunta: "{ex.get("pregunta_original", "")}"')
            formatted.append(f'Tipo: {ex.get("tipo", "")}')
            formatted.append(f'Subconsultas:')

            for subq in ex.get("subconsultas", []):
                formatted.append(f'  {subq.get("id")}. {subq.get("texto", "")}')

            formatted.append(f'Razonamiento: {ex.get("razonamiento", "")}')

        return "\n".join(formatted)

    def format_response_examples_for_prompt(self, max_examples: int = 3) -> str:
        """
        Formatea ejemplos de generación de respuestas para incluir en un prompt.

        Args:
            max_examples: Máximo número de ejemplos a incluir

        Returns:
            String formateado listo para incluir en el prompt del LLM
        """
        examples = self.get_response_examples()[:max_examples]
        formatted = []

        for i, ex in enumerate(examples, 1):
            formatted.append(f"\nEJEMPLO {i}:")
            formatted.append(f'Pregunta: "{ex.get("pregunta", "")}"')
            formatted.append(f'Respuesta correcta:\n{ex.get("respuesta_correcta", "")}')

            elementos = ex.get("elementos_clave", [])
            if elementos:
                formatted.append("\nElementos clave:")
                for elemento in elementos[:3]:  # Mostrar solo los 3 primeros
                    formatted.append(f"  • {elemento}")

        return "\n".join(formatted)

    def get_version(self) -> str:
        """Retorna la versión del archivo de ejemplos."""
        return self.examples.get("version", "unknown")

    def get_metadata(self) -> Dict:
        """Retorna metadata sobre uso e integración."""
        return self.examples.get("metadata", {})


# Instancia singleton para uso global
_loader_instance = None


def get_prompt_loader() -> FewShotPromptLoader:
    """
    Retorna una instancia singleton del FewShotPromptLoader.

    Returns:
        FewShotPromptLoader instance
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = FewShotPromptLoader()
    return _loader_instance
