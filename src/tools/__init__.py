from .time_tool import TimeCheckTool
from .calculator_tool import CalculatorTool
from .search_tool import WebSearchTool
from .memory_tool import RememberTool, RecallTool, ForgetTool
from .profile_tool import SetCalendarIDTool
from .calendar_tool import CalendarListTool, CalendarAddTool, CalendarDeleteTool, CalendarUpdateTool
from .google_drive_tool import DriveSearchTool, DriveReadTool
from .governance_tool import UserGovernanceTool
from .attendee_search_tool import AttendeeSearchTool
# --- KITS DE HERRAMIENTAS ---
MEMORY_KIT = {
    "save_memory": RememberTool(),
    "search_memory": RecallTool(),
    "forget_memory": ForgetTool()
}

CALENDAR_KIT = {
    "set_email": SetCalendarIDTool(),
    "calendar_list": CalendarListTool(),
    "calendar_add": CalendarAddTool(),
    "calendar_remove": CalendarDeleteTool(),
    "calendar_update": CalendarUpdateTool()
}

DRIVE_KIT = {
    "drive_search": DriveSearchTool(),
    "drive_read": DriveReadTool()
}


# Mapeo oficial: Nombre en YAML -> Instancia de la herramienta
TOOL_MAPPING = {
    'time': TimeCheckTool(),
    'math': CalculatorTool(),
    'search': WebSearchTool(),
    'memory_core': MEMORY_KIT,
    'calendar_core': CALENDAR_KIT,
    'drive_core': DRIVE_KIT,
    **MEMORY_KIT,
    **CALENDAR_KIT,
    **DRIVE_KIT,
    'user_governance': UserGovernanceTool(),
    'attendee_search': AttendeeSearchTool()
}