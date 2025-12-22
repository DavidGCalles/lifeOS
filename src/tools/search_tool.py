from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(..., description="The search query string.")

class WebSearchTool(BaseTool):
    name: str = "WebSearchTool"
    description: str = (
        "Useful for searching the internet for current events, facts, news, or specific data. "
        "Use this when you don't know the answer or need real-time info."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        try:
            with DDGS() as ddgs:
                # Extraemos 4 resultados para no saturar el contexto
                results = list(ddgs.text(query, max_results=4))
                
            if not results:
                return "No matching results found on the web."
            
            # Formateo compacto para el LLM
            formatted_results = []
            for r in results:
                title = r.get('title', 'No Title')
                link = r.get('href', '#')
                body = r.get('body', '')
                formatted_results.append(f"- **{title}** ({link}): {body}")
            
            return "\n\n".join(formatted_results)
        except Exception as e:
            return f"Error searching web: {str(e)}"