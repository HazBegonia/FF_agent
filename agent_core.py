# agent_core.py
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent_tools import get_all_tools

load_dotenv()

class FFAgentCore:
    def __init__(self):
        # 1. 初始化模型
        self.llm = ChatOpenAI(
            model=os.getenv("AI_MODEL"),
            base_url=os.getenv("AI_ENDPOINT"),
            api_key=os.getenv("AI_API_KEY"),
            temperature=0.2
        )
        
        self.tools = get_all_tools()
        
        self.session_store = {}
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"), # 这里由固定字符串变为占位符变量
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.base_agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True
        )

        self.agent_with_history = RunnableWithMessageHistory(
            self.base_agent_executor,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def get_session_history(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self.session_store:
            self.session_store[session_id] = ChatMessageHistory()
        return self.session_store[session_id]

    def chat(self, user_input: str, session_id: str = "default_session", system_prompt: str = "你是一个名为 FF 的资深智能助手...") -> str:
        """接收用户输入、会话ID和系统提示词，返回 Agent 回答"""
        try:
            response = self.agent_with_history.invoke(
                {
                    "input": user_input, 
                    "system_prompt": system_prompt
                },
                config={"configurable": {"session_id": session_id}}
            )
            return response["output"]
        except Exception as e:
            return f"Agent 运行出错: {str(e)}"