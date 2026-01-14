'''
Orquestador de Crews para LifeOS.
Coordina la ejecución de agentes y tareas según la solicitud del usuario.
'''
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks
from src.utils.session_manager import SessionManager
from src.identity_manager import UserContext 

class CrewOrchestrator:
    def __init__(self, session_manager: SessionManager):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()
        self.session_manager = session_manager

    def _format_identity_context(self, user: UserContext | None) -> str:
        """Helper para formatear la cabecera de identidad."""
        if not user:
            return ""
        
        # Construimos un bloque de texto claro para el LLM
        return (
            f"👤 INTERACTION CONTEXT:\n"
            f"User Name: {user.name}\n"
            f"User Role: {user.role}\n"
            f"User Description: {user.description or 'N/A'}\n"
            f"--------------------------------------------------\n"
        )

    def route_request(self, user_message: str, user: UserContext | None = None) -> str:
        """
        Ejecuta el Router con la lista de agentes dinámica e identidad del usuario.
        """
        # 1. Crear el agente Router
        dispatcher = self.agents.create_agent('dispatcher')
        
        # 2. OBTENER EL MENÚ DINÁMICO (Auto-Discovery)
        options_text = self.agents.get_agents_summary()
        
        # 3. PREPARAR EL PROMPT CON IDENTIDAD
        # Inyectamos quién habla para que el router detecte matices (ej: si habla un niño vs un adulto)
        identity_header = self._format_identity_context(user)
        full_context_message = f"{identity_header}\nIncoming Message: {user_message}"
        
        # 4. Crear la tarea inyectando el menú y el mensaje enriquecido
        routing_task = self.tasks.router_task(dispatcher, full_context_message, options_text)
        
        routing_crew = Crew(
            agents=[dispatcher],
            tasks=[routing_task],
            verbose=True
        )
        decision = routing_crew.kickoff()
        return str(decision).strip().upper()

    def execute_request(self, user_message: str, target_agent_key: str, chat_id: int | None = None, user: UserContext | None = None):
        """
        Ejecuta al agente seleccionado inyectando MEMORIA e IDENTIDAD.
        """
        # target_agent_key viene en MAYÚSCULAS desde el Router (ej: "PADRINO")
        yaml_key = target_agent_key.lower()
        
        print(f"🚀 Orquestador: Activando agente '{yaml_key}' para usuario '{user.name if user else 'Unknown'}'...")

        try:
            agent = self.agents.create_agent(yaml_key)
        except ValueError:
            print(f"⚠️ Agente '{yaml_key}' no encontrado. Fallback a JANE.")
            agent = self.agents.create_agent('jane')

        # --- CONSTRUCCIÓN DEL PROMPT MAESTRO ---
        prompt_parts = []

        # 1. IDENTIDAD (¿Quién eres?)
        if user:
            prompt_parts.append(self._format_identity_context(user))

        # 2. MEMORIA DE SESIÓN (¿Qué dijimos antes?)
        if chat_id:
            context_history = self.session_manager.get_context(chat_id)
            if context_history:
                print(f"🧠 Inyectando memoria contextual para Chat ID {chat_id}")
                prompt_parts.append(f"📜 CHAT HISTORY:\n{context_history}\n")

        # 3. MENSAJE ACTUAL (¿Qué quieres?)
        prompt_parts.append(f"👇 CURRENT REQUEST:\n{user_message}")

        # Unimos todo
        full_message = "\n".join(prompt_parts)

        # --- EJECUCIÓN ---
        task1 = self.tasks.analysis_task(agent, full_message)
        task2 = self.tasks.response_task(agent)
        
        execution_crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            verbose=True
        )
        return execution_crew.kickoff()