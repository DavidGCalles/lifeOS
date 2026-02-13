
import os
from sentence_transformers import SentenceTransformer

# Define the model name and the desired output directory
model_name = 'intfloat/multilingual-e5-small'
output_path = 'models/e5-small-sanitized'

# Ensure the output directory exists
os.makedirs(output_path, exist_ok=True)

print(f"🚀 Loading model '{model_name}' (Online)...")
# Load the model from Hugging Face
model = SentenceTransformer(model_name)

print(f"💾 Saving sanitized model to '{output_path}'...")
# Save the model to the specified directory
model.save(output_path)

print("✅ Model saved.")

# The original Dockerfile also removed modules.json.
# While this might not be necessary when the model is pre-packaged,
# we'll replicate the behavior for consistency.
modules_file_path = os.path.join(output_path, 'modules.json')
if os.path.exists(modules_file_path):
    print(f"🗑️ Removing '{modules_file_path}' for offline compatibility...")
    os.remove(modules_file_path)
    print("✅ File removed.")
