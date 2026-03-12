# agent_core.py
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.memory import ConversationBufferMemory

from agent_tools import get_all_tools

load_dotenv()

class LuminaAgentCore:
    def __init__(self):
        # 1. 初始化模型
        self.llm = ChatOpenAI(
            model=os.getenv("AI_MODEL"),
            base_url=os.getenv("AI_ENDPOINT"),
            api_key=os.getenv("AI_API_KEY"),
            temperature=0.2
        )
        
        # 2. 获取所有标准化工具
        self.tools = get_all_tools()
        
        # 3. 设置多轮对话记忆机制
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True
        )
        
        # 4. 设计 Agent 的核心 Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个名为 Lumina 的资深智能助手。你可以进行正常的对话。
            【极其重要】：用户已经在前端界面将文件上传到了你的本地向量知识库中！
            当用户说到“这个文件”、“这份文档”或询问文档内容时，你必须立刻、优先调用 `ask_knowledge_base` 工具去查，绝对不能说你看不见文件或要求用户提供！
            如果不确定答案，请结合检索到的内容诚实地说明。"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # 5. 创建 Tool Calling Agent (这是目前最先进的 Agent 类型)
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        # 6. 实例化执行器
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True,
            memory=self.memory
        )

    def chat(self, user_input: str) -> str:
        """接收用户输入，返回 Agent 回答"""
        try:
            response = self.agent_executor.invoke({"input": user_input})
            return response["output"]
        except Exception as e:
            return f"Agent 运行出错: {str(e)}"

if __name__ == "__main__":
    agent = LuminaAgentCore()
    print("🤖 Lumina Agent 初始化完毕！(输入 'exit' 退出)")
    while True:
        user_input = input("\n🧑 你: ")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        response = agent.chat(user_input)
        print(f"\n🤖 Lumina: {response}")