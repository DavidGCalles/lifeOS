'''
Docstring for src.llm_config
'''
from langchain_openai import ChatOpenAI

# Apuntamos al servicio 'litellm' definido en el docker-compose
# La key puede ser cualquiera, LiteLLM usa la real del .env
llm = ChatOpenAI(
    model="crewai-proxy", 
    openai_api_base="http://litellm:4000",
    openai_api_key="sk-fake-key", 
    temperature=0.7,
    max_retries=1
)
