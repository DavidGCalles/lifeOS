# Usar una imagen base de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Copiar los archivos de requisitos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el directorio src completo, manteniendo la estructura
COPY src ./src

EXPOSE 8080

# Comando para ejecutar la aplicación, especificando la ruta correcta
CMD ["python", "main.py"]
