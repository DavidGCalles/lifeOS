from datetime import datetime
import pytz 
from crewai.tools import BaseTool

class TimeCheckTool(BaseTool):
    name: str = "TimeCheckTool"
    description: str = (
        "Useful for getting the current local date, time, and day of the week in Madrid/Spain. "
        "Use this BEFORE scheduling, checking agenda, or asking about 'today'."
    )

    def _run(self) -> str:
        # Forzamos Timezone de Madrid
        tz = pytz.timezone('Europe/Madrid')
        now = datetime.now(tz)
        
        # Mapeo manual para evitar problemas de locale en Docker Alpine/Slim
        days_map = {
            "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
            "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
        }
        day_en = now.strftime("%A")
        day_es = days_map.get(day_en, day_en)
        
        return now.strftime(f"{day_es}, %Y-%m-%d %H:%M:%S %Z")