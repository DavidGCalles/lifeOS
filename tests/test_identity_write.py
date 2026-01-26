import sys
import os
import asyncio
import logging
import uuid
from dotenv import load_dotenv
load_dotenv()
# Path setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.identity_manager import IdentityManager

logging.basicConfig(level=logging.INFO)

async def test_write_capability():
    print("\n>>> 🆔 TEST: IdentityManager Write Capability (Firestore)")

    # Usamos un ID random para no ensuciar tu usuario real si no quieres
    # OJO: Para que funcione, Firestore debe estar activo en docker-compose
    test_id = f"test_user_{uuid.uuid4().hex[:8]}"
    
    print(f"   👤 Usuario de prueba: {test_id}")

    # 1. Crear/Actualizar usuario con un calendar_id ficticio
    fake_email = "test.dummy@gmail.com"
    print(f"   💾 Escribiendo calendar_id='{fake_email}'...")
    
    # Inyectamos también rol y nombre para que no sea un 'Stranger' al leerlo
    success = await IdentityManager.update_user(test_id, {
        "calendar_id": fake_email,
        "name": "Test Dummy",
        "role": "admin" # Para que pase filtros si los hubiera
    })

    if not success:
        print("   ❌ FALLO: No se pudo escribir (¿Está USE_FIRESTORE=true?)")
        return

    print("   ✅ Escritura reportada como exitosa.")

    # 2. Leer inmediatamente para verificar consistencia
    print("   📖 Leyendo usuario de vuelta...")
    user = await IdentityManager.get_user(test_id)

    print(f"   🔍 Recuperado: Nombre='{user.name}', CalendarID='{user.calendar_id}'")

    if user.calendar_id == fake_email:
        print("   🎉 SUCCESS: El dato ha persistido y se ha recuperado correctamente.")
    else:
        print(f"   ❌ FAIL: Dato esperado '{fake_email}', recibido '{user.calendar_id}'")

if __name__ == "__main__":
    # Forzamos la variable por si acaso ejecutas esto fuera de docker sin .env
    # (Aunque idealmente deberías correrlo dentro del container)
    if not os.getenv("USE_FIRESTORE"):
        print("⚠️  ADVERTENCIA: USE_FIRESTORE no detectado en entorno. Puede fallar si no hay credenciales.")
    
    asyncio.run(test_write_capability())