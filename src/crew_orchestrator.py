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
        Ejecuta el Crew del agente seleccionado (Análisis -> Respuesta).
        """
        # 1. Seleccionar el agente correcto
        active_agents = []
        if target_agent_key == 'PADRINO':
            active_agents.append(self.agents.padrino_agent())
        elif target_agent_key == 'KITCHEN':
            active_agents.append(self.agents.kitchen_agent())
        else: # AMBOS o Fallback
            # En caso de 'AMBOS', por simplicidad inicial, activamos al Padrino primero
            # (Mejora futura: crear un Crew con los dos)
            print(f"ℹ Modo complejo '{target_agent_key}' detectado. Activando Padrino por defecto.")
            active_agents.append(self.agents.padrino_agent())

        # 2. Construir las tareas para el agente seleccionado
        # Asumimos un solo agente por ahora para mantener la linealidad del chat
        agent = active_agents[0]
        task1 = self.tasks.analysis_task(agent, user_message)
        task2 = self.tasks.response_task(agent)
        # 3. Lanzar el Crew de ejecución
        execution_crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            verbose=True
        )
        return execution_crew.kickoff()
