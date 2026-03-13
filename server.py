import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import uvicorn
import agent_tools 
from agent_core import FFAgentCore
from agent_tools import get_rag_engine

app = FastAPI(title="FF Agent Backend")

agent = FFAgentCore()

class ChatRequest(BaseModel):
    user_input: str
    session_id: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """处理聊天对话的接口"""
    try:
        agent_tools.CURRENT_SESSION_ID = request.session_id
        
        response = agent.chat(request.user_input, request.session_id)
        return {"status": "success", "data": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/upload_doc")
async def upload_doc_endpoint(session_id: str = Form(...), file: UploadFile = File(...)):
    """处理文档上传并向量化的接口"""
    try:
        temp_file_path = f"./temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        rag = get_rag_engine(session_id)
        rag.ingest_document(temp_file_path)
        
        os.remove(temp_file_path)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/clear_db")
async def clear_db_endpoint(session_id: str = Form(...)):
    """清理知识库的接口"""
    rag = get_rag_engine(session_id)
    rag.clear_db()
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)