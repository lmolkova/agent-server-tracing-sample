#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv
load_dotenv()


from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from chat.fake_thread_context_processor import FakeThreadSpanProcessor
from chat.settings import AZMON_CONNECTION_STRING
HTTPXClientInstrumentor().instrument()

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.trace import get_tracer_provider, set_tracer_provider
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry._events import set_event_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._events import EventLoggerProvider
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor, ConsoleLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter, AzureMonitorMetricExporter, AzureMonitorTraceExporter
from azure.core.settings import settings
settings.tracing_implementation = None

def configure_tracing() -> TracerProvider:
    set_tracer_provider(TracerProvider())
    provider = get_tracer_provider()

    #provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    provider.add_span_processor(FakeThreadSpanProcessor())
    #provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    provider.add_span_processor(SimpleSpanProcessor(AzureMonitorTraceExporter(connection_string=AZMON_CONNECTION_STRING)))
    return provider


def configure_logging():
    set_logger_provider(LoggerProvider())
    provider = get_logger_provider()
    #provider.add_log_record_processor(SimpleLogRecordProcessor(OTLPLogExporter()))
    provider.add_log_record_processor(SimpleLogRecordProcessor(AzureMonitorLogExporter(connection_string=AZMON_CONNECTION_STRING)))
    event_provider = EventLoggerProvider()
    set_event_logger_provider(event_provider)
    return (provider, event_provider)

def configure_metrics() -> MeterProvider:
    views = [
        View(
            instrument_name="gen_ai.client.token.usage",
            aggregation=ExplicitBucketHistogramAggregation([1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864]),
        ),
        View(
            instrument_name="gen_ai.client.operation.duration",
            aggregation=ExplicitBucketHistogramAggregation([0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]),
        ),
    ]
    provider = MeterProvider(metric_readers=[
        #PeriodicExportingMetricReader(OTLPMetricExporter()),
        PeriodicExportingMetricReader(AzureMonitorMetricExporter(connection_string=AZMON_CONNECTION_STRING))
    ], views=views)
    set_meter_provider(provider)
    return provider

def main():
    configure_tracing()
    configure_logging()
    configure_metrics()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat.settings")
    DjangoInstrumentor().instrument()
    OpenAIInstrumentor().instrument()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
