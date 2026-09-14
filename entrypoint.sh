#!/bin/sh
set -e

# ============================================================
# entrypoint.sh | Se ejecuta cada vez que arranca el contenedor "web"
# IMPORTANTE: este archivo debe guardarse con saltos de línea LF (Unix),
# no CRLF (Windows). Si lo editan con Notepad y lo guardan mal,
# el contenedor va a fallar con un error tipo "bad interpreter".
# Usen VS Code: abajo a la derecha cambiar de CRLF a LF.
# ============================================================

echo ">> Esperando a que la base de datos esté lista..."

# Reintenta la conexión a Postgres hasta que responda
while ! python -c "
import socket
import os

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    host = os.environ.get('POSTGRES_HOST', 'db')
    port = int(os.environ.get('POSTGRES_PORT', 5432))
    s.connect((host, port))
    s.close()
except Exception:
    exit(1)
"; do
    echo ">> Base de datos no disponible todavía, reintentando en 2s..."
    sleep 2
done

echo ">> Base de datos lista. Aplicando migraciones..."

python manage.py migrate --noinput

echo ">> Arrancando servidor..."

exec "$@"