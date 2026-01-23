import sys
import os
import asyncio
import logging

# Asegurar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import UserContext, UserRole

# Configurar logging para ver errores si ocurren
logging.basicConfig(level=logging.INFO)

async def test_async_json_routing():
    print("\n>>> 🚦 TEST: Async Router (JSON Mode Validation)")
    
    # Setup mínimo
    session_manager = SessionManager()
    orchestrator = CrewOrchestrator(session_manager)
    
    # Usuario Dummy
    user = UserContext(telegram_id="999", name="TestUser", role=UserRole.ADMIN)

    test_cases = [
        # (Input, Expected Agent)
        ("Quiero fumar un cigarro ahora mismo", "PADRINO"),
        ("Tengo hambre, qué hay en la nevera?", "KITCHEN"),
        ("Pon una reunión mañana a las 10", "JANE"), 
        ("Hola", "JANE"),
        ("sdfkjhsdfkjh", "JANE"), # Garbage input check (Fallback or Jane)
    ]

    for message, expected in test_cases:
        print(f"\n📨 Input: '{message}'")
        
        # Medir tiempo aprox (aunque es integración, no benchmark riguroso)
        start_time = asyncio.get_event_loop().time()
        
        result = await orchestrator.route_request(message, user)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Verificación
        print(f"   👉 Result: {result} (Time: {elapsed:.2f}s)")
        
        if result == expected:
            print("   ✅ PASS")
        else:
            print(f"   ❌ FAIL (Expected {expected})")

if __name__ == "__main__":
    asyncio.run(test_async_json_routing())