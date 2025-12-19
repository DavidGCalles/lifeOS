from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="crewai-proxy", 
    base_url="http://litellm:4000",
    api_key="sk-fake-key",  
    temperature=0.7,
    max_retries=1
)