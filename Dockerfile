# Dockerfile for the backend
# Imagen de python
FROM python:3.12-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Direcotrio de trabajo dentro del contenedor
WORKDIR /api

# Copiar archivo de requirements.txt
COPY ./requirements.txt /api/requirements.txt

# Instalar dependencias
RUN pip install --no-cache-dir --upgrade -r /api/requirements.txt

# Copiar el resto de la aplicacion
COPY ./app /api/app

# Exponer el puerto de fastapi
EXPOSE 8000

# Comando para arancar la aplicación con el CLI de fastapi
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]