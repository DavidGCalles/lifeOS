'''
Script de test para los agentes personalizados de LifeOS.
Verifica que los agentes "Padrino de Adicciones" y "Kitchen Chief"'''
import sys
import os
from crewai import Task, Crew

try:
    from src.crew_agents import LifeOSAgents
    print("✅ Clase LifeOSAgents importada correctamente.")
except ImportError as e:
    print(f"❌ Error importando agentes: {e}")
    exit(1)

def test_padrino_personality():
    '''Testea la personalidad y respuestas del agente "Padrino de Adicciones".'''
    print("\n>>> 🕵️ TESTEANDO AL PADRINO...")  
    # 1. Instanciar
    agents = LifeOSAgents()
    padrino = agents.padrino_agent()
    # 2. Verificar atributos básicos
    print(f"   Rol: {padrino.role}")
    print(f"   Goal: {padrino.goal}")
    # 3. Prueba de Fuego: ¿Sabe hablar?
    # Creamos una tarea dummy solo para este test
    dummy_task = Task(
        description="El usuario te saluda diciendo 'Hola, quiero fumar'. Responde con TU personalidad en UNA sola frase corta.",
        expected_output="Una frase agresiva-cariñosa disuadiendo al usuario.",
        agent=padrino
    )
    crew = Crew(
        agents=[padrino],
        tasks=[dummy_task],
        verbose=True
    )
    print("   ⚡ Ejecutando interacción de prueba (esto gasta tokens)...")
    result = crew.kickoff()
    print("\n   💬 RESPUESTA DEL PADRINO:")
    print(f"   '{result}'")
    if "fumar" in str(result).lower() or "mierda" in str(result).lower() or "no" in str(result).lower():
        print("✅ EL PADRINO ESTÁ VIVO Y DE MAL HUMOR.")
    else:
        print("⚠️ El Padrino ha respondido, pero verifíca si el tono es correcto.")

def test_kitchen_personality():
    '''Testea la personalidad y respuestas del agente "Kitchen Chief".'''
    print("\n>>> 🧑‍🍳 TESTEANDO AL CHEF...")
    
    agents = LifeOSAgents()
    chef = agents.kitchen_agent()
    
    dummy_task = Task(
        description="El usuario dice 'Tengo hambre y solo hay huevos'. Responde con TU personalidad en UNA frase.",
        expected_output="Una orden culinaria directa.",
        agent=chef
    )
    
    crew = Crew(
        agents=[chef],
        tasks=[dummy_task],
        verbose=True
    )
    
    result = crew.kickoff()
    
    print("\n   💬 RESPUESTA DEL CHEF:")
    print(f"   '{result}'")
    print("✅ EL CHEF ESTÁ OPERATIVO.")

if __name__ == "__main__":
    test_padrino_personality()
    # test_kitchen_personality()
