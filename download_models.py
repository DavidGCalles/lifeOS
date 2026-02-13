import os
from huggingface_hub import snapshot_download

# Definimos la ruta de destino dentro de tu repo
model_name = "intfloat/multilingual-e5-small"
local_dir = "./model_cache"

print(f"🚀 Iniciando descarga de {model_name} en {local_dir}...")

# Descargamos el snapshot completo del modelo
snapshot_download(
    repo_id=model_name,
    local_dir=local_dir,
    local_dir_use_symlinks=False, # Importante para que Docker pueda copiar archivos reales
    ignore_patterns=["*.msgpack", "*.h5", "*.ot"] # Ahorramos espacio ignorando formatos que no usamos
)

print(f"✅ Descarga completada. Ahora tienes el modelo en la carpeta {local_dir}")