import os
import asyncio
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sys
import time
from PyQt6 import QtWidgets
import markdown
import agent_tools
import uuid
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from agent_core import LuminaAgentCore 
from rag_engine import AdvancedRAGEngine
from agent_tools import get_rag_engine
from qfluentwidgets import ListWidget

from qfluentwidgets import (
    MSFluentWindow, TextEdit, PrimaryPushButton, 
    TextBrowser, InfoBar, InfoBarPosition, 
    setTheme, Theme, TitleLabel, FluentIcon, NavigationItemPosition
)
# ==========================================
# 1. 核心对话工作线程 (真正调用大模型)
# ==========================================
class AgentWorker(QThread):
    update_signal = pyqtSignal(str) 
    finish_signal = pyqtSignal()

    def __init__(self, agent_instance, user_input, session_id, parent=None):
        super().__init__(parent)
        self.agent = agent_instance 
        self.user_input = user_input
        self.session_id = session_id 

    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        
        self.update_signal.emit(f"<b>🤖 Lumina:</b><br>")
        try:
            # 【新增】每次提问前，强行把当前 session_id 塞给工具模块！
            agent_tools.CURRENT_SESSION_ID = self.session_id
            
            raw_response = self.agent.chat(self.user_input, self.session_id) 
            html_response = markdown.markdown(raw_response, extensions=['fenced_code', 'tables'])
            self.update_signal.emit(html_response)
        except Exception as e:
            self.update_signal.emit(f"<div style='color: #ff5555;'>[系统报错] 连接失败：{str(e)}</div>")
        self.update_signal.emit("<br><br>") 
        self.finish_signal.emit()

# ==========================================
# 2. 聊天界面部件
# ==========================================
class ChatInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("ChatInterface")
        self.agent = LuminaAgentCore()
        
        self.session_ui_history = {} 
        self.current_session_id = None

        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.btn_new_chat = PrimaryPushButton("➕ 新建对话", self)
        self.btn_new_chat.clicked.connect(self.create_new_session)
        
        self.session_list = ListWidget(self)
        self.session_list.setFixedWidth(200)
        self.session_list.itemClicked.connect(self.switch_session)

        self.leftPanel.addWidget(self.btn_new_chat)
        self.leftPanel.addWidget(self.session_list)
        
        self.rightPanel = QVBoxLayout()
        self.title_label = TitleLabel("Lumina 智能助理", self)
        
        self.chat_display = TextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)

        self.inputLayout = QHBoxLayout()
        self.text_input = TextEdit(self)
        self.text_input.setPlaceholderText("在这里输入您的问题...")
        self.text_input.setFixedHeight(80)
        
        self.btn_send = PrimaryPushButton("发送 🚀", self)
        self.btn_send.setFixedSize(100, 80)
        self.btn_send.clicked.connect(self.handle_send)

        self.inputLayout.addWidget(self.text_input)
        self.inputLayout.addWidget(self.btn_send)

        self.rightPanel.addWidget(self.title_label)
        self.rightPanel.addWidget(self.chat_display)
        self.rightPanel.addLayout(self.inputLayout)

        self.mainLayout.addLayout(self.leftPanel)
        self.mainLayout.addLayout(self.rightPanel, stretch=1)

        self.create_new_session()

    def create_new_session(self):
        new_id = str(uuid.uuid4())[:8]
        session_name = f"对话 {self.session_list.count() + 1}"
        
        welcome_msg = "<b>🤖 Lumina:</b> 欢迎！这是一个全新的对话窗口。<br><br>"
        self.session_ui_history[new_id] = welcome_msg
        
        item = QtWidgets.QListWidgetItem(session_name)
        item.setData(Qt.ItemDataRole.UserRole, new_id) # 把 ID 藏在 Item 数据里
        self.session_list.addItem(item)
        self.session_list.setCurrentItem(item)
        
        self._load_session(new_id)

    def switch_session(self, item):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_session(session_id)

    def _load_session(self, session_id):
        self.current_session_id = session_id
        self.chat_display.setHtml(self.session_ui_history[session_id])
        self.text_input.setFocus()

    def handle_send(self):
        user_text = self.text_input.toPlainText().strip()
        if not user_text or not self.current_session_id:
            return

        user_msg = f"<div style='color: #0078D4;'><b>🧑‍💻 您:</b><br>{user_text}</div><br>"
        self.update_chat_display(user_msg)
        
        self.text_input.clear()
        self.btn_send.setEnabled(False)
        self.text_input.setEnabled(False)
        
        self.agent_thread = AgentWorker(self.agent, user_text, self.current_session_id)
        self.agent_thread.update_signal.connect(self.update_chat_display)
        self.agent_thread.finish_signal.connect(self.agent_finished)
        self.agent_thread.start()

    def update_chat_display(self, text):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(text)
        self.chat_display.setTextCursor(cursor)
        
        self.session_ui_history[self.current_session_id] = self.chat_display.toHtml()

    def agent_finished(self):
        self.btn_send.setEnabled(True)
        self.text_input.setEnabled(True)
        self.text_input.setFocus()

# ==========================================
# 3. 主窗口 
# ==========================================
class MainWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lumina Agent")
        self.resize(1000, 700)
        setTheme(Theme.DARK)

        self.chat_interface = ChatInterface(self)
        
        self.addSubInterface(
            self.chat_interface, 
            icon=FluentIcon.CHAT,  
            text='对话'
        )

        self.navigationInterface.addItem(
            routeKey='upload_docs',
            icon=FluentIcon.FOLDER,
            text='上传文档',
            onClick=self.handle_upload,
            position=NavigationItemPosition.BOTTOM
        )
        
        self.navigationInterface.addItem(
            routeKey='clear_db',
            icon=FluentIcon.DELETE,
            text='清空知识库',
            onClick=self.handle_clear_db,
            position=NavigationItemPosition.BOTTOM
        )

    def handle_upload(self):
        current_session = self.chat_interface.current_session_id
        if not current_session:
            InfoBar.warning(title="提醒", content="请先在左侧选择或新建一个对话！", parent=self)
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择知识库文件", "", "文档 (*.pdf *.txt *.md);;所有文件 (*)"
        )
        if file_paths:
            self.chat_interface.chat_display.append(f"<b>系统:</b> 正在当前会话中解析 {len(file_paths)} 个文件...<br><br>")
            
            self.doc_thread = DocWorker(file_paths, current_session)
            self.doc_thread.finish_signal.connect(self.on_docs_processed)
            self.doc_thread.start()

    def on_docs_processed(self, success):
        if success:
            InfoBar.success(
                title='知识库构建成功',
                content="文档已全部解析并向量化，您可以开始提问了！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.chat_interface.chat_display.append("<b>系统:</b> ✅ 知识库更新完成，现在我可以基于这些文档回答了！<br><br>")
        else:
            InfoBar.error(title="错误", content="文档处理失败，请查看控制台。", parent=self)

    def handle_clear_db(self):
        current_session = self.chat_interface.current_session_id
        if current_session:
            engine = get_rag_engine(current_session)
            engine.clear_db()
            
            InfoBar.success(title='清理完成', content="当前对话的知识库已被清空。", parent=self)
            self.chat_interface.chat_display.append("<b>系统:</b> 当前知识库已清空。<br><br>")

# ==========================================
# 1.5. 知识库处理工作线程 (后台解析文档)
# ==========================================
class DocWorker(QThread):
    progress_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(bool)

    def __init__(self, file_paths, session_id, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.session_id = session_id

    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            rag = get_rag_engine(self.session_id)
            for file_path in self.file_paths:
                self.progress_signal.emit(f"正在处理: {file_path}")
                rag.ingest_document(file_path) 
            self.finish_signal.emit(True)
        except Exception as e:
            self.progress_signal.emit(f"处理失败: {str(e)}")
            self.finish_signal.emit(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())