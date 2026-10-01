# Fairfield city-web MCP server (read-only access to fairfield.ca.gov and eScribe).
# Built on a networked machine (the Spark), then moved to the Mac with docker save/load:
# nothing in the running stack can pull or install.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY server.py .

RUN useradd --system --uid 10001 cityweb && mkdir -p /logs && chown cityweb /logs
USER cityweb
EXPOSE 8000
CMD ["python", "server.py"]
