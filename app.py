import streamlit as st
import os
from rag_engine import AdvancedRAGEngine  # 导入你写的类

# --- 页面配置 ---
st.set_page_config(page_title="资深开发者的 RAG 助手", layout="wide")
st.title("🚀 智能文档知识库 (RAG)")

# --- 初始化引擎 (利用 st.session_state 保证只加载一次) ---
if "rag_engine" not in st.session_state:
    with st.spinner("正在初始化检索引擎..."):
        st.session_state.rag_engine = AdvancedRAGEngine()
        st.session_state.chat_history = []
# --- 侧边栏：多文件上传 ---
with st.sidebar:
    st.header("文件管理")
    # 核心修改点 1：增加 accept_multiple_files=True
    uploaded_files = st.file_uploader(
        "上传文档 (支持多个文件)", 
        type=["pdf", "txt", "docx", "jpg", "png"],
        accept_multiple_files=True  
    )
    
    if uploaded_files: # 如果列表不为空
        if st.button("批量开始解析"):
            # 创建进度条，让用户知道还没死机
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                # 核心修改点 2：循环处理每个文件
                status_text.text(f"正在处理第 ({i+1}/{len(uploaded_files)}): {file.name}")
                
                # 保存临时文件
                temp_path = os.path.join("./temp", file.name)
                os.makedirs("./temp", exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(file.getbuffer())
                
                # 调用你的引擎解析
                st.session_state.rag_engine.ingest_document(temp_path)
                
                # 更新进度条
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("所有文档处理完成！✅")
            st.success(f"成功导入 {len(uploaded_files)} 个文档。")


    # 增加分割线
    st.divider()
    
    # app.py 里的清空按钮部分
    if st.button("🔥 清空知识库", type="primary", use_container_width=True):
        with st.spinner("正在清理..."):
            st.session_state.rag_engine.clear_db()
            st.session_state.chat_history = [] 
            st.success("清理完毕！现在的知识库已经是出厂设置了。")
            # 延时一下让用户看清提示，然后刷新
            st.rerun()


# --- 主界面：聊天窗口 ---
st.subheader("与你的文档对话")

# 显示历史聊天记录
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("请问关于文档的任何问题..."):
    # 显示用户消息
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用你的 RAG 引擎进行回答
    with st.chat_message("assistant"):
        with st.spinner("正在检索并思考..."):
            response = st.session_state.rag_engine.query(prompt)
            st.markdown(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})