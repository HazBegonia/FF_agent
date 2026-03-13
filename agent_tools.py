# agent_tools.py
import os
import logging
from langchain.tools import tool
from rag_engine import AdvancedRAGEngine

logger = logging.getLogger(__name__)

rag_engines = {}
CURRENT_SESSION_ID = "default_session" 

def get_rag_engine(session_id: str) -> AdvancedRAGEngine:
    if session_id not in rag_engines:
        db_path = os.path.join("./faiss_db", str(session_id))
        rag_engines[session_id] = AdvancedRAGEngine(db_dir=db_path)
    return rag_engines[session_id]

@tool
def ask_knowledge_base(question: str) -> str:
    """
    只要用户提问中提到了“文档”、“文件”、“知识库”或者任何暗示需要查阅资料的字眼，都必须立刻调用此工具！
    """
    session_id = CURRENT_SESSION_ID
    logger.info(f"👉 Agent 正在调用 RAG 工具，Session: {session_id} | 问题: {question}")
    
    try:
        engine = get_rag_engine(session_id)
        return engine.query(question)
    except Exception as e:
        return f"检索知识库时发生错误: {str(e)}"

@tool
def translate_text(text: str, target_language: str) -> str:
    """当用户要求翻译一段文本时调用此工具。"""
    return f"请将以下内容翻译为{target_language}：\n{text}"

@tool
def get_web_content(url: str) -> str:
    """当用户提供网页链接并要求读取时调用此工具。"""
    return f"这是从 {url} 抓取到的模拟核心内容..."

def get_all_tools():
    return [ask_knowledge_base, translate_text, get_web_content]