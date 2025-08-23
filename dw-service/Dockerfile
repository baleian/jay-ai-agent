FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .

RUN uv sync

# Expose the application port
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]