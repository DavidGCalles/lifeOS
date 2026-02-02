import json
import logging
import asyncio
import inspect
from typing import Any
from src.utils.tool_converter import convert_tools_to_openai_schema
from src.utils.llm_router import LiteLLMRouter

logger = logging.getLogger(__name__)

class FastTrackAgent:
    """
    Agente ligero y ASÍNCRONO.
    Soporta inputs multimodales (Texto + Imagen) nativamente.
    """
    is_fast_agent = True

    def __init__(self, role: str, goal: str, backstory: str, tools: list[Any] | None = None, verbose: bool = False, model_name: str = "crewai-proxy", **kwargs):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.verbose = verbose
        self.router = LiteLLMRouter()
        self.model_name = model_name
        self.openai_tools = convert_tools_to_openai_schema(self.tools) if self.tools else None
        self.tool_map = {t.name: t for t in self.tools}

    async def execute(self, user_message: str | list[dict[str, Any]], context: str | None = None) -> str:
        """
        Ejecuta el ciclo de pensamiento.
        Args:
            user_message: Puede ser un string (texto plano) o una lista de dicts (OpenAI Multimodal format).
            context: Información adicional (Identidad, Historial) que se inyecta en el System Prompt.
        """
        # 1. Construcción del System Prompt
        system_prompt = (
            f"ROLE: {self.role}\n"
            f"GOAL: {self.goal}\n"
            f"BACKSTORY: {self.backstory}\n"
        )
        if self.openai_tools:
            system_prompt += "\nTOOLS: You have access to external tools. USE THEM."

        # Inyectamos el contexto en el System Prompt para mantener limpio el mensaje del usuario
        if context:
            system_prompt += f"\n\n[RUNTIME CONTEXT]\n{context}"

        # 2. Construcción de mensajes
        # Si user_message es una lista, se pasa tal cual. LiteLLM se encarga del resto.
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        if self.verbose:
            preview = "📸 [Multimodal Payload]" if isinstance(user_message, list) else user_message
            logger.info(f"⚡ ASYNC AGENT ({self.role}): {preview}")

        # 3. Bucle de Ejecución (Max 5 turnos)
        for _ in range(5):
            try:
                response = await self.router.acompletion(
                    model=self.model_name,
                    messages=messages,
                    tools=self.openai_tools,
                    tool_choice="auto" if self.openai_tools else None
                )
                
                msg = response.choices[0].message
                # Pydantic v2 dump
                msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg.dict()
                messages.append(msg_dict)

                if msg.tool_calls:
                    if self.verbose:
                        logger.info(f"   🛠️  Tool Calls: {len(msg.tool_calls)}")

                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        tool_call_id = tool_call.id
                        
                        tool_instance = self.tool_map.get(tool_name)
                        result_content: Any = ""

                        if not tool_instance:
                            result_content = f"Error: Tool '{tool_name}' not found."
                        else:
                            try:
                                args = json.loads(tool_args_str)
                                # Detección robusta de corrutinas
                                is_async = inspect.iscoroutinefunction(tool_instance.run) or \
                                           (hasattr(tool_instance, "_run") and inspect.iscoroutinefunction(tool_instance._run))

                                if is_async:
                                    result_content = await tool_instance.run(**args)
                                else:
                                    result_content = await asyncio.to_thread(tool_instance.run, **args)
                                
                                # Paracaídas por si devuelve corrutina sin esperar
                                if inspect.iscoroutine(result_content):
                                    result_content = await result_content

                            except Exception as e:
                                error_msg = f"Error executing {tool_name}: {str(e)}"
                                logger.error(error_msg)
                                result_content = error_msg

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": str(result_content)
                        })
                    continue 
                
                return msg.content or ""

            except Exception as e:
                logger.error(f"❌ Async Agent Error: {e}", exc_info=True)
                return f"Error: {e}"

        return "Error: Maximum execution turns reached."