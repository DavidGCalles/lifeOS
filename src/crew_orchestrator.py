# src/crew_orchestrator.py

import asyncio
import json
import re
import logging
from typing import Any
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks
from src.utils.session_manager import SessionManager
from src.identity_manager import UserContext 

logger = logging.getLogger(__name__)

class CrewOrchestrator:
    def __init__(self, session_manager: SessionManager):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()
        self.session_manager = session_manager

    def _format_identity_context(self, user: UserContext | None) -> str:
        if not user: return ""
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

    async def route_request(self, user_message: str | list[dict[str, Any]], user: UserContext | None = None) -> str:
        """
        Enruta la petición haciendo Hot-Swap de modelo si es necesario.
        """
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
                raw_response = await dispatcher.execute(
                    user_message=user_message, 
                    context=routing_context
                )
                
                # 2. PARSING JSON ESTRICTO
                decision_data = self._clean_and_extract_json(raw_response)
                if decision_data and "target_agent" in decision_data:
                    return str(decision_data["target_agent"]).strip().upper()
                
                # 3. FALLBACK SEGURO (Default -> JANE)
                # Si el modelo no devuelve un JSON claro, NO adivinamos por palabras clave.
                # Preferimos fallar hacia el asistente general (Jane) que enviar "reformar cocina" al cocinero.
                logger.warning(f"⚠️ Router Fallback: No valid JSON detected in '{raw_response[:50]}...'. Defaulting to JANE.")
                return "JANE"

            except Exception as e:
                logger.error(f"⚠️ Router Error (Safety Catch): {e}. Defaulting to JANE.")
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

    async def execute_request(self, 
                              user_message: str | list[dict[str, Any]], 
                              target_agent_key: str, 
                              chat_id: int | None = None, 
                              user: UserContext | None = None, 
                              extra_context: str | None = None) -> Any:
        # ... (sin cambios en execute_request) ...
        yaml_key = target_agent_key.lower()
        logger.info(f"🚀 Executing '{yaml_key}'...")

        agent = self.agents.create_agent(yaml_key) or self.agents.create_agent('jane')

        context_parts: list[str] = []
        if extra_context: context_parts.append(f"🔥 PRIORITY CONTEXT: {extra_context}")
        if user: context_parts.append(self._format_identity_context(user))
        
        if chat_id:
            history = await self.session_manager.get_context(chat_id)
            if history:
                history_str = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history])
                context_parts.append(f"📜 CHAT HISTORY:\n{history_str}")

        full_context = "\n\n".join(context_parts)

        if getattr(agent, "is_fast_agent", False):
            return await agent.execute(user_message=user_message, context=full_context)
        else:
            if isinstance(user_message, list):
                text_content = next((x['text'] for x in user_message if x['type'] == 'text'), "Image Content")
                user_message_str = f"[User sent an image]: {text_content}"
            else:
                user_message_str = user_message
            
            full_message = f"{full_context}\n👇 REQUEST:\n{user_message_str}"
            task1 = self.tasks.analysis_task(agent, full_message)
            task2 = self.tasks.response_task(agent)
            crew = Crew(agents=[agent], tasks=[task1, task2], verbose=True)
            return await asyncio.to_thread(crew.kickoff)