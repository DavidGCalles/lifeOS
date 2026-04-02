''' Crew Orchestrator for managing and routing tasks within the LifeOS system.
This module defines the CrewOrchestrator class, which is responsible for routing user
requests to the appropriate agents based on the content of the message. It implements
a two-stage routing mechanism: first attempting a zero-shot classification using an NLI
model via the ZeroShotClient, and if that fails, falling back to a more traditional
LLM-based router agent.'''

import asyncio
import json
import re
import logging
import time
from typing import Any
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks
from src.managers.identity_manager import UserContext
from src.memory_gateway import MemoryGateway
from src.schemas.memory import MemoryCategory, MemoryType
from src.utils.zero_shot_client import ZeroShotClient

logger = logging.getLogger(__name__)

class CrewOrchestrator:
    '''Orchestrator for routing user requests to the appropriate agents in LifeOS.'''
    def __init__(self, memory_gateway: MemoryGateway):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()
        self.memory_gateway = memory_gateway
        self.zero_shot_client = ZeroShotClient()

    def _format_identity_context(self, user: UserContext | None) -> str:
        if not user:
            return ""
        return (
            f"👤 USER IDENTITY:\n"
            f"Name: {user.name}\n"
            f"Role: {user.role}\n"
            f"Desc: {user.description or 'N/A'}\n"
        )

    def _clean_and_extract_json(self, text: str) -> dict[str, Any] | None:
        """Intenta extraer y limpiar JSON de la respuesta del LLM."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Regex para encontrar el primer bloque JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            candidate = match.group(0)
            # Limpieza básica de markdown
            candidate = re.sub(r'^```(?:json)?\s*', '', candidate)
            candidate = re.sub(r'\s*```$', '', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Último intento: comillas simples a dobles
                try:
                    return json.loads(candidate.replace("'", '"'))
                except Exception:
                    pass
        return None

    async def _zero_shot_routing(self, user_message: str) -> str | None:
        """
        Intenta enrutar usando clasificación Zero-Shot (rápida).
        Retorna el nombre del agente si la confianza es alta, o None.
        """
        try:
            hipotheses = self.agents.get_zero_shot_hypothesis()
            valid_agents = list(self.agents.config.keys())

            # Run evaluation in a thread to avoid blocking the event loop
            top_agent = await asyncio.to_thread(
                self.zero_shot_client.evaluate_routing,
                user_message,
                hipotheses,
                valid_agents
            )
            return top_agent

        except Exception as e:
            logger.error("❌ Zero-Shot Classification Error: %s", e)
            return None

    async def route_request(self, user_message: str | list[dict[str, Any]],
                            user: UserContext | None = None) -> str:
        """
        Enruta la petición haciendo Hot-Swap de modelo si es necesario.
        """
        start_time = time.time()
        logger.info(
            "🚦 Routing initiated: user=%s message_type=%s",
            user.telegram_id if user else "unknown",
            type(user_message).__name__)
        # --- STAGE 1: Zero-Shot Routing (Text Only) ---
        if isinstance(user_message, str):
            result = await self._zero_shot_routing(user_message)
            if result:
                return result
            else:
                logger.info("Zero-Shot routing failed. Fallback to Classic Router.")

        # --- STAGE 2: Classic Router Fallback ---
        dispatcher = self.agents.create_agent('dispatcher')
        # 1. DETECCIÓN MULTIMODAL
        if isinstance(user_message, list):
            logger.info("👁️ Visual Input detected: Dispatcher transforming to 'vision-model'")
            dispatcher.model_name = "vision-model"
        options_text = self.agents.get_agents_summary()
        identity_header = self._format_identity_context(user)
        routing_context = f"{identity_header}\nAvailable Agents:\n{options_text}"

        if getattr(dispatcher, "is_fast_agent", False):
            logger.info("⚡ Routing (Fast Track)...")
            try:
                exec_start = time.time()
                raw_response = await dispatcher.execute(
                    user_message=user_message,
                    context=routing_context,
                    user_context=user # Pasamos el UserContext al FastTrackAgent
                )
                exec_elapsed = time.time() - exec_start
                logger.info(
                    "📤 Dispatcher responded in %.2fs (len=%d)",
                    exec_elapsed, len(str(raw_response)))
                # 2. PARSING JSON ESTRICTO
                decision_data = self._clean_and_extract_json(raw_response)
                if decision_data and "target_agent" in decision_data:
                    candidate = str(decision_data["target_agent"]).strip().upper()
                    # Validate the decided agent exists in configuration
                    if candidate.lower() in self.agents.config:
                        total_elapsed = time.time() - start_time
                        logger.info(
                            "✅ Router Decision: %s (total_time=%.2fs)",
                            candidate, total_elapsed)
                        return candidate
                    else:
                        logger.warning(
                            "⚠️ Router Decision '%s' not recognized."
                            " Raw response: %s. Defaulting to JANE.",
                            candidate, raw_response[:200])
                        return "JANE"
                # 3. FALLBACK SEGURO (Default -> JANE)
                # Si el modelo no devuelve un JSON claro, NO adivinamos por palabras clave.
                logger.warning("⚠️ Router Fallback: No valid JSON detected."
                               " Defaulting to JANE.")
                return "JANE"
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    "❌ Router Error after %.2fs: %s. Defaulting to JANE.",
                    elapsed, str(e), exc_info=True)
                return "JANE"
        else:
            # Fallback para modo lento (Legacy)
            if isinstance(user_message, list):
                return "JANE"
            full_msg = f"{routing_context}\nIncoming: {user_message}"
            task = self.tasks.router_task(dispatcher, full_msg, options_text)
            crew = Crew(agents=[dispatcher], tasks=[task], verbose=True)
            decision = await asyncio.to_thread(crew.kickoff)
            return str(decision).strip().upper()
    async def run_consolidation_task(self, conversation_history: str, user) -> str:
        '''Ejecuta la tarea de consolidación de memoria usando un agente especializado.'''
        start_time = time.time()
        logger.info("🧠 Memory Consolidation iniciada para %s", user.telegram_id)

        agent = self.agents.create_agent('memory_consolidator')
        # Extraemos los valores literales de tus Enums
        valid_categories = [e.value for e in MemoryCategory]
        valid_types = [e.value for e in MemoryType]

        # Montamos el prompt con inyecciones seguras
        task_template = self.tasks.config['memory_consolidation']['description']
        prompt = task_template.replace('{conversation_history}', conversation_history)
        prompt = prompt.replace('{categories}', str(valid_categories))
        prompt = prompt.replace('{types}', str(valid_types))

        try:
            summary_json_str = await agent.execute(user_message=prompt)
        except Exception as e:
            logger.error("❌ Fallo en LLM durante consolidación: %s", e)
            return "[]" # Devolvemos array vacío en caso de fallo para no romper el parser

        elapsed = time.time() - start_time
        logger.info("✅ Extracción completada en %.2fs.", elapsed)
        return summary_json_str

    async def execute_request(self,
                              user_message: str | list[dict[str, Any]],
                              target_agent_key: str,
                              chat_id: int | None = None,
                              user: UserContext | None = None,
                              extra_context: str | None = None) -> Any:
        '''Ejecuta la petición en el agente objetivo con contexto enriquecido.'''
        start_time = time.time()
        yaml_key = target_agent_key.lower()
        logger.info(
            "🚀 Agent execution starting: agent=%s user=%s chat_id=%s",
            yaml_key, user.telegram_id if user else "unknown", chat_id)

        agent = self.agents.create_agent(yaml_key) or self.agents.create_agent('jane')
        if agent is None:
            logger.error("❌ Agent '%s' not found, fallback failed. Returning error.", yaml_key)
            return "Agent not available"

        context_parts: list[str] = []
        if extra_context:
            context_parts.append(f"🔥 PRIORITY CONTEXT: {extra_context}")
            logger.debug("📌 Extra context injected (len=%d)", len(extra_context))
        if user:
            context_parts.append(self._format_identity_context(user))
        if chat_id and user:
            logger.debug("📚 Fetching working memory for chat_id=%s", chat_id)
            # retrieve only messages visible to this user via gateway
            history = await self.memory_gateway.fetch_working_memory(user, chat_id)
            if history:
                logger.info("📜 Chat history loaded: %d messages", len(history))
                history_str = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history])
                context_parts.append(f"📜 CHAT HISTORY:\n{history_str}")
            else:
                logger.debug("📜 No chat history available")

        full_context = "\n\n".join(context_parts)

        try:
            if getattr(agent, "is_fast_agent", False):
                logger.debug("⚡ Fast Agent execution path")
                exec_start = time.time()
                result = await agent.execute(
                    user_message=user_message,
                    context=full_context,
                    user_context=user
                )
                exec_elapsed = time.time() - exec_start
                logger.info("✅ Fast agent execution complete: %.2fs", exec_elapsed)
                
                # Kill switch detection
                if str(result).strip() == "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY":
                    logger.info("🛑 Orchestrator detected kill switch token. Returning exactly.")
                    return "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY"
                    
                return result
            else:
                logger.info("🔧 Crew Agent execution path (slow)")
                if isinstance(user_message, list):
                    text_content = next(
                        (x['text'] for x in user_message if x['type'] == 'text'),
                        "Image Content")
                    user_message_str = f"[User sent an image]: {text_content}"
                    logger.debug(
                        "📸 Multimodal message detected, extracted text: %s",
                        text_content[:50])
                else:
                    user_message_str = user_message
            full_message = f"{full_context}\n👇 REQUEST:\n{user_message_str}"
            task1 = self.tasks.analysis_task(agent, full_message)
            task2 = self.tasks.response_task(agent)
            crew = Crew(agents=[agent], tasks=[task1, task2], verbose=True)
            result = await asyncio.to_thread(crew.kickoff)
            
            # Kill switch detection for Legacy Path
            if str(result).strip() == "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY":
                logger.info("🛑 Orchestrator detected kill switch token in Legacy Path. Returning exactly.")
                return "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY"
                
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "❌ Error during agent execution after %.2fs: %s",
                elapsed, str(e), exc_info=True)
            return f"Error executing agent: {str(e)}"
