import base64
import json
import os
from time import sleep
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from httpx import URL

from chat.settings import MODEL, EMBEDDING_MODEL, OPENAI_CLIENT as openai, SEARCH_CLIENT as search_client
from chat.settings import EVENT_LOGGER as logger
from opentelemetry.trace import get_current_span, SpanKind
from opentelemetry._events import Event
from opentelemetry.trace import get_tracer
from urllib.parse import urlparse
from azure.search.documents.models import VectorizedQuery
from opentelemetry.context import set_value, attach, detach, get_current
from chat.setup_search import setup_search, index_hotels

GROUNDED_PROMPT="""
You are a friendly assistant that helps people find hotels.
Answer the query using the sources provided below.

Query: {query}

Sources:
{sources}
"""

QUERY_REWRITE_PROMPT = """
Rewrite the following user query into a clear, specific, and
formal request.
If user query does not contain a location, call the get_user_location tool
to get the user's location.
"""

RERANKER_PROMPT = """
You are an expert search result ranker. Your task is to evaluate the relevance of each hotel to the given query and assign a relevancy score.

For each hotel:
1. Analyze its content in relation to the query.
2. Assign a relevancy score from 0 to 10, where 10 is most relevant.

Be objective and consistent in your evaluations.
"""

tracer = get_tracer(__name__)

def index(request):
    return render(request, 'index.html')

def _generate_id():
    return base64.b64encode(os.urandom(16)).decode("utf-8")

agent_id = f"asst_{_generate_id()}"
agent_name = "hotel search"


@csrf_exempt
def setup(request):
    setup_search()
    index_hotels()
    return HttpResponse("Setup complete")

@csrf_exempt
def search_page(request):
    query = request.POST.get('query')
    #get_current_span().set_attribute("query", query)

    ctx = get_current()
    ctx = set_value("agent_id", agent_id, ctx)
    ctx = set_value("agent_name", agent_name, ctx)
    thread_id = f"thread_{_generate_id()}"
    ctx = set_value("agent_thread_id", thread_id, ctx)
    ctx = set_value("agent_thread_run_id", f"run_{_generate_id()}", ctx)
    token = attach(ctx)
    response = _vector_search_rag(query)
    detach(token)
    response["query"] = query
    response["thread_id"] = thread_id

    return render(request, 'search_page.html', response)

@tracer.start_as_current_span(f"thread_run {agent_name}", kind=SpanKind.SERVER)
def _vector_search_rag(query):
    rewritten_query = _rewrite_query(query)
    embeddings = _get_embeddings(rewritten_query)
    documents = _vector_search(embeddings.data[0].embedding)
    documents_reranked = _rerank_results(query, documents)
    response = openai.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": GROUNDED_PROMPT.format(query=rewritten_query, sources=documents_reranked)
            }
        ],
        temperature=0.5,
        model=MODEL
    )

    get_current_span().set_attribute("gen_ai.thread.run.status", "completed")
    current_ctx = get_current_span().get_span_context()

    metadata = {
        "response_id": response.id,
        "trace_id": current_ctx.trace_id,
        "span_id": current_ctx.span_id,
        "trace_flags": current_ctx.trace_flags,
    }
    return {
        "query": query,
        "search_results":  "\n".join([json.dumps(document) for document in documents]),
        "reranked_results": documents_reranked,
        "metadata": metadata,
        "completion": response.choices[0].message.content
    }

def _emit_document_event(document):
    attributes = {f"document.metadata.{k.lower()}":v for k, v in document.items() if not k.startswith("@")}
    attributes["document.relevance.score"]=document["@search.score"]

    if document["@search.reranker_score"]:
        attributes["azure.search.document.reranker.score"]=document["@search.reranker_score"]
    logger.emit(Event("search.document", body="todo - workaround", attributes=attributes))

def _add_common_search_attributes(search_span, search_endpoint, top_k):
    search_span.set_attribute("db.system.name", "azure.ai.search")

    if search_client._index_name:
        search_span.set_attribute("db.collection.name", search_client._index_name)

    search_span.set_attribute("db.operation.name", "search")
    if search_endpoint.hostname:
        search_span.set_attribute("server.address", search_endpoint.hostname)
    if search_endpoint.port:
        search_span.set_attribute("server.port", search_endpoint.port)

    search_span.set_attribute("db.query.limit", top_k)

@csrf_exempt
def feedback_page(request):
    (score, response_id) = _record_feedback(request.POST.get('feedback'),
                    request.POST.get('response_id'),
                    int(request.POST.get('trace_id', 0)),
                    int(request.POST.get('span_id', 0)))

    return HttpResponse(f"Feedback received: score = {score}, response_id = {response_id}")

@tracer.start_as_current_span("rewrite_query")
def _rewrite_query(query):
    completion = openai.chat.completions.create(
        model=MODEL,
        temperature=0.8,
        messages=[
            {"role": "system", "content": QUERY_REWRITE_PROMPT},
            {"role": "user", "content": query},
        ],
        tools=[ get_user_location_tool_definition()],
    )

    if (completion.choices[0].finish_reason == "tool_calls"):
        tool_call_id = completion.choices[0].message.tool_calls[0].id
        tool_call = get_user_location(tool_call_id)
        completion = openai.chat.completions.create(
                model=MODEL,
                temperature=0.8,
                messages=[
                    {"role": "system", "content": QUERY_REWRITE_PROMPT},
                    {"role": "user", "content": query},
                    {"role": "assistant", "tool_calls": completion.choices[0].message.to_dict()["tool_calls"]},
                    {"role": "tool", "content": tool_call, "tool_call_id": tool_call_id}]
            )

    return completion.choices[0].message.content

@tracer.start_as_current_span(f"embeddings {EMBEDDING_MODEL}", kind=SpanKind.CLIENT)
def _get_embeddings(rewritten_query):
    embedding_span = get_current_span()
    embeddings = openai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=rewritten_query
    )
    embedding_span.set_attribute("gen_ai.system", "openai")
    embedding_span.set_attribute("gen_ai.request.model", EMBEDDING_MODEL)
    embedding_span.set_attribute("gen_ai.request.encoding_formats", "float")

    (host, port) = get_openai_server_address_and_port()
    embedding_span.set_attribute("server.address", host)
    if port and port > 0 and port != 443:
        embedding_span.set_attribute("server.port", port)
    embedding_span.set_attribute("gen_ai.response.model", embeddings.model)
    embedding_span.set_attribute("gen_ai.usage.input_tokens", embeddings.usage.prompt_tokens)

    return embeddings


@tracer.start_as_current_span("rerank_results")
def _rerank_results(query, documents):
    get_current_span().set_attribute("TODO", "we don't have semantics defined")
    formatted_user_message = f"Query: {query}\n\nDocuments:\n{json.dumps(documents, indent=2)}"
    response = openai.chat.completions.create(
        model=MODEL,
        temperature=0.8,
        messages=[
            {"role": "system", "content": RERANKER_PROMPT},
            {"role": "user", "content": formatted_user_message}
        ]
    )

    return response.choices[0].message.content

def _vector_search(embeddings):
    search_results = None
    url = urlparse(search_client._endpoint)
    top_k = 3
    index_name = search_client._index_name
    with tracer.start_as_current_span(f"search {index_name}", kind=SpanKind.CLIENT) as search_span:
        _add_common_search_attributes(search_span, url, top_k)
        search_span.set_attribute("azure.search.query.type", "vector") # hybrid, vector, semantic
        search_results = search_client.search(
            top=top_k,
            search_text="",
            select=["HotelId", "HotelName", "Description", "Address"],
            vector_queries=[VectorizedQuery(vector=embeddings, k_nearest_neighbors=10, fields="DescriptionVector", exhaustive=True)],
        )
        res = list(search_results)
        for document in res:
            _emit_document_event(document)

        search_span.set_attribute("db.response.returned_rows", len(res))
    return res

@tracer.start_as_current_span("execute_tool get_user_location")
def get_user_location(tool_call_id):
    get_current_span().set_attribute("gen_ai.tool.name", "get_user_location")
    get_current_span().set_attribute("gen_ai.tool.call.id", tool_call_id)

    with tracer.start_as_current_span("call weather service", kind=SpanKind.CLIENT) as span:
        sleep(0.01)
    return "Seattle, WA"

def get_current_weather_tool_definition():
    return {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. Boston, MA",
                    },
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    }

def get_user_location_tool_definition():
    return {
        "type": "function",
        "function": {
            "name": "get_user_location",
            "description": "Get the user's location",
            "parameters": {},
        },
    }

def _record_feedback(feedback, response_id, trace_id, span_id):
    score = None
    if (feedback == '+1'):
        score = 1.0
    elif (feedback == '-1'):
        score = -1.0

    logger.emit(Event("gen_ai.evaluation.user_feedback",
                        span_id=span_id,
                        trace_id=trace_id,
                        body={"comment": "something users might provide"},
                        attributes={"gen_ai.response.id": response_id,
                                    "gen_ai.evaluation.score": score}))

    return (score, response_id)


def get_openai_server_address_and_port():
    base_client = getattr(openai, "_client", None)
    base_url = getattr(base_client, "base_url", None)
    if not base_url:
        return

    host = None
    port = -1
    if isinstance(base_url, URL):
        host = base_url.host
        port = base_url.port
    elif isinstance(base_url, str):
        url = urlparse(base_url)
        host = url.hostname
        port = url.port

    return (host, port)