from fastapi.security import APIKeyHeader

api_key = APIKeyHeader(name="X-API-Key", auto_error=False)
