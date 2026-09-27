"""
Configuración de telemetría para el chatbot.
Configura OpenTelemetry con Phoenix para trazabilidad completa.
"""

from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from src.core.config import TELEMETRY_ENDPOINT


def setup_telemetry():
    """
    Configura la telemetría con Phoenix usando OpenTelemetry.
    
    Debe llamarse UNA VEZ al inicio de la aplicación antes de usar
    cualquier componente de LlamaIndex.
    """
    tracer_provider = TracerProvider()
    span_processor = SimpleSpanProcessor(
        OTLPSpanExporter(endpoint=TELEMETRY_ENDPOINT)
    )
    tracer_provider.add_span_processor(span_processor)
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
