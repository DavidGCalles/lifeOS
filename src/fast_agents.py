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
        logger.info("⚡ Fast Agent execution: role='%s' model=%s input_type=%s", self.role, self.model_name, type(user_message).__name__)
        
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
            logger.debug("📌 Context injected (len=%d)", len(context))

        # 2. Construcción de mensajes
        # Si user_message es una lista, se pasa tal cual. LiteLLM se encarga del resto.
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        if self.verbose:
            preview = "📸 [Multimodal Payload]" if isinstance(user_message, list) else user_message
            logger.info("🎯 Agent Input: %s", preview[:80] if isinstance(preview, str) else preview)

        # 3. Bucle de Ejecución (Max 5 turnos)
        turn = 0
        for turn in range(5):
            logger.debug("🔄 Reasoning turn %d/5 for agent '%s'", turn + 1, self.role)
            try:
                logger.debug("📤 Calling LLM: model=%s tools=%d", self.model_name, len(self.openai_tools) if self.openai_tools else 0)
                response = await self.router.acompletion(
                    model=self.model_name,
                    messages=messages,
                    tools=self.openai_tools,
                    tool_choice="auto" if self.openai_tools else None
                )
                
                msg = response.choices[0].message
                msg_dict = {
                    "role": getattr(msg, "role", "assistant"),
                    "content": getattr(msg, "content", "") or "",
                }
                
                # 2. Si el modelo quiere usar herramientas, guardamos esa intención
                # (Aquí aprovechamos que ya vamos a acceder a tool_calls después)
                if getattr(msg, "tool_calls", None):
                    msg_dict["tool_calls"] = [
                        t.model_dump() if hasattr(t, "model_dump") else t.dict() 
                        for t in msg.tool_calls
                    ]

                # 3. Guardamos en el historial AHORA que está completo
                messages.append(msg_dict)

                if getattr(msg, "tool_calls", None):
                    logger.info("🛠️ Tool invocation detected: %d tool(s) called", len(msg.tool_calls))

                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        tool_call_id = tool_call.id
                        
                        logger.debug("🔧 Executing tool: %s (id=%s)", tool_name, tool_call_id[:8])
                        
                        tool_instance = self.tool_map.get(tool_name)
                        result_content: Any = ""

                        if not tool_instance:
                            result_content = f"Error: Tool '{tool_name}' not found."
                            logger.warning("⚠️ Tool not found: %s", tool_name)
                        else:
                            try:
                                args = json.loads(tool_args_str)
                                logger.debug("📥 Tool args parsed: %s", list(args.keys()))
                                
                                # Detección robusta de corrutinas
                                is_async = inspect.iscoroutinefunction(tool_instance.run) or \
                                           (hasattr(tool_instance, "_run") and inspect.iscoroutinefunction(tool_instance._run))

                                if is_async:
                                    logger.debug("⚡ Running async tool: %s", tool_name)
                                    result_content = await tool_instance.run(**args)
                                else:
                                    logger.debug("🔄 Running sync tool in thread pool: %s", tool_name)
                                    result_content = await asyncio.to_thread(tool_instance.run, **args)
                                
                                logger.debug("✅ Tool completed: %s (result_len=%d)", tool_name, len(str(result_content)))
                                
                                # Paracaídas por si devuelve corrutina sin esperar
                                if inspect.iscoroutine(result_content):
                                    result_content = await result_content

                            except Exception as e:
                                error_msg = f"Error executing {tool_name}: {str(e)}"
                                logger.error("❌ Tool execution failed: %s -> %s", tool_name, str(e), exc_info=True)
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