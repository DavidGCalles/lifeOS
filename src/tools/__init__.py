from .time_tool import TimeCheckTool
from .calculator_tool import CalculatorTool
from .search_tool import WebSearchTool
from .memory_tool import RememberTool, RecallTool, ForgetTool
from .profile_tool import SetCalendarIDTool
from .calendar_tool import CalendarListTool

# --- KITS DE HERRAMIENTAS ---
MEMORY_KIT = [
    RememberTool(),
    RecallTool(),
    ForgetTool()
]

# Mapeo oficial: Nombre en YAML -> Instancia de la herramienta
TOOL_MAPPING = {
    'time': TimeCheckTool(),
    'math': CalculatorTool(),
    'search': WebSearchTool(),
    'memory_core': MEMORY_KIT,
    'set_calendar_id': SetCalendarIDTool(),
    'calendar_list': CalendarListTool()
}