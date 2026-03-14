import os
import sys
import uuid
import markdown
import requests
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog
from PyQt6.QtGui import QScreen, QKeyEvent
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (
    MSFluentWindow, TextEdit, PrimaryPushButton, 
    TextBrowser, InfoBar, InfoBarPosition, 
    setTheme, Theme, TitleLabel, FluentIcon, NavigationItemPosition,
    ToolButton, TransparentToolButton, ListWidget, LineEdit,
    MessageBoxBase, SubtitleLabel,
    RoundMenu, Action, MessageBox
)

import requests

def get_real_api_url():
    online_config_url = "https://gitee.com/Haz_Begonia/ff-config/raw/master/url.txt" 
    
    try:
        response = requests.get(online_config_url, timeout=5)
        if response.status_code == 200:
            real_url = response.text.strip()
            
            if real_url.startswith("http"):
                print(f"成功获取动态地址: {real_url}")
                return real_url
            else:
                print("警告：抓取到的内容不是有效网址，可能链接填错了！内容前50个字符为：", real_url[:50])
                
    except Exception as e:
        print("获取动态地址失败，将使用本地默认地址:", e)
    
    return "http://127.0.0.1:8000" 

API_BASE_URL = get_real_api_url()

class AgentWorker(QThread):
    update_signal = pyqtSignal(str) 
    finish_signal = pyqtSignal()

    def __init__(self, user_input, session_id, system_prompt, parent=None):
        super().__init__(parent)
        self.user_input = user_input
        self.session_id = session_id 
        self.system_prompt = system_prompt

    def run(self):
        self.update_signal.emit(f"<b>🤖 FF:</b><br>")
        try:
            payload = {
                "user_input": self.user_input, 
                "session_id": self.session_id,
                "system_prompt": self.system_prompt
            }
            response = requests.post(f"{API_BASE_URL}/chat", json=payload, timeout=120)
            response.raise_for_status()
            
            res_json = response.json()
            
            if res_json.get("status") == "success":
                raw_response = res_json.get("data")
            else:
                raw_response = f"服务端处理报错: {res_json.get('message')}"

            html_response = markdown.markdown(raw_response, extensions=['fenced_code', 'tables'])
            self.update_signal.emit(html_response)
            
        except requests.exceptions.RequestException as e:
            self.update_signal.emit(f"<div style='color: #ff5555;'>[网络报错] 无法连接到大模型服务端！请确认 server.py 是否已启动。<br>详细错误：{str(e)}</div>")
        except Exception as e:
            self.update_signal.emit(f"<div style='color: #ff5555;'>[系统报错] 解析数据失败：{str(e)}</div>")
            
        self.update_signal.emit("<br><br>") 
        self.finish_signal.emit()

class DocWorker(QThread):
    progress_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(bool)

    def __init__(self, file_paths, session_id, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.session_id = session_id

    def run(self):
        try:
            for file_path in self.file_paths:
                self.progress_signal.emit(f"正在上传: {file_path}")
        
                with open(file_path, 'rb') as f:
                    files = {'file': (os.path.basename(file_path), f)}
                    data = {'session_id': self.session_id}
                    resp = requests.post(f"{API_BASE_URL}/upload_doc", files=files, data=data)
                    resp.raise_for_status()
                    
                if resp.json().get("status") != "success":
                    raise Exception(resp.json().get("message"))
            
            self.finish_signal.emit(True)
        except requests.exceptions.RequestException:
            self.progress_signal.emit("网络连接失败")
            self.finish_signal.emit(False)
        except Exception as e:
            self.progress_signal.emit(f"处理失败: {str(e)}")
            self.finish_signal.emit(False)

class PromptDialog(MessageBoxBase):
    """自定义系统提示词输入弹窗"""
    def __init__(self, current_prompt="", parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('✨ 设定专属智能体角色', self)
        self.textEdit = TextEdit(self)
        
        self.textEdit.setPlaceholderText("例如：你是一位精通Python的资深老师，请用幽默风趣的语言解答我的问题...")
        self.textEdit.setText(current_prompt)
        self.textEdit.setMinimumHeight(150)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.textEdit)

        self.widget.setMinimumWidth(450)

class RenameDialog(MessageBoxBase):
    """自定义重命名对话弹窗"""
    def __init__(self, current_name="", parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('✏️ 重命名对话', self)
        self.nameEdit = LineEdit(self)
        self.nameEdit.setText(current_name)
        self.nameEdit.setClearButtonEnabled(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.nameEdit)
        self.widget.setMinimumWidth(350)

class ChatInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("ChatInterface")
        
        self.session_ui_history = {} 
        self.session_prompts = {}
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

        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self.show_context_menu)

        self.leftPanel.addWidget(self.btn_new_chat)
        self.leftPanel.addWidget(self.session_list)
        self._is_sidebar_expanded = True
        self.sidebar_anim = QPropertyAnimation(self.left_container, b"maximumWidth", self)
        self.sidebar_anim.setDuration(300)
        self.sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # ---------------- 右侧主要区域 ----------------
        self.rightPanel = QVBoxLayout()

        # 1. 标题栏与角色设定按钮
        self.title_layout = QHBoxLayout()
        self.title_label = TitleLabel("FF 智能体", self)
        
        self.btn_set_role = ToolButton(FluentIcon.EDIT, self)
        self.btn_set_role.setToolTip("设定智能体角色 (System Prompt)")
        self.btn_set_role.clicked.connect(self.open_prompt_dialog)
        
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch(1) 
        self.title_layout.addWidget(self.btn_set_role)

        # 2. 聊天历史显示区
        self.chat_display = TextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)

        # 3. 底部输入区
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

        # --- 组装右侧面板 ---
        self.rightPanel.addLayout(self.title_layout) 
        self.rightPanel.addWidget(self.chat_display)
        self.rightPanel.addLayout(self.inputLayout)

        self.mainLayout.addWidget(self.left_container)
        self.mainLayout.addLayout(self.rightPanel, 1)

        # 默认创建第一个会话
        self.create_new_session()
    
    def open_prompt_dialog(self):
        if not self.current_session_id:
            return

        current_prompt = self.session_prompts.get(self.current_session_id, "")
        
        dialog = PromptDialog(current_prompt, self.window())
        
        if dialog.exec(): 
            new_prompt = dialog.textEdit.toPlainText().strip()
            self.session_prompts[self.current_session_id] = new_prompt
            
            InfoBar.success(
                title='角色已更新',
                content='当前对话的专属系统提示词已生效！',
                orient=Qt.Orientation.Horizontal,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.window()
            )

    def toggle_sidebar(self):
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
        self.session_prompts[new_id] = "你是一个名为 FF 的资深智能助手..."
        
        item = QtWidgets.QListWidgetItem(session_name)
        item.setData(Qt.ItemDataRole.UserRole, new_id)
        self.session_list.addItem(item)
        self.session_list.setCurrentItem(item)
        self.btn_send.setEnabled(True)
        self.text_input.setEnabled(True)
        
        self._load_session(new_id)

    def switch_session(self, item):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_session(session_id)

    def show_context_menu(self, pos):
        """在鼠标右键点击的位置显示菜单"""
        item = self.session_list.itemAt(pos)
        if not item:
            return

        self.session_list.setCurrentItem(item)
        self.switch_session(item)

        menu = RoundMenu(parent=self)
        
        rename_action = Action(FluentIcon.EDIT, '重命名', self)
        rename_action.triggered.connect(lambda: self.rename_session(item))
        
        delete_action = Action(FluentIcon.DELETE, '删除对话', self)
        delete_action.triggered.connect(lambda: self.delete_session(item))
        
        menu.addAction(rename_action)
        menu.addAction(delete_action)
        
        menu.exec(self.session_list.mapToGlobal(pos))

    def rename_session(self, item):
        """弹出重命名窗口"""
        dialog = RenameDialog(item.text(), self.window())
        if dialog.exec():
            new_name = dialog.nameEdit.text().strip()
            if new_name:
                item.setText(new_name)

    def delete_session(self, item):
        """删除当前会话"""
        title = '删除对话'
        content = f'确定要删除 "{item.text()}" 吗？此操作无法恢复。'
        w = MessageBox(title, content, self.window())
        if w.exec():
            session_id = item.data(Qt.ItemDataRole.UserRole)
            
            row = self.session_list.row(item)
            self.session_list.takeItem(row)
            
            if session_id in self.session_ui_history:
                del self.session_ui_history[session_id]
            if session_id in self.session_prompts:
                del self.session_prompts[session_id]
            if self.session_list.count() > 0:
                first_item = self.session_list.item(0)
                self.session_list.setCurrentItem(first_item)
                self.switch_session(first_item)
            else:
                self.current_session_id = None
                self.chat_display.setHtml("<br><br><h3 style='text-align:center; color:gray;'>暂无对话，请点击左侧 ➕ 新建对话。</h3>")
                self.btn_send.setEnabled(False)
                self.text_input.setEnabled(False)
                self.btn_set_role.setToolTip("请先新建对话")

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

        current_sys_prompt = self.session_prompts.get(self.current_session_id, "")
        if not current_sys_prompt:
            current_sys_prompt = "你是一个名为 FF 的资深智能助手..." 

        self.agent_thread = AgentWorker(user_text, self.current_session_id, current_sys_prompt)
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
class SafeMenuButton(QWidget):
    clicked = pyqtSignal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelected = lambda x: None  
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        self.menu_btn_container = SafeMenuButton(self)
        self.menu_btn_container.setFixedSize(40, 40)
        self.menu_btn_container.real_btn.clicked.connect(self.chat_interface.toggle_sidebar)

        self.navigationInterface.addWidget(
            'toggle_sidebar_btn', 
            self.menu_btn_container,
            None,
            NavigationItemPosition.TOP 
        )
        
        self.addSubInterface(self.chat_interface, icon=FluentIcon.CHAT, text='对话')
        
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
            self.chat_interface.chat_display.append(f"<b>系统:</b> 正在将 {len(file_paths)} 个文件发送到服务端...<br><br>")
            
            self.doc_thread = DocWorker(file_paths, current_session)
            self.doc_thread.finish_signal.connect(self.on_docs_processed)
            self.doc_thread.start()

    def on_docs_processed(self, success):
        if success:
            InfoBar.success(
                title='知识库构建成功',
                content="文档已全部上传至服务端并解析完毕，可以开始提问了！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.chat_interface.chat_display.append("<b>系统:</b> ✅ 知识库更新完成！<br><br>")
        else:
            InfoBar.error(title="错误", content="文档处理失败，请检查服务端是否正常运行。", parent=self)

    def handle_clear_db(self):
        current_session = self.chat_interface.current_session_id
        if current_session:
            try:
                resp = requests.post(f"{API_BASE_URL}/clear_db", data={"session_id": current_session})
                resp.raise_for_status()
                
                InfoBar.success(title='清理完成', content="服务端的知识库已被清空。", parent=self)
                self.chat_interface.chat_display.append("<b>系统:</b> 服务端当前知识库已清空。<br><br>")
            except Exception as e:
                InfoBar.error(title="错误", content=f"清理请求失败，无法连接到服务端。", parent=self)

class ChatTextEdit(TextEdit):
    send_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
                super().keyPressEvent(event)
            else:
                self.send_signal.emit()
                event.accept() 
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())