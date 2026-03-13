import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1" # 严禁底层 C++ 库在子线程里无限套娃开线程！

import logging
from typing import List
from dotenv import load_dotenv

from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

logger.info("正在初始化全局向量模型...")
GLOBAL_EMBEDDINGS = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={'device': 'cpu'},       
    encode_kwargs={'normalize_embeddings': True}
)
logger.info("全局向量模型加载完毕！")

class AdvancedRAGEngine:
    def __init__(self, db_dir: str = "./faiss_db"): 
        self.db_dir = db_dir
        self.AI_API_KEY = os.getenv("AI_API_KEY")
        self.base_url = os.getenv("AI_ENDPOINT")
        self.AI_MODEL = os.getenv("AI_MODEL")
        
        self.llm = ChatOpenAI(
            model = self.AI_MODEL,
            base_url = self.base_url,
            api_key = self.AI_API_KEY,
            temperature = 0.3
        )
        
        self.embeddings = GLOBAL_EMBEDDINGS

    def ingest_document(self, file_path: str):
        logger.info(f"开始处理文件: {file_path}")
        loader = UnstructuredFileLoader(file_path)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, 
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
        )
        splits = text_splitter.split_documents(docs)
        
        index_path = os.path.join(self.db_dir, "index.faiss")
        if os.path.exists(index_path):
            vectorstore = FAISS.load_local(self.db_dir, self.embeddings, allow_dangerous_deserialization=True)
            vectorstore.add_documents(splits)
        else:
            vectorstore = FAISS.from_documents(splits, self.embeddings)
            
        vectorstore.save_local(self.db_dir)
        logger.info(f"文件处理完成，共生成 {len(splits)} 个文本块，已存入 FAISS！")

    def _get_advanced_retriever(self):
        vectorstore = FAISS.load_local(self.db_dir, self.embeddings, allow_dangerous_deserialization=True)
        base_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

        multi_query_prompt = PromptTemplate(
            input_variables=["question"],
            template="""你是一个AI语言模型助手。你的任务是根据给定的用户问题，生成 3 个不同版本的提问。
            请用中文输出，每个问题占一行，不要有其他废话。
            原始问题: {question}"""
        )
        
        multi_query_retriever = MultiQueryRetriever.from_llm(
            retriever=base_retriever,
            llm=self.llm,
            prompt=multi_query_prompt
        )
        
        return multi_query_retriever

    def query(self, user_question: str) -> str:
        if not os.path.exists(os.path.join(self.db_dir, "index.faiss")):
            return "当前对话还没有上传过任何文档哦，请先在左侧上传文档再提问。"

        retriever = self._get_advanced_retriever()
        
        template = """请基于以下检索到的参考信息来回答用户的问题。
        如果你不知道答案，请直接说不知道，不要编造。
        
        参考信息:
        {context}
        
        用户问题: {question}
        
        回答:"""
        prompt = PromptTemplate.from_template(template)

        def format_docs(docs: List[Document]):
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        logger.info(f"开始处理提问: {user_question}")
        return rag_chain.invoke(user_question)
    
    def clear_db(self):
        logger.info("正在清空向量数据库内容...")
        try:
            import shutil
            if os.path.exists(self.db_dir):
                shutil.rmtree(self.db_dir)
            logger.info("数据库内容已重置。")
        except Exception as e:
            logger.error(f"清空数据库时发生错误: {e}")
            raise e