import sys
import os
import asyncio
from dotenv import load_dotenv

# Asegurar que el path de src es accesible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno (CRÍTICO: LiteLLM necesita GEMINI_API_KEY para funcionar)
load_dotenv()

try:
    from src.utils.llm_router import LiteLLMRouter
except ImportError as e:
    print(f"❌ Error importando src.utils.llm_router: {e}")
    sys.exit(1)

async def test_router_generation():
    print("\n>>> 🧪 TEST: Embedded LiteLLM Router (In-Process)")
    
    try:
        # 1. Inicializar Singleton
        print("   Initializing Router...")
        router = LiteLLMRouter()
        print("✅ Router Initialized.")

        # 2. Definir el modelo a probar
        # Usamos 'crewai-proxy' que es el nombre definido en tu litellm_config.yaml
        # LiteLLM hará load-balancing entre los Gemini definidos bajo ese nombre.
        model_name = "crewai-proxy"

        print(f"⚡ Sending request to embedded model group: '{model_name}'...")
        
        # 3. Llamada asíncrona directa (Fast Track)
        response = await router.acompletion(
            model=model_name,
            messages=[{"role": "user", "content": "Say 'Fast Track Online' in Spanish."}],
            max_tokens=50
        )

        # 4. Verificar salida
        content = response.choices[0].message.content
        print(f"\n   📩 Response received:\n   '{content}'")
        
        assert content is not None
        print("\n✅ TEST PASSED: Received valid response via Embedded Router.")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_router_generation())