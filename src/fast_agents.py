import os
import json
import logging
from openai import OpenAI
from src.utils.tool_converter import convert_tools_to_openai_schema

# Configuración de logs
logger = logging.getLogger(__name__)

class FastTrackAgent:
    """
    Agente ligero que evita el overhead de CrewAI.
    Se conecta DIRECTAMENTE al proxy local, ignorando el objeto LLM de CrewAI.
    """
    is_fast_agent = True

    def __init__(self, role: str, goal: str, backstory: str, tools: list = None, verbose: bool = False, **kwargs):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.verbose = verbose
        
        # --- CONFIGURACIÓN DIRECTA (Blindaje contra errores de Atributos) ---
        # No usamos self.llm para evitar 'LLM object has no attribute model_name'
        self.model_name = "crewai-proxy"
        
        # Usamos la variable de entorno o el default de Docker
        self.base_url = os.getenv("LITELLM_URL", "http://litellm:4000")
        self.api_key = "sk-fast-agent" # Dummy key para LiteLLM
        
        # Cliente OpenAI Nativo
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        # Pre-conversión de herramientas (Usamos tu función existente)
        self.openai_tools = convert_tools_to_openai_schema(self.tools) if self.tools else None
        self.tool_map = {t.name: t for t in self.tools}

    def execute(self, user_message: str, context: str = None) -> str:
        # 1. Prompt del Sistema
        system_prompt = (
            f"ROLE: {self.role}\n"
            f"GOAL: {self.goal}\n"
            f"BACKSTORY: {self.backstory}\n"
        )
        if context:
            system_prompt += f"\nCONTEXT:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        if self.verbose:
            logger.info(f"⚡ FAST-TRACK AGENT ({self.role}) STARTING...")

        # 2. Bucle de Ejecución (Max 5 turnos)
        for turn in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.openai_tools,
                    tool_choice="auto" if self.openai_tools else None
                )
                
                msg = response.choices[0].message
                messages.append(msg)

                # Si pide herramientas
                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        
                        tool_instance = self.tool_map.get(tool_name)
                        if not tool_instance:
                            result = f"Error: Tool '{tool_name}' not found."
                        else:
                            try:
                                args = json.loads(tool_args_str)
                                # Usamos .run() para aprovechar la validación de Pydantic de CrewAI
                                result = tool_instance.run(**args)
                            except Exception as e:
                                result = f"Error executing {tool_name}: {str(e)}"

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result)
                        })
                    continue # Siguiente vuelta del bucle
                
                return msg.content or ""

            except Exception as e:
                logger.error(f"❌ FastTrack Error: {e}")
                return f"Error in FastTrack execution: {e}"

        return "Error: Maximum execution turns reached."