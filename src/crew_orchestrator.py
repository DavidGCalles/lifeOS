import asyncio
import json
import re
import logging
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks
from src.utils.session_manager import SessionManager
from src.identity_manager import UserContext 

# Configurar logger local
logger = logging.getLogger(__name__)

class CrewOrchestrator:
    def __init__(self, session_manager: SessionManager):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()
        self.session_manager = session_manager

    def _format_identity_context(self, user: UserContext | None) -> str:
        """Helper para formatear la cabecera de identidad."""
        if not user:
            return ""
        
        return (
            f"👤 INTERACTION CONTEXT:\n"
            f"User Name: {user.name}\n"
            f"User Role: {user.role}\n"
            f"User Description: {user.description or 'N/A'}\n"
            f"--------------------------------------------------\n"
        )

    def _clean_and_extract_json(self, text: str) -> dict | None:
        """
        Intenta extraer un objeto JSON válido de una cadena de texto sucia
        usando expresiones regulares. Compatible con fallbacks 'charlatanes'.
        """
        try:
            # 1. Intentar parseo directo
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Buscar patrón { ... } (incluyendo saltos de línea)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
        return None

    async def route_request(self, user_message: str, user: UserContext | None = None) -> str:
        """
        Ejecuta el Router de forma ASÍNCRONA (Con Regex Extraction).
        """
        dispatcher = self.agents.create_agent('dispatcher')
        options_text = self.agents.get_agents_summary()
        identity_header = self._format_identity_context(user)
        full_context_message = f"{identity_header}\nIncoming Message: {user_message}"

        # --- BRANCHING LOGIC ---
        if getattr(dispatcher, "is_fast_agent", False):
            # FAST TRACK: Await directo + Regex Extraction
            
            logger.info("⚡ Fast-tracking dispatcher (Regex Mode)")
            context = f"Available options: {options_text}"
            
            try:
                # 1. Ejecución Texto Normal
                raw_response = await dispatcher.execute(
                    user_message=full_context_message, 
                    context=context
                )
                
                # 2. Extracción Quirúrgica
                decision_data = self._clean_and_extract_json(raw_response)
                
                if decision_data and "target_agent" in decision_data:
                    target_agent = decision_data["target_agent"].strip().upper()
                    logger.info(f"🎯 Router Decision (JSON): {target_agent}")
                    return target_agent
                
                # 3. Fallback sucio
                raw_upper = raw_response.upper()
                if "PADRINO" in raw_upper: return "PADRINO"
                if "KITCHEN" in raw_upper: return "KITCHEN"
                
                logger.warning(f"⚠️ JSON Extraction failed. Raw: '{raw_response[:50]}...'. Defaulting to JANE.")
                return "JANE"

            except Exception as e:
                logger.error(f"⚠️ Dispatcher error: {e}. Defaulting to JANE.")
                return "JANE"

        else:
            # SLOW TRACK: CrewAI (Legacy)
            print("🐢 Crew-tracking dispatcher")
            routing_task = self.tasks.router_task(dispatcher, full_context_message, options_text)
            routing_crew = Crew(
                agents=[dispatcher],
                tasks=[routing_task],
                verbose=True
            )
            decision = await asyncio.to_thread(routing_crew.kickoff)
            return str(decision).strip().upper()

    async def execute_request(self, user_message: str, target_agent_key: str, chat_id: int | None = None, user: UserContext | None = None):
        """
        Ejecuta al agente seleccionado. Si es Fast, await directo. Si es Crew, thread.
        """
        yaml_key = target_agent_key.lower()
        print(f"🚀 Orquestador: Activando agente '{yaml_key}' para usuario '{user.name if user else 'Unknown'}'...")

        try:
            agent = self.agents.create_agent(yaml_key)
        except ValueError:
            print(f"⚠️ Agente '{yaml_key}' no encontrado. Fallback a JANE.")
            agent = self.agents.create_agent('jane')
        
        if not agent:
             agent = self.agents.create_agent('jane')

        # --- CONSTRUCCIÓN DEL CONTEXTO ---
        context_parts = []
        if user:
            context_parts.append(self._format_identity_context(user))

        if chat_id:
            # UPDATE: Añadido await porque get_context ahora es async (Issue #005)
            context_history = await self.session_manager.get_context(chat_id)
            if context_history:
                print(f"🧠 Inyectando memoria contextual para Chat ID {chat_id}")
                context_parts.append(f"📜 CHAT HISTORY:\n{context_history}\n")

        full_context = "\n".join(context_parts)

        # --- EJECUCIÓN ---
        if getattr(agent, "is_fast_agent", False):
            # FAST TRACK
            print(f"⚡ Fast-tracking {agent.role}")
            return await agent.execute(user_message=user_message, context=full_context)
        else:
            # SLOW TRACK
            print(f"🐢 Crew-tracking {agent.role}")
            full_message_for_crew = f"{full_context}\n👇 CURRENT REQUEST:\n{user_message}"
            
            task1 = self.tasks.analysis_task(agent, full_message_for_crew)
            task2 = self.tasks.response_task(agent)
            
            execution_crew = Crew(
                agents=[agent],
                tasks=[task1, task2],
                verbose=True
            )
            # Bloqueante -> Thread
            return await asyncio.to_thread(execution_crew.kickoff)