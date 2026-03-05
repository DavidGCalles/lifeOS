'''
This file defines the LifeOSAgents class factory,
which reads agent configurations from a YAML file
and creates agents with the appropriate tools and
settings.

It supports both standard CrewAI agents and
FastTrackAgents, allowing for flexible execution
modes. The factory also includes logging for
better traceability of agent creation and tool
assignment.
'''

import os
import logging
import yaml
from crewai import Agent
from src.llm_config import llm
from src.tools import TOOL_MAPPING
from src.fast_agents import FastTrackAgent

logger = logging.getLogger(__name__)

class LifeOSAgents:
    '''Factory class to create agents based on YAML configuration.'''
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'agents.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"No se encuentra la configuración en {config_path}")
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def get_agents_summary(self):
        '''Generates a summary of all agents defined in the configuration.'''
        summary_lines = []
        for key, data in self.config.items():
            if not data.get('public', False):
                continue
            line = f"- {key.upper()}: {data['goal']}"
            summary_lines.append(line)
        return "\n".join(summary_lines)

    def get_public_agent_names(self):
        """Returns a list of names of agents marked as public."""
        return [key for key, data in self.config.items() if data.get('public', False)]

    def create_agent(self, agent_key):
        """Factoría: Crea el agente e inyecta herramientas dinámicamente."""
        agent_key = agent_key.lower()
        agent_data = self.config.get(agent_key)
        if not agent_data:
            logger.warning("⚠️ Agente '%s' no encontrado en YAML.", agent_key)
            return None

        # --- LÓGICA DE INYECCIÓN DE HERRAMIENTAS ---
        agent_tools = []
        requested_tools = agent_data.get('tools', [])
        if requested_tools:
            # print(f"   🛠️  Equipando a {agent_key.upper()} con: {requested_tools}")
            for tool_name in requested_tools:
                tool_instance = TOOL_MAPPING.get(tool_name)
                if tool_instance:
                    if isinstance(tool_instance, dict):
                        # Extraemos los valores (las herramientas) del diccionario
                        agent_tools.extend(tool_instance.values())
                    # Herramienta individual
                    else:
                        agent_tools.append(tool_instance)
                else:
                    logger.warning(
                        "   ⚠️  WARN: Herramienta '%s' no existe en el catálogo.",
                        tool_name)

        execution_mode = agent_data.get('execution_mode', 'crew')
        target_model_name = agent_data.get('model_name', 'crewai-proxy')

        agent_params = {
            'role': agent_data['role'],
            'goal': agent_data['goal'],
            'backstory': agent_data['backstory'],
            'tools': agent_tools,
            'llm': llm
        }

        if execution_mode == 'fast':
            logger.info(
                "⚡ Creando FastTrackAgent para %s usando modelo: %s",
                agent_key.upper(), target_model_name)
            # Inyectamos el nombre del modelo específico para el Router (Gemma)
            return FastTrackAgent(**agent_params, model_name=target_model_name)
        else:
            logger.info("🐢 Creando CrewAI Agent para %s", agent_key.upper())
            # Los agentes normales usan el 'llm' global configurado en src/llm_config.py
            agent_params['verbose'] = agent_data.get('verbose', True)
            agent_params['allow_delegation'] = agent_data.get('allow_delegation', False)
            return Agent(**agent_params)
