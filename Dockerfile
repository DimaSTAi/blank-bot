FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для reportlab, weasyprint, pypdf и шрифтов
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app ./app

# Убедимся, что папки для данных и шрифтов существуют
RUN mkdir -p /app/app/data /app/app/static/fonts

CMD ["python", "main.py"]
