'''
Define las tareas especializadas de LifeOS para los agentes.
Cada tarea tiene una descripción clara y un output esperado.
'''
from textwrap import dedent
from crewai import Task

class LifeOSTasks:
    '''
    Clase que define las tareas especializadas de LifeOS.
    '''
    def analysis_task(self, agent, user_message):
        """
        Paso 1: Entender qué demonios quiere el usuario antes de contestar.
        Analiza la intención oculta y el riesgo.
        """
        return Task(
            description=dedent(f"""
                ANALIZA el siguiente mensaje del usuario con visión táctica:
                Mensaje: "{user_message}"
                
                Tu misión es determinar:
                1. INTENCIÓN: ¿Qué busca realmente? (¿Ayuda urgente? ¿Desahogo? ¿Planificación? ¿Sabotaje?).
                2. ESTADO EMOCIONAL: ¿Está ansioso, cabreado, deprimido o motivado?
                3. NIVEL DE RIESGO: ¿Hay peligro de recaída inminente (tabaco) o desastre nutricional?
                
                No respondas al usuario aún. Tu salida debe ser un REPORTE INTERNO breve.
            """),
            expected_output="Reporte estructurado de Intención, Emoción y Riesgo.",
            agent=agent
        )

    def response_task(self, agent):
        """
        Paso 2: Generar la respuesta final usando el análisis previo.
        CrewAI pasará automáticamente el output de la tarea anterior a esta.
        """
        return Task(
            description=dedent("""
                Usando el reporte de análisis anterior, GENERA la respuesta final para el usuario.
                
                Requisitos:
                - Aplica tu PERSONALIDAD (Backstory) al 200%.
                - Si el riesgo es alto, sé contundente (Protocolo Tough Love o Michelin exigente).
                - Si es bajo, mantén el rol pero sé constructivo.
                - Tu respuesta debe ser texto plano listo para enviar por Telegram.
                - NO incluyas 'Role:', 'Backstory:' ni meta-datos en la respuesta final. Solo el mensaje.
            """),
            expected_output="Mensaje de respuesta final para el usuario.",
            agent=agent
        )

    def router_task(self, agent, user_message):
        '''Define la tarea de enrutamiento para decidir qué agente debe actuar.'''
        return Task(
            description=dedent(f"""
                Analiza el mensaje del usuario: "{user_message}"
                
                Decide qué agente debe actuar.
                
                Reglas:
                - Si es sobre fumar, ansiedad, disciplina -> 'PADRINO'
                - Si es sobre comida, hambre, recetas -> 'KITCHEN'
                - Si menciona ambos (ej: "tengo ansiedad por fumar y quiero comer") -> 'AMBOS'
                - Si no tiene sentido o es saludo genérico -> 'PADRINO' (Por defecto es el líder).
                
                Tu respuesta debe ser ÚNICAMENTE una de estas palabras: PADRINO, KITCHEN, AMBOS.
                No añadas puntuación ni explicaciones.
            """),
            expected_output="Una sola palabra: PADRINO, KITCHEN o AMBOS.",
            agent=agent
        )
