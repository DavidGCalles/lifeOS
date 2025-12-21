'''
Define las tareas especializadas de LifeOS para los agentes.
Cada tarea tiene una descripción clara y un output esperado.
'''
import yaml
import os
from crewai import Task

class LifeOSTasks:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'tasks.yaml')
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def analysis_task(self, agent, user_message):
        template = self.config['analysis']['description']
        return Task(
            description=template.format(role=agent.role, user_message=user_message),
            expected_output=self.config['analysis']['expected_output'],
            agent=agent
        )

    def response_task(self, agent):
        template = self.config['response']['description']
        return Task(
            description=template.format(role=agent.role),
            expected_output=self.config['response']['expected_output'],
            agent=agent
        )

    def router_task(self, agent, user_message, agent_options_text):
        """
        Recibe 'agent_options_text' dinámico desde el orquestador.
        """
        template = self.config['router']['description']
        return Task(
            description=template.format(
                user_message=user_message,
                agent_options=agent_options_text # <--- AQUÍ SE INYECTA EL MENÚ
            ),
            expected_output=self.config['router']['expected_output'],
            agent=agent
        )