'''
Orquestador de Crews para LifeOS.
Coordina la ejecución de agentes y tareas según la solicitud del usuario.
'''
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks
from src.utils.session_manager import SessionManager

class CrewOrchestrator:
    def __init__(self):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()

    def route_request(self, user_message):
        """
        Ejecuta el Router con la lista de agentes dinámica.
        """
        # 1. Crear el agente Router
        dispatcher = self.agents.create_agent('dispatcher')
        
        # 2. OBTENER EL MENÚ DINÁMICO (Auto-Discovery)
        options_text = self.agents.get_agents_summary()
        
        # 3. Crear la tarea inyectando el menú
        routing_task = self.tasks.router_task(dispatcher, user_message, options_text)
        
        routing_crew = Crew(
            agents=[dispatcher],
            tasks=[routing_task],
            verbose=True
        )
        decision = routing_crew.kickoff()
        return str(decision).strip().upper()

    def execute_request(self, user_message, target_agent_key, chat_id=None):
        """
        Ejecuta al agente seleccionado.
        """
        # target_agent_key viene en MAYÚSCULAS desde el Router (ej: "PADRINO")
        # Lo pasamos a minúsculas para buscar en el YAML
        yaml_key = target_agent_key.lower()
        
        print(f"🚀 Orquestador: Activando agente '{yaml_key}'...")

        try:
            agent = self.agents.create_agent(yaml_key)
        except ValueError:
            print(f"⚠️ Agente '{yaml_key}' no encontrado. Fallback a JANE.")
            agent = self.agents.create_agent('jane')

        # --- LÓGICA DE INYECCIÓN DE MEMORIA ---
        full_message = user_message
        if chat_id:
            context_history = SessionManager.get_context(chat_id)
            if context_history:
                print(f"🧠 Inyectando memoria contextual para Chat ID {chat_id}")
                # Prependemos el historial al mensaje actual
                full_message = f"{context_history}\n\nUser Current Request: {user_message}"

        task1 = self.tasks.analysis_task(agent, full_message)
        task2 = self.tasks.response_task(agent)
        
        execution_crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            verbose=True
        )
        return execution_crew.kickoff()