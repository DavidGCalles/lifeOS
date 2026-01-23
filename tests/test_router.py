'''
Test para el enrutador (Router) de LifeOS.
Verifica que las decisiones de enrutamiento sean correctas.
'''
import sys
import os
import asyncio

# Asegurar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager

async def test_routing():
    '''Prueba el enrutador ASÍNCRONO.'''
    # Necesitamos un SessionManager dummy aunque no lo usemos mucho aquí
    session_manager = SessionManager()
    orchestrator = CrewOrchestrator(session_manager)
    
    scenarios = [
        ("Me quiero fumar un paquete entero", "PADRINO"),
        ("¿Qué puedo cenar que sea sano?", "KITCHEN"),
        ("Hola, buenos días", "JANE"), # Jane suele ser el default para phatic
        ("Agenda para hoy", "JANE"),
    ]
    
    print("\n>>> 🚦 TESTEANDO DISPATCHER (ASYNC ROUTER)...")
    
    for message, expected in scenarios:
        print(f"\n📩 Input: '{message}'")
        print("   Thinking...")
        
        # AHORA USAMOS AWAIT
        result = await orchestrator.route_request(message)
        
        print(f"   👉 Decisión: {result}")
        
        # Verificación laxa (por si devuelve JANE (CHIEF) en vez de JANE)
        if expected in result:
            print("   ✅ CORRECTO")
        else:
            print(f"   ⚠️ DIVERGENCIA (Esperaba {expected})")

if __name__ == "__main__":
    asyncio.run(test_routing())