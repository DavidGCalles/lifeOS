from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    expression: str = Field(..., description="Mathematical expression to evaluate (e.g., '200 * 0.15 + 30').")

class CalculatorTool(BaseTool):
    name: str = "CalculatorTool"
    description: str = (
        "Useful for performing mathematical calculations. "
        "Input must be a string expression. Supports +, -, *, /, %, ()."
    )
    args_schema: type[BaseModel] = CalculatorInput

    def _run(self, expression: str) -> str:
        try:
            # Lista blanca de caracteres para evitar inyecciones de código
            allowed_chars = "0123456789+-*/().% "
            if not all(char in allowed_chars for char in expression):
                return "Error: Caracteres inválidos. Solo se permite aritmética básica."

            # Eval en sandbox (sin globals ni locals)
            result = eval(expression, {"__builtins__": None}, {})
            return str(result)
        except Exception as e:
            return f"Error calculando '{expression}': {str(e)}"