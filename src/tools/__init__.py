from .time_tool import TimeCheckTool
from .calculator_tool import CalculatorTool
from .search_tool import WebSearchTool 

# Mapeo oficial: Nombre en YAML -> Instancia de la herramienta
TOOL_MAPPING = {
    'time': TimeCheckTool(),
    'math': CalculatorTool(),
    'search': WebSearchTool()
} 