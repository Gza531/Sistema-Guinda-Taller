# Base Docker + Django + PostgreSQL — Taller de Programación

Proyecto Django ya generado y funcionando, listo para levantar con Docker y
empezar a desarrollar el sistema de la organización asignada (Práctica
Profesional) sin perder tiempo en la configuración inicial. Ya incluye
Django REST Framework instalado y un endpoint de ejemplo, por si su
organización necesita una API REST.

## Contenido

- `Dockerfile` → define la imagen del contenedor de Django.
- `docker-compose.yml` → levanta dos servicios: `web` (Django) y `db` (Postgres).
- `requirements.txt` → dependencias de Python.
- `entrypoint.sh` → espera a la base de datos, aplica migraciones y arranca el servidor.
- `.env.example` → variables de entorno de ejemplo (copiar como `.env`).
- `manage.py`, `config/` → proyecto Django ya iniciado (`django-admin startproject`).
- `core/` → app de ejemplo con una vista de inicio que confirma que el stack funciona.
- `api/` → app de ejemplo con un endpoint REST (`/api/estado/`), lista para ampliar con los serializers y vistas de su organización.

## Primeros pasos

1. Copien `.env.example` como `.env` y ajusten el nombre de la base de datos y
   usuario según el nombre de su organización (por ejemplo: `sabor_andino_db`).

2. Levanten los contenedores:
   ```
   docker compose up --build
   ```

3. Abran en el navegador:
   ```
   http://localhost:8000
   ```
   Si ven la pantalla "Stack funcionando", Django se conectó correctamente a
   Postgres y ya pueden empezar a trabajar.

4. Prueben también el endpoint de ejemplo de la API REST:
   ```
   http://localhost:8000/api/estado/
   ```
   Debería devolver un JSON simple confirmando que la API funciona.

5. Para crear un superusuario (usuario admin de Django):
   ```
   docker compose exec web python manage.py createsuperuser
   ```
   Después entren a `http://localhost:8000/admin`.

6. Para entrar a una terminal dentro del contenedor (correr comandos de manage.py, instalar algo, etc.):
   ```
   docker compose exec web bash
   ```

7. Para crear una app nueva de Django (por ejemplo, la app principal de su sistema):
   ```
   docker compose exec web python manage.py startapp nombre_app
   ```
   No se olviden de agregarla a `INSTALLED_APPS` en `config/settings.py`.

8. Para crear y aplicar migraciones después de modificar un modelo:
   ```
   docker compose exec web python manage.py makemigrations
   docker compose exec web python manage.py migrate
   ```

9. Para apagar todo:
   ```
   docker compose down
   ```
   (Los datos de la base de datos NO se pierden: quedan en el volumen
   `postgres_data`. Si quieren borrar todo desde cero, usen `docker compose down -v`).

## API REST (Django REST Framework)

El proyecto ya trae `djangorestframework` instalado y configurado
(`rest_framework` está en `INSTALLED_APPS`, con paginación básica en
`REST_FRAMEWORK` dentro de `config/settings.py`). La app `api/` incluye un
endpoint de ejemplo (`EstadoAPIView`) que pueden usar como modelo para los
suyos.

Para agregar un endpoint real sobre un modelo de su organización:

1. Definan el modelo en la app correspondiente (por ejemplo, `Cliente` en una
   app `clientes`).
2. Creen un archivo `serializers.py` en esa app, con una clase
   `ClienteSerializer(serializers.ModelSerializer)`.
3. Creen una vista (por ejemplo, `ClienteListView(generics.ListCreateAPIView)`)
   que use ese serializer.
4. Registren la ruta en `config/urls.py`, agrupada bajo `/api/`, por ejemplo:
   `path('api/clientes/', include('clientes.urls'))`.

## Adaptar a su proyecto

- Cambien `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` en `.env` por
  el nombre de su organización.
- Reemplacen la vista de `core/views.py` y su template por las páginas reales
  de su sistema, o creen apps nuevas para cada módulo (ver paso 7).
- El código del proyecto vive montado en tiempo real: no hace falta
  reconstruir la imagen cada vez que cambian un archivo `.py`, solo si
  cambian `requirements.txt`.
- Si agregan una librería nueva, súmenla a `requirements.txt` y reconstruyan
  con `docker compose up --build`.

## Estructura del proyecto

```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── entrypoint.sh
├── .env.example
├── manage.py
├── config/          # configuración global del proyecto (settings, urls)
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── core/            # app de ejemplo (vista de inicio, reemplazar/ampliar)
│   ├── views.py
│   ├── models.py
│   └── templates/core/home.html
└── api/             # app de ejemplo para la API REST
    ├── views.py
    └── urls.py
```

---
Prof. Lic. Adrián Aguirre | ISDEM | Taller de Programación
