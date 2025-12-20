'''
Orquestador de Crews para LifeOS.
Coordina la ejecución de agentes y tareas según la solicitud del usuario.
'''
from crewai import Crew
from src.crew_agents import LifeOSAgents
from src.tasks import LifeOSTasks


class CrewOrchestrator:
    '''Orquestador que maneja la lógica de enrutamiento y ejecución de Crews para LifeOS.'''
    def __init__(self):
        self.agents = LifeOSAgents()
        self.tasks = LifeOSTasks()

    def route_request(self, user_message):
        """
        Usa un Crew de un solo agente para decidir quién atiende la petición.
        """
        dispatcher = self.agents.dispatcher_agent()
        routing_task = self.tasks.router_task(dispatcher, user_message)
        # Crew ligera para clasificación rápida
        routing_crew = Crew(
            agents=[dispatcher],
            tasks=[routing_task],
            verbose=True
        )
        decision = routing_crew.kickoff()
        return str(decision).strip().upper()

    def execute_request(self, user_message, target_agent_key):
        """
        Ejecuta el Crew del agente seleccionado.
        """
        active_agents = []
        # Selector de Agentes
        if target_agent_key == 'PADRINO':
            active_agents.append(self.agents.padrino_agent())
        elif target_agent_key == 'KITCHEN':
            active_agents.append(self.agents.kitchen_agent())
        elif target_agent_key == 'JANE':
            active_agents.append(self.agents.jane_agent())
        else:
            # Fallback seguro: Ante la duda, Jane toma el mando.
            print(f"ℹ Destino '{target_agent_key}' no reconocido. Derivando a Jane.")
            active_agents.append(self.agents.jane_agent())

        # Construcción y ejecución del Crew
        agent = active_agents[0]
        task1 = self.tasks.analysis_task(agent, user_message)
        task2 = self.tasks.response_task(agent)
        execution_crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            verbose=True
        )
        return execution_crew.kickoff()
