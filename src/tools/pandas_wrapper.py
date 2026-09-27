"""
Wrapper para PandasQueryEngine que captura el código pandas ejecutado.
Esto permite trackear las consultas ejecutadas para testing y debugging.
"""
import pandas as pd
import warnings
import io
import sys
import re
from llama_index.experimental.query_engine import PandasQueryEngine
from llama_index.core.base.response.schema import Response
from typing import Any


class TrackedPandasQueryEngine(PandasQueryEngine):
    """
    Extiende PandasQueryEngine para capturar el código pandas ejecutado
    y detectar warnings/errores/resultados vacíos.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_pandas_code = None
        self.last_warning = None  # Capturar último warning
        self.has_error = False    # Flag de error
        self.df = kwargs.get('df')  # Guardar referencia al DataFrame

    def _check_empty_result(self, pandas_code: str, result: Any) -> bool:
        """
        Verifica si el resultado es 0 porque el filtro no retornó filas.

        Args:
            pandas_code: Código pandas ejecutado
            result: Resultado de la consulta

        Returns:
            True si detecta que el filtro está vacío, False si es un 0 legítimo
        """
        if self.df is None:
            return False

        # Solo verificar si el resultado es 0 o muy cercano a 0
        try:
            result_num = float(result)
            if result_num != 0.0:
                return False  # No es 0, no hay problema
        except (ValueError, TypeError):
            return False  # No es número, no aplica esta verificación

        # El resultado es 0, verificar si es porque el filtro está vacío
        try:
            # Extraer la parte del filtro (antes de la agregación)
            # Buscar patrones como df[...] o df[(...)
            filter_pattern = r'df\[(.*?)\](?:\[|\.)'
            match = re.search(filter_pattern, pandas_code)

            if match:
                filter_expr = match.group(1)

                # Ejecutar solo el filtro para contar filas
                filtered_df = eval(f"self.df[{filter_expr}]")

                if len(filtered_df) == 0:
                    # El DataFrame filtrado está vacío
                    self.has_error = True
                    self.last_warning = "El filtro aplicado no retornó ninguna fila. Los valores buscados probablemente no existen en el dataset."
                    return True

        except Exception as e:
            # Si hay error al verificar, no marcarlo como error
            # (preferible falso negativo que falso positivo)
            pass

        return False

    def _query(self, query_bundle) -> Response:
        \"\"\"Override _query para capturar el código generado y warnings.\"\"\"
        # Resetear estado
        self.last_warning = None
        self.has_error = False

        # Capturar warnings
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")  # Capturar todos los warnings

            try:
                # Llamar al método original
                response = super()._query(query_bundle)
            except Exception as e:
                # Si hay excepción, marcar como error
                self.has_error = True
                self.last_warning = f"Exception: {str(e)}"
                raise

        # Verificar si hubo warnings
        if warning_list:
            # Guardar el primer warning
            self.last_warning = str(warning_list[0].message)
            # Marcar como error si el warning es de pandas
            if "UserWarning" in str(warning_list[0].category.__name__):
                self.has_error = True

        # Intentar extraer el código pandas de la respuesta
        # PandasQueryEngine incluye el código en response.metadata
        if hasattr(response, 'metadata') and response.metadata:
            self.last_pandas_code = response.metadata.get('pandas_instruction_str', None)

        # Si no está en metadata, intentar extraerlo del response
        if not self.last_pandas_code and hasattr(response, 'response'):
            # El código generado suele estar en el response
            self.last_pandas_code = str(response.response)

        # Verificar si el resultado es 0 por filtro vacío
        if self.last_pandas_code:
            self._check_empty_result(self.last_pandas_code, response.response)

        return response

    async def _aquery(self, query_bundle) -> Response:
        """Override async _aquery para capturar el código generado y warnings."""
        # Resetear estado
        self.last_warning = None
        self.has_error = False

        # Capturar warnings
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")  # Capturar todos los warnings

            try:
                # Llamar al método original
                response = await super()._aquery(query_bundle)
            except Exception as e:
                # Si hay excepción, marcar como error
                self.has_error = True
                self.last_warning = f"Exception: {str(e)}"
                raise

        # Verificar si hubo warnings
        if warning_list:
            # Guardar el primer warning
            self.last_warning = str(warning_list[0].message)
            # Marcar como error si el warning es de pandas
            if "UserWarning" in str(warning_list[0].category.__name__):
                self.has_error = True

        # Intentar extraer el código pandas de la respuesta
        if hasattr(response, 'metadata') and response.metadata:
            self.last_pandas_code = response.metadata.get('pandas_instruction_str', None)

        if not self.last_pandas_code and hasattr(response, 'response'):
            self.last_pandas_code = str(response.response)

        # Verificar si el resultado es 0 por filtro vacío
        if self.last_pandas_code:
            self._check_empty_result(self.last_pandas_code, response.response)

        return response

    def get_last_code(self) -> str:
        """Retorna el último código pandas ejecutado."""
        return self.last_pandas_code or "No disponible"

    def get_last_warning(self) -> str:
        """Retorna el último warning capturado."""
        return self.last_warning or "Sin warnings"

    def had_error(self) -> bool:
        """Retorna True si hubo un error o warning crítico."""
        return self.has_error
