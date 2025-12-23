'''
Docstring for src.crew_agents
'''
# src/crew_agents.py

import yaml
import os
from crewai import Agent
from src.llm_config import llm
# NUEVO: Importamos el mapeo de herramientas
from src.tools import TOOL_MAPPING 

class LifeOSAgents:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'agents.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"No se encuentra la configuración en {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def get_agents_summary(self):
        # ... (código existente igual) ...
        summary_lines = []
        for key, data in self.config.items():
            if key == 'dispatcher':
                continue
            line = f"- {key.upper()}: {data['goal']}"
            summary_lines.append(line)
        return "\n".join(summary_lines)

    def create_agent(self, agent_key):
        """Factoría: Crea el agente e inyecta herramientas dinámicamente."""
        agent_key = agent_key.lower()
        agent_data = self.config.get(agent_key)
        
        if not agent_data:
            # Fallback de seguridad, aunque idealmente debería lanzar error
            print(f"⚠️ Agente '{agent_key}' no encontrado en YAML.")
            return None

        # --- LÓGICA DE INYECCIÓN DE HERRAMIENTAS ---
        agent_tools = []
        requested_tools = agent_data.get('tools', [])
        
        if requested_tools:
            print(f"   🛠️  Equipando a {agent_key.upper()} con: {requested_tools}")
            for tool_name in requested_tools:
                tool_instance = TOOL_MAPPING.get(tool_name)
                if tool_instance:
                    agent_tools.append(tool_instance)
                else:
                    print(f"   ⚠️  WARN: Herramienta '{tool_name}' no existe en el catálogo.")

        return Agent(
            role=agent_data['role'],
            goal=agent_data['goal'],
            backstory=agent_data['backstory'],
            verbose=agent_data.get('verbose', True),
            allow_delegation=agent_data.get('allow_delegation', False),
            tools=agent_tools,
            llm=llm
        )