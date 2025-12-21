'''
Docstring for src.crew_agents
'''
import yaml
import os
from crewai import Agent
from src.llm_config import llm

class LifeOSAgents:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        """Carga el YAML de agentes."""
        # Ajusta la ruta según tu estructura de carpetas
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'agents.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"No se encuentra la configuración en {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def get_agents_summary(self):
        """
        AUTO-DISCOVERY: Genera una lista de texto con los agentes disponibles 
        y sus objetivos para dársela al Router.
        Excluye al propio 'dispatcher'.
        """
        summary_lines = []
        for key, data in self.config.items():
            if key == 'dispatcher':
                continue
            # Formato: "- CLAVE: Objetivo..."
            line = f"- {key.upper()}: {data['goal']}"
            summary_lines.append(line)
        
        return "\n".join(summary_lines)

    def create_agent(self, agent_key):
        """Factoría: Crea el agente leyendo sus datos del diccionario cargado."""
        agent_key = agent_key.lower()
        agent_data = self.config.get(agent_key)
        
        if not agent_data:
            raise ValueError(f"Agente '{agent_key}' no definido en agents.yaml")

        # Inyección de Herramientas Específicas
        agent_tools = []

        return Agent(
            role=agent_data['role'],
            goal=agent_data['goal'],
            backstory=agent_data['backstory'],
            verbose=agent_data.get('verbose', True),
            allow_delegation=agent_data.get('allow_delegation', False),
            tools=agent_tools,
            llm=llm
        )