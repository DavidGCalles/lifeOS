from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.logging_config import get_logger
logger = get_logger(__name__)

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
            logger.debug("CalculatorTool evaluating: %s", expression)
            # Lista blanca de caracteres para evitar inyecciones de código
            allowed_chars = "0123456789+-*/().% "
            if not all(char in allowed_chars for char in expression):
                logger.warning("CalculatorTool: invalid characters in expression: %s", expression)
                return "Error: Caracteres inválidos. Solo se permite aritmética básica."

            # Eval en sandbox (sin globals ni locals)
            result = eval(expression, {"__builtins__": None}, {})
            logger.debug("CalculatorTool result: %s", result)
            return str(result)
        except Exception as e:
            logger.exception("CalculatorTool error evaluating expression: %s", expression)
            return f"Error calculando '{expression}': {str(e)}"