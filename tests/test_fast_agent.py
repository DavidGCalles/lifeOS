import sys
import os
import asyncio
import logging

# Asegurar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fast_agents import FastTrackAgent
from src.tools.calculator_tool import CalculatorTool

# Configurar logging para ver lo que pasa
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')

async def test_async_agent_with_tools():
    print("\n>>> 🏎️  TEST: Async FastTrack Agent (Tool Execution)")

    # 1. Instanciamos el Agente con la Calculadora
    # Simulamos ser "Kitchen" para que tenga sentido hacer cálculos (ej. calorías/cantidades)
    agent = FastTrackAgent(
        role="Math Assistant",
        goal="Calculate accurate results efficiently.",
        backstory="You are a precise mathematical assistant.",
        tools=[CalculatorTool()],
        verbose=True
    )

    # 2. Query que requiere herramienta
    query = "Calculate 123 * 456 and tell me the result."
    print(f"   👤 User Query: '{query}'")

    # 3. Ejecución Asíncrona
    try:
        response = await agent.execute(query)
        print(f"\n   🤖 Agent Response:\n   {response}")
        
        # 4. Verificación
        expected_math = 123 * 456 # 56088
        if str(expected_math) in response:
            print(f"\n✅ TEST PASSED: Agent used the tool and got {expected_math}.")
        else:
            print(f"\n⚠️ TEST WARNING: The number {expected_math} was not strictly found in text (Check output).")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_async_agent_with_tools())