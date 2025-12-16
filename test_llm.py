'''
Docstring for test_llm
'''
try:
    from src.llm_config import llm
    print("✅ Configuración cargada (src/llm_config.py).")
except ImportError as e:
    print(f"❌ Error de importación. Asegúrate de haber creado el archivo src/llm_config.py: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Error en la configuración del LLM: {e}")
    exit(1)

def test_connection():
    '''
    Prueba básica para verificar que el LLM responde.
    '''
    print("\n>>> 🧪 INICIANDO PRUEBA DE CONEXIÓN Y FALLBACK...")
    print(">>> Intentando invocar al modelo primario (o sus reservas)...")
   
    try:
        # Usamos invoke, que es la llamada estándar que usará CrewAI por debajo
        msg = "Hola. Confirma que estás operativo respondiendo solo con la palabra: OPERATIVO."
        response = llm.invoke(msg)      
        print("\n✅ RESPUESTA RECIBIDA:")
        print("----------------------------------------")
        print(f"Contenido: {response.content}")
        print(f"Modelo (metadata): {response.response_metadata.get('model_name', 'Desconocido (Oculto por Fallback wrapper)')}")
        print("----------------------------------------")
        print(">>> ✅ PRUEBA EXITOSA: El cerebro está conectado.")
        
    except Exception as e:
        print("\n❌ ERROR CRÍTICO LLAMANDO AL LLM:")
        print(e)
        print("\nPosibles causas:")
        print("1. API Key inválida en .env")
        print("2. Rate Limit agresivo (Si esto pasa, el fallback debería haber saltado, así que revisa si TODOS los modelos fallaron).")

if __name__ == "__main__":
    test_connection()