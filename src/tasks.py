'''
Define las tareas especializadas de LifeOS para los agentes.
Cada tarea tiene una descripción clara y un output esperado.
'''
from textwrap import dedent
from crewai import Task

class LifeOSTasks:
    
    def analysis_task(self, agent, user_message):
        """Tarea genérica de análisis."""
        return Task(
            description=dedent(f"""
                ANALIZA el mensaje del usuario con tu lente de ({agent.role}):
                Mensaje: "{user_message}"
                
                Determina:
                1. INTENCIÓN REAL: ¿Qué necesita?
                2. CONTEXTO FAMILIAR: ¿Afecta a David, Natalia o Gabriel?
                3. DATOS CLAVE: Extrae fechas, horas o cantidades.
                
                Output: Reporte interno breve.
            """),
            expected_output="Reporte de análisis táctico.",
            agent=agent
        )

    def response_task(self, agent):
        """Tarea genérica de respuesta."""
        return Task(
            description=dedent("""
                Genera la respuesta final al usuario.
                
                Directrices:
                - Mantén tu PERSONALIDAD (Jane es cálida, Padrino es estoico, Kitchen es eficiente).
                - Sé útil y accionable.
                - Formato limpio para Telegram.
                - Si eres JANE: Usa un tono cercano y protector ("Como jefa de gabinete, sugiero...").
            """),
            expected_output="Respuesta de texto lista para enviar.",
            agent=agent
        )

    def router_task(self, agent, user_message):
        '''Enrutador actualizado con JANE como default.'''
        return Task(
            description=dedent(f"""
                Clasifica el mensaje del usuario: "{user_message}"
                
                Elige el agente más adecuado:
                - PADRINO: Solo para Tabaco, Vicios graves, Disciplina estoica.
                - KITCHEN: Solo para Comida, Recetas, Lista de la compra.
                - JANE: Para TODO lo demás (Agenda, dudas, charla, emociones, coordinación familiar).
                
                Responde SOLO con una palabra clave: PADRINO, KITCHEN o JANE.
            """),
            expected_output="Una sola palabra clave de clasificación.",
            agent=agent
        )