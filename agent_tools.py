# agent_tools.py
from langchain.tools import tool
from rag_engine import AdvancedRAGEngine
import logging

logger = logging.getLogger(__name__)

# 1. 实例化我们的 RAG 引擎
rag_engine = AdvancedRAGEngine()

@tool
def ask_knowledge_base(question: str) -> str:
    """
    当用户询问关于文档中的特定信息时，必须调用此工具。
    传入的参数 question 应该是具体的问题。
    """
    logger.info(f"👉 Agent 正在调用 RAG 工具，问题: {question}")
    try:
        # 直接调用我们写好的高阶 RAG 管道
        return rag_engine.query(question)
    except Exception as e:
        return f"检索知识库时发生错误: {str(e)}"

@tool
def translate_text(text: str, target_language: str) -> str:
    """
    当用户要求翻译一段文本时调用此工具。
    参数 text 是要翻译的内容，target_language 是目标语言（如英语、日语等）。
    """
    logger.info(f"👉 Agent 正在调用翻译工具")
    return f"请将以下内容翻译为{target_language}：\n{text}"

@tool
def get_web_content(url: str) -> str:
    """
    当用户提供了一个 http/https 链接，并要求读取网页信息或总结网页时调用此工具。
    """
    logger.info(f"👉 Agent 正在调用网页抓取工具，URL: {url}")
    return f"这是从 {url} 抓取到的模拟核心内容：该网页主要介绍了一些..."

def get_all_tools():
    return [ask_knowledge_base, translate_text, get_web_content]