import os
import logging
from typing import List
from dotenv import load_dotenv

from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

class AdvancedRAGEngine:
    def __init__(self, db_dir: str = "./chroma_db"):
        self.db_dir = db_dir
        self.AI_API_KEY = os.getenv("AI_API_KEY")
        self.base_url = os.getenv("AI_ENDPOINT")
        self.AI_MODEL = os.getenv("AI_MODEL")
        self.AI_EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL")
        self.EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
        
        # 1. 核心模型初始化 (这里默认使用 OpenAI，你可以随时换成本地的 Ollama/VLLM)
        self.llm = ChatOpenAI(
            model = self.AI_MODEL,
            base_url = self.base_url,
            api_key = self.AI_API_KEY,
            temperature = 0.3
        )
        self.embeddings = OpenAIEmbeddings(
            model = self.AI_EMBEDDING_MODEL,
            api_key = self.EMBEDDING_API_KEY, 
            base_url = self.base_url
        )
        
        # 初始化向量数据库引用
        self.vectorstore = Chroma(
            persist_directory=self.db_dir, 
            embedding_function=self.embeddings
        )

    def ingest_document(self, file_path: str):
        """
        阶段一：文档加载与高级分片 (Chunking & Embeddings)
        """
        logger.info(f"开始处理文件: {file_path}")
        loader = UnstructuredFileLoader(file_path)
        docs = loader.load()

        # 高级技巧：合理设置 chunk_size 和 overlap。
        # chunk 太大则召回精度低，太小则丢失上下文。overlap 保证截断处的信息连贯。
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, 
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
        )
        splits = text_splitter.split_documents(docs)
        
        # 存入 ChromaDB
        self.vectorstore.add_documents(splits)
        logger.info(f"文件处理完成，共生成 {len(splits)} 个文本块。")

    def _get_advanced_retriever(self):
        """
        阶段二与三：构建 多路召回 + 重排 的复合检索器
        """
        # 基础检索器：一次性召回较多文档（比如 15 个），为了给重排留足空间
        base_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 15})

        # --- 核心技术 1: Multi-Query (Query Translation) ---
        # 覆写默认的 Prompt，强制要求大模型生成中文的不同视角问题
        multi_query_prompt = PromptTemplate(
            input_variables=["question"],
            template="""你是一个AI语言模型助手。你的任务是根据给定的用户问题，生成 3 个不同版本的提问。
            通过从不同角度重写问题，帮助用户克服基于距离的相似性搜索的局限性。
            请用中文输出，每个问题占一行，不要有其他废话。
            原始问题: {question}"""
        )
        
        multi_query_retriever = MultiQueryRetriever.from_llm(
            retriever=base_retriever,
            llm=self.llm,
            prompt=multi_query_prompt
        )

        # --- 核心技术 2: 召回重排 (Reranking) ---
        # 向量检索只计算“字面语义距离”，我们需要 CrossEncoder 来计算“问题与文档的真实匹配度”
        model = HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
        compressor = CrossEncoderReranker(model=model, top_n=4) # 从 15 个中精选最相关的 4 个

        # 组合成复合检索器
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=multi_query_retriever
        )
        
        return compression_retriever

    def query(self, user_question: str) -> str:
        """
        阶段四：检索与合成回答 (Retrieval & Synthesis)
        """
        retriever = self._get_advanced_retriever()
        
        # 定义最终合成答案的 Prompt
        template = """请基于以下检索到的参考信息来回答用户的问题。
        如果你不知道答案，请直接说不知道，不要编造。
        
        参考信息:
        {context}
        
        用户问题: {question}
        
        回答:"""
        prompt = PromptTemplate.from_template(template)

        # 格式化检索到的文档
        def format_docs(docs: List[Document]):
            return "\n\n".join(doc.page_content for doc in docs)

        # 使用 LangChain Expression Language (LCEL) 构建执行链
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        logger.info(f"开始处理提问: {user_question}")
        return rag_chain.invoke(user_question)
    
    def clear_db(self):
        """
        文明清空数据库：清空集合内容，而不删除文件夹
        """
        logger.info("正在清空向量数据库内容...")
        
        try:
            # 1. 使用 Chroma 自带的方法删除当前集合
            # 这会清空所有存进去的文档，但保留数据库的结构
            self.vectorstore.delete_collection()
            
            # 2. 重新初始化（Chroma 会自动创建一个新的空集合）
            self.vectorstore = Chroma(
                persist_directory=self.db_dir, 
                embedding_function=self.embeddings
            )
            logger.info("数据库内容已重置。")
        except Exception as e:
            logger.error(f"清空数据库时发生错误: {e}")
            # 如果上面还是锁死，至少给用户一个友好的提示
            raise e
# --- 本地测试代码 ---
if __name__ == "__main__":
    engine = AdvancedRAGEngine()
    
    engine.ingest_document(r"D:\桌面\桌面文件\76cadffbec5ecc872e48e230af59941e.jpg")
    
    answer = engine.query("文档里提到了哪些信息？")
    print("\n=== 最终回答 ===")
    print(answer)