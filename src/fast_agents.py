import json
from openai import OpenAI
from typing import List
from crewai.tools.base_tool import BaseTool
from src.utils.tool_converter import convert_tools_to_openai_schema

class FastTrackAgent:
    """
    A lightweight agent that bypasses CrewAI for faster execution.
    """
    is_fast_agent = True

    def __init__(self, role: str, goal: str, backstory: str, tools: List[BaseTool] = None, llm=None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.llm = llm
        self.client = OpenAI()

    def execute(self, user_message: str, context: str = None) -> str:
        """
        Executes the agent's logic.
        """
        system_prompt = f"{self.role}. {self.backstory}. {self.goal}."
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})
        
        messages.append({"role": "user", "content": user_message})

        while True:
            response = self.client.chat.completions.create(
                model=self.llm.model_name if self.llm else "gpt-4",
                messages=messages,
                tools=convert_tools_to_openai_schema(self.tools) if self.tools else None,
                tool_choice="auto" if self.tools else None
            )
            
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                messages.append(response_message)
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if not tool:
                        raise ValueError(f"Tool '{tool_name}' not found.")
                    
                    tool_result = tool.run(**tool_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": str(tool_result),
                    })
            else:
                return response_message.content

