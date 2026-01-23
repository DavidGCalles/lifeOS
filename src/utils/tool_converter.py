from crewai.tools.base_tool import BaseTool
from typing import List

def convert_tools_to_openai_schema(tools: List[BaseTool]) -> List[dict]:
    """
    Converts a list of CrewAI tools to the OpenAI function schema.
    Compatible with Pydantic v1 and v2.
    """
    schema_list = []
    for tool in tools:
        # Obtener el esquema de forma segura
        parameters = {"type": "object", "properties": {}}
        
        if tool.args_schema:
            if hasattr(tool.args_schema, 'model_json_schema'):
                # Pydantic v2
                parameters = tool.args_schema.model_json_schema()
            elif hasattr(tool.args_schema, 'schema'):
                # Pydantic v1
                parameters = tool.args_schema.schema()
        
        function_schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": parameters
            }
        }
        schema_list.append(function_schema)
    return schema_list