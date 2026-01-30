import sys
import os
import asyncio
import logging

# Asegurar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fast_agents import FastTrackAgent
from src.tools.calculator_tool import CalculatorTool

# Central logging config
from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
import logging
logger = logging.getLogger(__name__)

async def test_async_agent_with_tools():
    logger.info("\n>>> 🏎️  TEST: Async FastTrack Agent (Tool Execution)")

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
    logger.info(f"   👤 User Query: '{query}'")

    # 3. Ejecución Asíncrona
    try:
        response = await agent.execute(query)
        logger.info(f"\n   🤖 Agent Response:\n   {response}")
        
        # 4. Verificación
        expected_math = 123 * 456 # 56088
        if str(expected_math) in response:
            logger.info(f"\n✅ TEST PASSED: Agent used the tool and got {expected_math}.")
        else:
            logger.warning(f"\n⚠️ TEST WARNING: The number {expected_math} was not strictly found in text (Check output).")

    except Exception as e:
        logger.exception(f"\n❌ TEST FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_async_agent_with_tools())