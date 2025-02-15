import os
from pathlib import Path
from urllib.parse import urlparse
from opentelemetry._events import get_event_logger
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from openai import AzureOpenAI
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import ConnectionType

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "django-insecure-kl^t0c0l42fyt=usm+u(4j2e@v9@6gygw2n%dh%m3x#nr!1*(-"
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "chat.urls"

INSTALLED_APPS = [
   'chat',
   'markdownify',
]

MARKDOWNIFY = {
    'default': {
        'LINKIFY_TEXT': {
            'AUTOLINKS': False
        }
    }
}

SETTINGS_PATH = os.path.normpath(os.path.dirname(__file__))
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(SETTINGS_PATH, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = "chat.wsgi.application"

MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
INDEX_NAME = "hotels-vector2"

AZMON_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
if PROJECT_CONNECTION_STRING:
    _project_client = AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(), conn_str=PROJECT_CONNECTION_STRING
    )
    if not AZMON_CONNECTION_STRING:
        AZMON_CONNECTION_STRING = _project_client.telemetry.get_connection_string()

    OPENAI_CLIENT = _project_client.inference.get_azure_openai_client(api_version="2024-08-01-preview")

    _search_connection = _project_client.connections.get_default(connection_type=ConnectionType.AZURE_AI_SEARCH)

    SEARCH_CLIENT = SearchClient(
        endpoint=_search_connection.endpoint_url,
        index_name=INDEX_NAME,
        credential=DefaultAzureCredential(),
    )

    INDEX_CLIENT = SearchIndexClient(
        endpoint=_search_connection.endpoint_url, credential=DefaultAzureCredential())
else:
    OPENAI_CLIENT = AzureOpenAI(
        openai_api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        openai_api_version="2024-08-01-preview",
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
    SEARCH_CLIENT = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY")),
    )
    INDEX_CLIENT = SearchIndexClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY")),
    )

EVENT_LOGGER = get_event_logger("chat", version="1.0.0")
