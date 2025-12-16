import logging
import google.generativeai as genai
from src.agents.padrino_agent import PadrinoAgent
from src.agents.kitchen_chief_agent import KitchenChiefAgent
from src.prompts.prompts import ORCHESTRATOR_PROMPT

class OrchestratorAgent:
    def __init__(self, api_key: str):
        self.padrino_agent = PadrinoAgent(api_key)
        self.kitchen_chief_agent = KitchenChiefAgent(api_key)
        genai.configure(api_key=api_key)
        self.classifier_model = genai.GenerativeModel(model_name='gemma-3-4b-it')


    def route(self, chat_id: int, user_input: str) -> tuple[str, str, str]:
        # 1. Clasificar el prompt del usuario
        prompt = ORCHESTRATOR_PROMPT.format(user_input=user_input)
        response = self.classifier_model.generate_content(prompt)
        
        # 2. Decidir a qué agente enrutar
        agent_name = response.text.strip().upper()
        if "PADRINO" in agent_name:
            return self.padrino_agent.generate_response(chat_id, user_input)
        elif "KITCHEN" in agent_name:
            return self.kitchen_chief_agent.generate_response(chat_id, user_input)
        else:
            # Fallback por si el clasificador no da una respuesta clara
            logging.warning(f"Clasificador dudoso. Respuesta: '{agent_name}'. Usando Padrino por defecto.")
            return self.padrino_agent.generate_response(chat_id, user_input)

    def start_chat(self, chat_id: int):
        """Limpia el historial de conversación para un chat específico en todos los agentes."""
        self.padrino_agent.clear_history(chat_id)
        self.kitchen_chief_agent.clear_history(chat_id)

