import sys
import time
import markdown
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from agent_core import LuminaAgentCore 
from rag_engine import AdvancedRAGEngine

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

    def __init__(self, agent_instance, user_input, parent=None):
        super().__init__(parent)
        # 接收主界面传来的 agent 实例（保证对话具有上下文记忆）
        self.agent = agent_instance 
        self.user_input = user_input

    def run(self):
        self.update_signal.emit(f"<b>🤖 Lumina:</b><br>")
        
        try:
            # 【核心调用】调用 agent_core 中的方法
            # 假设你的 agent 有一个类似 chat 或 invoke 的方法：
            raw_response = self.agent.chat(self.user_input) 
            
            # 将 Markdown 转换为 HTML 以便在界面完美显示
            html_response = markdown.markdown(raw_response, extensions=['fenced_code', 'tables'])
            self.update_signal.emit(html_response)
            
        except Exception as e:
            # 如果大模型 API 报错或网络异常，显示在界面上
            self.update_signal.emit(f"<div style='color: #ff5555;'>[系统报错] 连接大模型失败：{str(e)}</div>")
            
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
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)

        self.title_label = TitleLabel("Lumina 智能助理", self)
        
        self.chat_display = TextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.append("<b>🤖 Lumina:</b> 欢迎使用桌面端！请在下方输入您的问题，或者在左侧侧边栏上传文档。<br><br>")
        

        self.inputLayout = QHBoxLayout()
        self.text_input = TextEdit(self)
        self.text_input.setPlaceholderText("在这里输入您的问题...")
        self.text_input.setFixedHeight(80)
        
        self.btn_send = PrimaryPushButton("发送 🚀", self)
        self.btn_send.setFixedSize(100, 80)

        self.inputLayout.addWidget(self.text_input)
        self.inputLayout.addWidget(self.btn_send)

        self.vBoxLayout.addWidget(self.title_label)
        self.vBoxLayout.addWidget(self.chat_display)
        self.vBoxLayout.addLayout(self.inputLayout)

        self.btn_send.clicked.connect(self.handle_send)

    def handle_send(self):
        user_text = self.text_input.toPlainText().strip()
        if not user_text:
            return

        self.chat_display.append(f"<div style='color: #0078D4;'><b>🧑‍💻 您:</b><br>{user_text}</div><br>")
        self.text_input.clear()
        self.btn_send.setEnabled(False)
        self.text_input.setEnabled(False)
        
        self.agent_thread = AgentWorker(self.agent, user_text)
        self.agent_thread.update_signal.connect(self.update_chat_display)
        self.agent_thread.finish_signal.connect(self.agent_finished)
        self.agent_thread.start()

    def update_chat_display(self, text):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(text)
        self.chat_display.setTextCursor(cursor)

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

        self.rag_system = AdvancedRAGEngine()

    def handle_upload(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择知识库文件", "", "文档 (*.pdf *.txt *.md);;所有文件 (*)"
        )
        if file_paths:
            self.chat_interface.chat_display.append(f"<b>系统:</b> 正在后台解析 {len(file_paths)} 个文件，建立向量索引，请稍候...<br><br>")
            
            # 【核心】启动后台知识库处理线程
            self.doc_thread = DocWorker(self.rag_system, file_paths)
            self.doc_thread.finish_signal.connect(self.on_docs_processed)
            self.doc_thread.start()

    # 【新增】处理完成后的回调函数
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
         InfoBar.warning(
                title='清理完成',
                content="知识库已被清空。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
         self.chat_interface.chat_display.append("<b>系统:</b> 知识库已清空。<br><br>")
# ==========================================
# 1.5. 知识库处理工作线程 (后台解析文档)
# ==========================================
class DocWorker(QThread):
    progress_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(bool)

    def __init__(self, rag_instance, file_paths, parent=None):
        super().__init__(parent)
        self.rag = rag_instance
        self.file_paths = file_paths

    def run(self):
        try:
            # 遍历选中的每一个文件
            for file_path in self.file_paths:
                # 触发一下进度信号（可选：如果你想在 UI 上显示进度）
                self.progress_signal.emit(f"正在处理: {file_path}")
                
                # 【核心修改】调用 rag_engine 中正确的方法名 ingest_document
                self.rag.ingest_document(file_path)
                
            self.finish_signal.emit(True)
        except Exception as e:
            self.progress_signal.emit(f"处理失败: {str(e)}")
            self.finish_signal.emit(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())