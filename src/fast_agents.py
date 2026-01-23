import json
import logging
import asyncio
from typing import List, Optional
from src.utils.tool_converter import convert_tools_to_openai_schema
from src.utils.llm_router import LiteLLMRouter

# Configuración de logs
logger = logging.getLogger(__name__)

class FastTrackAgent:
    """
    Agente ligero y ASÍNCRONO que evita el overhead de CrewAI.
    Utiliza el LiteLLMRouter embebido para inferencia de latencia cero (in-process)
    y envuelve las herramientas síncronas en hilos para no bloquear el loop.
    """
    is_fast_agent = True

    def __init__(self, role: str, goal: str, backstory: str, tools: list = None, verbose: bool = False, model_name: str = "crewai-proxy", **kwargs):
        """
        Args:
            model_name (str): El nombre del grupo de modelos en litellm_config.yaml. 
                              Usa "router-model" para Gemma/Clasificación (Sin Tools)
                              o "crewai-proxy" para Agentes (Con Tools).
        """
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.verbose = verbose
        
        # Conexión al cerebro (Singleton In-Process)
        self.router = LiteLLMRouter()
        
        # Modelo dinámico (inyectado desde YAML o default)
        self.model_name = model_name

        # Pre-conversión de herramientas a esquema OpenAI
        # Si no hay tools, esto se queda en None, lo cual es vital para Gemma.
        self.openai_tools = convert_tools_to_openai_schema(self.tools) if self.tools else None
        self.tool_map = {t.name: t for t in self.tools}

    async def execute(self, user_message: str, context: str = None) -> str:
        """
        Ejecuta el ciclo de pensamiento del agente de forma asíncrona.
        Maneja User -> LLM -> Tool (en hilo) -> LLM -> Respuesta.
        """
        # 1. Construcción del System Prompt REFORZADO
        system_prompt = (
            f"ROLE: {self.role}\n"
            f"GOAL: {self.goal}\n"
            f"BACKSTORY: {self.backstory}\n"
        )
        if self.openai_tools:
            system_prompt += "\nTOOLS: You have access to external tools. USE THEM. Do not guess information if you can use a tool."

        if context:
            system_prompt += f"\nCONTEXT:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        if self.verbose:
            logger.info(f"⚡ ASYNC FAST-TRACK AGENT ({self.role}) STARTING. Model: {self.model_name}")

        import inspect # Importamos aquí para asegurar disponibilidad

        # 2. Bucle de Ejecución (Max 5 turnos)
        for turn in range(5):
            try:
                # A. Llamada al LLM
                response = await self.router.acompletion(
                    model=self.model_name,
                    messages=messages,
                    tools=self.openai_tools,
                    tool_choice="auto" if self.openai_tools else None
                )
                
                msg = response.choices[0].message
                
                # --- FIX CRÍTICO 1: SANITIZACIÓN DE HISTORIAL ---
                # Convertimos el objeto Pydantic a dict puro para evitar errores de 
                # serialización en la siguiente vuelta del bucle.
                msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg.dict()
                messages.append(msg_dict)

                # B. ¿Quiere usar herramientas?
                if msg.tool_calls:
                    if self.verbose:
                        logger.info(f"   🛠️  Agent requests {len(msg.tool_calls)} tool(s)...")

                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        tool_call_id = tool_call.id
                        
                        tool_instance = self.tool_map.get(tool_name)
                        result_content = ""

                        if not tool_instance:
                            result_content = f"Error: Tool '{tool_name}' not found."
                        else:
                            try:
                                args = json.loads(tool_args_str)
                                if self.verbose:
                                    logger.info(f"   👉 Executing {tool_name} with {args}")
                                
                                # --- FIX CRÍTICO 2: EJECUCIÓN HÍBRIDA ROBUSTA ---
                                # Detectamos si es corutina por definición (Class) o por instancia.
                                is_async = inspect.iscoroutinefunction(tool_instance.run) or \
                                           (hasattr(tool_instance, "_run") and inspect.iscoroutinefunction(tool_instance._run))

                                if is_async:
                                    # Async tool: await directo
                                    result_content = await tool_instance.run(**args)
                                else:
                                    # Sync tool: thread
                                    result_content = await asyncio.to_thread(tool_instance.run, **args)
                                
                                # --- PARACAÍDAS DE EMERGENCIA ---
                                # Si por alguna razón devolvió una corutina sin esperar (pasa a veces con wrappers),
                                # la ejecutamos ahora para que no llegue "<coroutine object...>" al LLM.
                                if inspect.iscoroutine(result_content):
                                    result_content = await result_content

                            except Exception as e:
                                error_msg = f"Error executing {tool_name}: {str(e)}"
                                logger.error(error_msg)
                                result_content = error_msg

                        # C. Inyectar resultado
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": str(result_content)
                        })
                    
                    # Continuamos a la siguiente iteración para que el LLM lea el resultado
                    continue 
                
                # Si no hubo tool calls, esta es la respuesta final
                return msg.content or ""

            except Exception as e:
                logger.error(f"❌ Async FastTrack Error: {e}", exc_info=True)
                return f"Error in FastTrack execution: {e}"

        return "Error: Maximum execution turns reached."