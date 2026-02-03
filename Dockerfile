# Usar una imagen base de Python
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Copiar los archivos de requisitos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# En vez de copiar solo src, copiamos TODO el contexto actual (respetando el .dockerignore)
COPY . .
# -------------------

EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["python", "main.py"]