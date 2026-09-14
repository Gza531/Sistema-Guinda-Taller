# ============================================================
# Dockerfile base | Proyecto Django - Práctica Profesional II
# ISDEM - Prof. Lic. Adrián Aguirre
# ============================================================

# Imagen base: Python 3.12 en su version "slim" (liviana)
FROM python:3.12-slim

# Evita que Python genere archivos .pyc y que el output se "trabe" en el log
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Dependencias del sistema necesarias para compilar psycopg2 (driver de Postgres)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Copiamos primero solo requirements.txt para aprovechar la cache de Docker:
# si no cambian las dependencias, no se vuelven a instalar en cada build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora copiamos el resto del código del proyecto
COPY . .

# Convertimos el entrypoint a LF y le damos permiso de ejecución
# (protección extra por si alguien lo edita en Windows y quedan CRLF)
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
