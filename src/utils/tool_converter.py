from crewai.tools.base_tool import BaseTool
from typing import List

def convert_tools_to_openai_schema(tools: List[BaseTool]) -> List[dict]:
    """
    Converts a list of CrewAI tools to the OpenAI function schema.
    """
    schema_list = []
    for tool in tools:
        function_schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if tool.args_schema else {"type": "object", "properties": {}}
            }
        }
        schema_list.append(function_schema)
    return schema_list
