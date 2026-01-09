from .time_tool import TimeCheckTool
from .calculator_tool import CalculatorTool
from .search_tool import WebSearchTool
from .memory_tool import RememberTool, RecallTool, ForgetTool

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
    # Los siguientes son para mantener compatibilidad, pero se deprecian
    'save_memory': RememberTool(),
    'search_memory': RecallTool(),
    'forget_memory': ForgetTool(),
}