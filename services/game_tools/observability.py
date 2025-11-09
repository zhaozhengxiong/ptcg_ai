"""OpenTelemetry instrumentation for Game Tools."""
from __future__ import annotations

import logging
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
    from opentelemetry.metrics import get_meter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from prometheus_client import start_http_server
except ImportError:
    trace = None
    PrometheusMetricReader = None
    GrpcInstrumentorServer = None
    get_meter = None
    MeterProvider = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    start_http_server = None

logger = logging.getLogger(__name__)


def setup_observability(
    service_name: str = "game-tools",
    prometheus_port: int = 9090,
    enable_console_exporter: bool = False,
):
    """Set up OpenTelemetry observability.
    
    Args:
        service_name: Service name for tracing
        prometheus_port: Port for Prometheus metrics endpoint
        enable_console_exporter: Enable console span exporter (for debugging)
    """
    if not trace or not TracerProvider:
        logger.warning("OpenTelemetry 不可用，已禁用可观测性")
        return

    # Set up tracing
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(service_name)

    # Add console exporter if enabled
    if enable_console_exporter and ConsoleSpanExporter and BatchSpanProcessor:
        console_exporter = ConsoleSpanExporter()
        span_processor = BatchSpanProcessor(console_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

    # Set up metrics
    if PrometheusMetricReader and MeterProvider:
        metric_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(metric_reader=metric_reader)
        
        # Start Prometheus metrics server
        if start_http_server:
            try:
                start_http_server(prometheus_port)
                logger.info(f"Prometheus 指标服务器已启动，端口: {prometheus_port}")
            except Exception as e:
                logger.error(f"启动 Prometheus 服务器失败: {e}", exc_info=True)

    # Instrument gRPC
    if GrpcInstrumentorServer:
        try:
            GrpcInstrumentorServer().instrument()
            logger.info("已启用 gRPC 插桩")
        except Exception as e:
            logger.error(f"gRPC 插桩失败: {e}", exc_info=True)

    logger.info(f"可观测性设置完成，服务名称: {service_name}")


def get_tracer(name: Optional[str] = None):
    """Get a tracer instance."""
    if not trace:
        return None
    return trace.get_tracer(name or "game-tools")


def get_meter_instance(name: Optional[str] = None):
    """Get a meter instance."""
    if not get_meter:
        return None
    return get_meter(name or "game-tools")

