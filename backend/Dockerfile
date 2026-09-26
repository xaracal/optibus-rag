FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

COPY app ./app
COPY dataset ./dataset

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
