# Possible server-side Azure Agents example

Prerequisites:

- Option 1: Azure Foundry project
  - It should be connected to OpenAI deployment. `gpt-4o` and `t-embedding-ada-002` models are used by default
  - Azure Search should be connected to the project and allow Entra ID auth, user should have permissions to create/read indexes
  - Application Insights resource should be connected to the project
- Option 2: Azure Search, Azure OpenAI and Application Insights resources (without the project)

How to run:

1. Install dependencies with `python -m pip install requirements.txt`
2. Set environment variables - see [.env](.env) for the details:
   - `OTEL_SERVICE_NAME` to `agent-service` or any other service name you like
   - `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`.
   - If you want to use models different than `gpt-4o` and `text-embedding-ada-002`, set `AZURE_OPENAI_DEPLOYMENT` and `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
   - If using project - `PROJECT_CONNECTION_STRING` for your project
   - Otherwise set `APPLICATIONINSIGHTS_CONNECTION_STRING`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY` env vars
4. run with `python manage.py runserver 0.0.0.0:8000`
5. open http://localhost:8000/setup once to create index and index hotel info
6. open http://localhost:8000
7. submit your hotel search (e.g. "indoor pool")
9. optionally provide feedback
10. You can check generated telemetry in Azure Foundry UI or in Application Insights resource
