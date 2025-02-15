from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from opentelemetry.context import get_value

class FakeThreadSpanProcessor(SpanProcessor):
    def __init__(self):
        pass

    def on_start(self, span, parent_context):
        thread_id = get_value("agent_thread_id", parent_context)
        if thread_id is not None:
            span.set_attribute("gen_ai.thread.id", thread_id)

        thread_run_id = get_value("agent_thread_run_id", parent_context)
        if thread_run_id is not None:
            span.set_attribute("gen_ai.thread.run.id", thread_run_id)

        agent_id = get_value("agent_id", parent_context)
        if agent_id is not None:
            span.set_attribute("gen_ai.agent.id", agent_id)

        agent_name = get_value("agent_name", parent_context)
        if agent_name is not None:
            span.set_attribute("gen_ai.agent.name", agent_name)


    def on_end(self, span: ReadableSpan):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        pass