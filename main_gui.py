import os
import torch
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
from PyQt6.QtGui import QScreen
from agent_core import FFAgentCore 
from rag_engine import AdvancedRAGEngine
from agent_tools import get_rag_engine
from qfluentwidgets import ListWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QKeyEvent
from qfluentwidgets import (
    MSFluentWindow, TextEdit, PrimaryPushButton, 
    TextBrowser, InfoBar, InfoBarPosition, 
    setTheme, Theme, TitleLabel, FluentIcon, NavigationItemPosition,
    ToolButton, TransparentToolButton
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
        
        self.update_signal.emit(f"<b>🤖 FF:</b><br>")
        try:
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
        self.agent = FFAgentCore()
        
        self.session_ui_history = {} 
        self.current_session_id = None

        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(16)

        self.left_container = QWidget(self)
        self.left_container.setMaximumWidth(200)
        self.left_container.setMinimumWidth(0) 
        
        self.leftPanel = QVBoxLayout(self.left_container)
        self.leftPanel.setContentsMargins(0, 0, 0, 0)

        self.btn_new_chat = PrimaryPushButton("➕ 新建对话", self.left_container)
        self.btn_new_chat.clicked.connect(self.create_new_session)
        
        self.session_list = ListWidget(self.left_container)
        self.session_list.itemClicked.connect(self.switch_session)

        self.leftPanel.addWidget(self.btn_new_chat)
        self.leftPanel.addWidget(self.session_list)
        self._is_sidebar_expanded = True
        self.sidebar_anim = QPropertyAnimation(self.left_container, b"maximumWidth", self)
        self.sidebar_anim.setDuration(300)
        self.sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.rightPanel = QVBoxLayout()
        
        self.title_layout = QHBoxLayout()
        self.title_label = TitleLabel("FF 智能助理", self)
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch(1) 

        self.chat_display = TextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)

        self.inputLayout = QHBoxLayout()

        self.text_input = ChatTextEdit(self)
        self.text_input.setPlaceholderText("在这里输入您的问题")

        self.text_input.send_signal.connect(self.handle_send)
        self.text_input.setFixedHeight(80)
        
        self.btn_send = PrimaryPushButton("发送 🚀", self)
        self.btn_send.setFixedSize(100, 80)
        self.btn_send.clicked.connect(self.handle_send)

        self.inputLayout.addWidget(self.text_input)
        self.inputLayout.addWidget(self.btn_send)

        self.rightPanel.addLayout(self.title_layout) 
        self.rightPanel.addWidget(self.chat_display)
        self.rightPanel.addLayout(self.inputLayout)

        # ==========================================
        # 组装这三个部分：常驻条 -> 滑动侧边栏 -> 右侧主界面
        # ==========================================
        self.mainLayout.addWidget(self.left_container)
        self.mainLayout.addLayout(self.rightPanel, 1)

        self.create_new_session()

    def toggle_sidebar(self):
        """控制左侧会话列表的滑动伸缩动画"""
        if self.sidebar_anim.state() == QPropertyAnimation.State.Running:
            return

        if self._is_sidebar_expanded:
            self.sidebar_anim.setStartValue(200)
            self.sidebar_anim.setEndValue(0)
            self._is_sidebar_expanded = False
        else:
            self.sidebar_anim.setStartValue(0)
            self.sidebar_anim.setEndValue(200)
            self._is_sidebar_expanded = True
            
        self.sidebar_anim.start()

    def create_new_session(self):
        new_id = str(uuid.uuid4())[:8]
        session_name = f"对话 {self.session_list.count() + 1}"
        
        welcome_msg = "<b>🤖 FF:</b> 欢迎！有什么可以帮助的呢？<br><br>"
        self.session_ui_history[new_id] = welcome_msg
        
        item = QtWidgets.QListWidgetItem(session_name)
        item.setData(Qt.ItemDataRole.UserRole, new_id)
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

# ==========================================
# 特洛伊木马容器：专治 QFluentWidgets 底部路由闪退
# ==========================================
class SafeMenuButton(QWidget):
    # 骗过底层路由，给它一个信号去连，但我们永远不 emit，切断它的切页逻辑
    clicked = pyqtSignal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        # 骗过底层状态检查
        self.setSelected = lambda x: None  
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 真正干活的按钮藏在里面
        self.real_btn = TransparentToolButton(FluentIcon.MENU, self)
        self.real_btn.setFixedSize(40, 40)
        layout.addWidget(self.real_btn)
        
class MainWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FF Agent")
        self.resize(700, 600)
        setTheme(Theme.DARK)

        self.chat_interface = ChatInterface(self)
        
        # ==========================================
        # 1. 部署顶部安全折叠按钮
        # ==========================================
        self.menu_btn_container = SafeMenuButton(self)
        self.menu_btn_container.setFixedSize(40, 40)
        # 将真正干活的按钮绑定到折叠动画上
        self.menu_btn_container.real_btn.clicked.connect(self.chat_interface.toggle_sidebar)

        self.navigationInterface.addWidget(
            'toggle_sidebar_btn', 
            self.menu_btn_container,
            None,
            NavigationItemPosition.TOP 
        )
        
        # ==========================================
        # 2. 加载聊天主界面
        # ==========================================
        self.addSubInterface(
            self.chat_interface, 
            icon=FluentIcon.CHAT,  
            text='对话'
        )
        
        # ==========================================
        # 3. 恢复底部按钮（去掉会引发报错的 isSelectable）
        # ==========================================
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

        self.center()
    def center(self):
        """将窗口移动到屏幕中心"""
        screen = self.screen()
        screen_geometry = screen.availableGeometry()
        size = self.frameGeometry()
        x = (screen_geometry.width() - size.width()) // 2
        y = (screen_geometry.height() - size.height()) // 2
        
        self.move(x, y)
        
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

# ==========================================
# 自定义聊天输入框：接管回车键逻辑
# ==========================================
class ChatTextEdit(TextEdit):
    # 自定义一个信号，当用户敲击纯回车时发射
    send_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event: QKeyEvent):
        # 如果按下的是回车键 (Return 对应主键盘回车，Enter 对应数字键盘回车)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # 检查是否同时按下了 Shift 或 Control
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
                # 正常放行：执行换行逻辑
                super().keyPressEvent(event)
            else:
                # 纯回车：拦截默认换行行为，发射发送信号
                self.send_signal.emit()
                event.accept() # 告诉系统“这按键我处理了，你别管了”
        else:
            # 按了其他键，该干嘛干嘛
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())