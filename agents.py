from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage


class Agent:
    """
    A single agent with a fixed personality (system prompt).
    Uses any LangChain-compatible LLM under the hood.
    """

    def __init__(self, name: str, system_prompt: str, llm):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm

    def run(self, context: str, task: str) -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""CURRENT ANALYSIS LOG:
{context if context.strip() else "(No analysis yet — you are going first.)"}

YOUR TASK:
{task}""")
        ]
        response = self.llm.invoke(messages)
        # Handle both ChatModel (AIMessage) and LLM (str) responses
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response).strip()
