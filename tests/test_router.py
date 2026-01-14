'''
Test para el enrutador (Router) de LifeOS.
Verifica que las decisiones de enrutamiento sean correctas.
'''
from src.crew_orchestrator import CrewOrchestrator

def test_routing():
    '''Prueba el enrutador con varios escenarios de entrada.'''
    orchestrator = CrewOrchestrator()
    scenarios = [
        ("Me quiero fumar un paquete entero", "PADRINO"),
        ("¿Qué puedo cenar que sea sano?", "KITCHEN"),
        ("Hola, buenos días", "PADRINO"), # Default esperado
    ]
    print("\n>>> 🚦 TESTEANDO DISPATCHER (ROUTER)...")
    for message, expected in scenarios:
        print(f"\n📩 Input: '{message}'")
        print("   Thinking...")
        result = orchestrator.route_request(message)
        print(f"   👉 Decisión: {result}")
        if expected in result:
            print("   ✅ CORRECTO")
        else:
            print(f"   ⚠️ DIVERGENCIA (Esperaba {expected})")

if __name__ == "__main__":
    test_routing()
