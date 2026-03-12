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
    只要用户提问中提到了“文档”、“文件”、“知识库”或者任何暗示需要查阅资料的字眼（例如“这是干啥的”、“总结一下”），都必须立刻调用此工具！
    哪怕用户的问题很宽泛，也请直接将用户的原话作为 question 参数传入，交由检索系统处理。
    """
    logger.info(f"👉 Agent 正在调用 RAG 工具，问题: {question}")
    try:
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