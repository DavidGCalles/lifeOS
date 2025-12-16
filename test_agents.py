'''
Script de test para los agentes personalizados de LifeOS.
Verifica que los agentes "Padrino de Adicciones" y "Kitchen Chief"'''
import sys
import os
from crewai import Crew

# Aseguramos que Python encuentre la carpeta src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Importamos los Agentes (del archivo renombrado) y las Tareas nuevas
    from src.crew_agents import LifeOSAgents
    from src.tasks import LifeOSTasks
    print("✅ Clases importadas correctamente.")
except ImportError as e:
    print(f"❌ Error importando: {e}")
    exit(1)

def test_full_chain():
    '''
    Testea la cadena completa de análisis y respuesta del agente "Padrino de Adicciones".
    Simula un mensaje de usuario con riesgo de recaída y verifica la respuesta final.
    '''
    print("\n>>> 🕵️ TESTEANDO CADENA COMPLETA (Análisis + Respuesta)...")
    # 1. Instanciar
    agents = LifeOSAgents()
    tasks = LifeOSTasks()
    # Usamos al Padrino para el test
    padrino = agents.padrino_agent()
    # 2. Mensaje simulado (Situación de riesgo)
    user_msg = "He tenido un día horrible en el trabajo y creo que me merezco un cigarro."
    print(f"   📩 Input Usuario: '{user_msg}'")
    # 3. Crear las tareas
    # Observa: task1 (análisis) alimenta a task2 (respuesta)
    task1 = tasks.analysis_task(padrino, user_msg)
    task2 = tasks.response_task(padrino)
    # 4. Crear el Crew secuencial
    crew = Crew(
        agents=[padrino],
        tasks=[task1, task2],
        verbose=True
    )
    print("   ⚡ Ejecutando Crew...")
    result = crew.kickoff()
    print("\n   💬 RESULTADO FINAL (Lo que vería el usuario):")
    print(f"   '{result}'")

if __name__ == "__main__":
    test_full_chain()
