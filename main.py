import sys
import os
import json
from datetime import datetime
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QToolBar, QMenu,
    QMessageBox, QLineEdit, QPushButton, QComboBox, QCheckBox, QPushButton, QGroupBox, QSpacerItem, QSizePolicy,
    QDialog, QVBoxLayout as QVBoxDialogLayout, QFormLayout, QTextEdit, QInputDialog, QListWidgetItem
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, QStandardPaths, QSize, QPoint, Qt, QObject, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QColor, QIcon

STORAGE_FILE = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation), "storages.json")
SETTINGS_FILE = "settings.json"

from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot

class CloseBridge(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window

    @pyqtSlot()
    def closeWindow(self):
        self.window.close()


class ConsoleBridge(QObject):
    def __init__(self, console_widget):
        super().__init__()
        self.console_widget = console_widget

    @pyqtSlot(str)
    def log(self, message):
        self.console_widget.append(f"[log] {message}")
        self.console_widget.verticalScrollBar().setValue(self.console_widget.verticalScrollBar().maximum())

class DevConsole(QDialog):
    def __init__(self, web_page: QWebEnginePage):
        super().__init__()
        self.setWindowTitle("Developer Console")
        self.setMinimumSize(600, 300)
        self.web_page = web_page

        layout = QVBoxDialogLayout()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("background-color: black; color: lime; font-family: Consolas, monospace;")
        self.output.setFont(QFont("Consolas", 10))

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type JavaScript command and press Enter...")
        self.input.setStyleSheet("background-color: black; color: white; font-family: Consolas, monospace;")
        self.input.returnPressed.connect(self.run_command)

        layout.addWidget(self.output)
        layout.addWidget(self.input)
        self.setLayout(layout)

        self.console_bridge = ConsoleBridge(self.output)
        self.channel = QWebChannel()
        self.channel.registerObject("pyConsole", self.console_bridge)
        self.web_page.setWebChannel(self.channel)

        self.web_page.loadFinished.connect(self.inject_webchannel_js)

    def inject_webchannel_js(self):
        try:
            possible_paths = [
                os.path.join(sys.prefix, "Lib", "site-packages", "PyQt6", "Qt6", "resources", "qtwebchannel", "qwebchannel.js"),
                os.path.join(sys.prefix, "Lib", "site-packages", "PyQt6", "Qt", "resources", "qtwebchannel", "qwebchannel.js"),
            ]
            qweb_js = None
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        qweb_js = f.read()
                    break

            if not qweb_js:
                raise FileNotFoundError("qwebchannel.js not found in known paths.")

            self.web_page.runJavaScript(qweb_js)

            self.web_page.runJavaScript("""
                (function() {
                    function initHook() {
                        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
                            setTimeout(initHook, 100);
                            return;
                        }
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            const pyConsole = channel.objects.pyConsole;
                            const originalLog = console.log;
                            console.log = function(...args) {
                                try {
                                    const message = args.map(a =>
                                        typeof a === 'object' ? JSON.stringify(a) : String(a)
                                    ).join(" ");
                                    pyConsole.log(message);
                                } catch (e) {}
                                originalLog.apply(console, args);
                            };
                            console.log("✅ DevConsole hook active");
                        });
                    }
                    initHook();
                })();
            """)
        except Exception as e:
            self.output.append(f'<span style="color: red;">❌ Failed to inject qwebchannel.js: {e}</span>')

    def run_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        self.output.append(f"> {cmd}")
        self.input.clear()

        def handle_result(result):
            if result is not None:
                formatted = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
                self.output.append(f"[return] {formatted}")
                self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

        try:
            self.web_page.runJavaScript(cmd, handle_result)
        except Exception as e:
            self.output.append(f'<span style="color: red;">❌ Exception: {e}</span>')

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local Storage Settings")
        self.setFixedSize(300, 150)

        self.settings = current_settings
        layout = QVBoxLayout()

        self.cors_checkbox = QCheckBox("Enable CORS Unblock")
        self.cors_checkbox.setChecked(self.settings.get("enable_cors", False))
        layout.addWidget(self.cors_checkbox)

        self.drag_checkbox = QCheckBox("Allow drag-and-drop of programs")
        self.drag_checkbox.setChecked(self.settings.get("allow_drag_programs", False))
        layout.addWidget(self.drag_checkbox)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def get_settings(self):
        return {
            "enable_cors": self.cors_checkbox.isChecked(),
            "allow_drag_programs": self.drag_checkbox.isChecked()
        }

class BrowserWindow(QMainWindow):
    def __init__(self, title: str, url: str, profile: QWebEngineProfile):
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(200, 150, 1000, 700)
        self.home_url = url

        self.browser = QWebEngineView()
        page = QWebEnginePage(profile, self)

        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.XSSAuditingEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

        self.browser.setPage(page)
        self.browser.setUrl(QUrl(url))
        self.setCentralWidget(self.browser)

        self.toolbar = QToolBar("Browser Toolbar")
        self.toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(self.toolbar)

        reload_action = QAction("Restart", self)
        reload_action.triggered.connect(self.browser.reload)
        self.toolbar.addAction(reload_action)

        dev_action = QAction("Developer Console", self)
        dev_action.triggered.connect(self.open_dev_console)
        self.toolbar.addAction(dev_action)

        tools_menu_button = QAction("Open Apps", self)
        tools_menu_button.triggered.connect(self.open_tools_menu)
        self.toolbar.addAction(tools_menu_button)

        resolution_menu_button = QAction("Resolution", self)
        resolution_menu_button.triggered.connect(self.open_resolution_menu)
        self.toolbar.addAction(resolution_menu_button)

        corsunblock_button = QAction("CORS Unblock", self)
        corsunblock_button.setCheckable(True)  
        corsunblock_button.triggered.connect(self.toggle_cors_unblock)
        self.toolbar.addAction(corsunblock_button)

        system_button = QAction("System", self)
        system_button.triggered.connect(self.open_system_menu)
        self.toolbar.addAction(system_button)

        self.profile_name = profile.persistentStoragePath().split("_")[-1]
        self.browser.page().loadFinished.connect(self.check_storage_limit)

    def check_storage_limit(self):
        name = self.profile_name
        base_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        storage_path = os.path.join(base_path, f"Profile_{name}")

        size_bytes = 0
        for root, _, files in os.walk(storage_path):
            for f in files:
                fp = os.path.join(root, f)
                size_bytes += os.path.getsize(fp)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                all_storages = json.load(f)
                data = all_storages.get(name, {})
        else:
            data = {}

        limit_enabled = data.get("limit_enabled", False)
        max_size = data.get("max_size_mb", 0)

        if limit_enabled and size_mb > max_size:
            self.browser.page().loadFinished.disconnect(self.check_storage_limit)

            html = """
            <html>
            <head><style>
                body {
                    background-color: black;
                    color: lime;
                    font-family: "Lucida Console", monospace;
                    padding: 40px;
                    font-size: 16px;
                }
                .border {
                    border: 2px solid lime;
                    padding: 20px;
                    max-width: 600px;
                    margin: auto;
                }
                h1 {
                    color: red;
                    font-size: 20px;
                }
            </style></head>
            <body>
                <div class="border">
                    <h1>*** DISK ERROR ***</h1>
                    <p>LOCAL STORAGE HAS EXCEEDED ITS MAXIMUM ALLOWED SIZE.</p>
                    <p>Please free up space or increase the size limit.</p>
                </div>
                <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
                <script>
                    document.body.addEventListener("keydown", () => {
                        if (typeof pyBridge !== "undefined") {
                            pyBridge.closeWindow();
                        }
                    });
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        window.pyBridge = channel.objects.pyBridge;
                    });
                </script>
            </body>
            </html>
            """

            bridge = CloseBridge(self)
            channel = QWebChannel()
            channel.registerObject("pyBridge", bridge)
            self.browser.page().setWebChannel(channel)

            actions_to_remove = ["System", "CORS Unblock", "Restart", "Open Apps", "Developer Console"]

            for action in self.toolbar.actions():
                if action.text() in actions_to_remove:
                    self.toolbar.removeAction(action)
            
            self.browser.setHtml(html)



    def open_system_menu(self):
        menu = QMenu(self)

        rename_action = QAction("Rename Object", self)
        rename_action.triggered.connect(self.rename_object_dialog)
        menu.addAction(rename_action)

        remove_action = QAction("Remove Object", self)
        remove_action.triggered.connect(self.remove_object_dialog)
        menu.addAction(remove_action)

        remove_action = QAction("Execute BSOD", self)
        remove_action.triggered.connect(self.bluscreen_object_dialog)
        menu.addAction(remove_action)

        button_pos = self.toolbar.mapToGlobal(QPoint(0, self.toolbar.height()))
        menu.popup(button_pos)


    def rename_object_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename Object")

        layout = QVBoxLayout(dialog)

        path_input = QLineEdit(dialog)
        path_input.setPlaceholderText("Enter object path")
        layout.addWidget(path_input)

        name_input = QLineEdit(dialog)
        name_input.setPlaceholderText("Enter new name")
        layout.addWidget(name_input)

        execute_button = QPushButton("Rename", dialog)
        layout.addWidget(execute_button)

        def on_rename():
            path = path_input.text()
            new_name = name_input.text()
            js = f'w96.FS.rename("{path}", "{new_name}")'
            self.browser.page().runJavaScript(js)
            dialog.accept()

        execute_button.clicked.connect(on_rename)
        dialog.exec()

    def bluscreen_object_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("BSOD")

        layout = QVBoxLayout(dialog)

        message_input = QLineEdit(dialog)
        message_input.setPlaceholderText("Enter BSOD message")
        layout.addWidget(message_input)

        execute_button = QPushButton("Start", dialog)
        layout.addWidget(execute_button)

        def on_rename():
            message = message_input.text()
            js = f'w96.sys.renderBSOD("{message}")'
            self.browser.page().runJavaScript(js)
            dialog.accept()

        execute_button.clicked.connect(on_rename)
        dialog.exec()

    def remove_object_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Remove Object")

        layout = QVBoxLayout(dialog)

        path_input = QLineEdit(dialog)
        path_input.setPlaceholderText("Enter object path")
        layout.addWidget(path_input)

        use_rmdir_checkbox = QCheckBox("Use rmdir", dialog)
        layout.addWidget(use_rmdir_checkbox)

        execute_button = QPushButton("Remove", dialog)
        layout.addWidget(execute_button)

        def on_remove():
            path = path_input.text()
            use_rmdir = use_rmdir_checkbox.isChecked()  
            if use_rmdir:
                js = f'w96.FS.rmdir("{path}")' 
            else:
                js = f'w96.FS.rm("{path}")' 
            self.browser.page().runJavaScript(js)
            dialog.accept()

        execute_button.clicked.connect(on_remove)
        dialog.exec()


    def load_settings():
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {"enable_cors": False, "allow_drag_programs": False}

    def save_settings(settings):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

    def toggle_cors_unblock(self, checked):
        self.corsunblock_enabled = checked

        if checked:

            def inject_js():
                js = """
                (function() {
                    if (!window._cors_patched) {
                        const originalFetch = window.fetch;
                        window.fetch = function() {
                            const args = arguments;
                            const modifiedArgs = [...args];
                            if (modifiedArgs[1]) {
                                modifiedArgs[1].mode = 'no-cors';
                            } else {
                                modifiedArgs[1] = { mode: 'no-cors' };
                            }
                            return originalFetch.apply(this, modifiedArgs);
                        };
                        window._cors_patched = true;
                        console.log('CORS Unblock simulated');
                    }
                })();
                """
                self.browser.page().runJavaScript(js)

            def on_load_finished():
                inject_js()
                self.browser.page().loadFinished.disconnect(on_load_finished)

            self.browser.page().loadFinished.connect(on_load_finished)

            if self.browser.url().toString() != "about:blank":
                inject_js()

            QMessageBox.information(self, "CORS Status", "CORS Unblock enabled. Note: This is a simulation and may not work for all requests.")

        else:
            self.browser.reload()
            QMessageBox.information(self, "CORS Status", "CORS Unblock disabled.")



    def open_resolution_menu(self):
        menu = QMenu(self)

        sizes = {
            "320x240": (320, 240),
            "640x480": (640, 480),
            "800x600": (800, 600),
            "1024x600": (1024, 600),
            "1280x720": (1280, 720),
            "1280x800": (1280, 800),
            "1366x768": (1366, 768),
            "1440x900": (1440, 900),
            "1600x900": (1600, 900),
            "1920x1080": (1920, 1080),
            "2560x1440": (2560, 1440),
            "3840x2160": (3840, 2160),
        }

        for label, (w, h) in sizes.items():
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, width=w, height=h: self.setFixedSize(width, height))
            menu.addAction(action)

        fullscreen_action = QAction("Toggle Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        menu.addAction(fullscreen_action)

        pos = self.toolbar.mapToGlobal(QPoint(80, self.toolbar.height()))
        menu.popup(pos)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def go_home(self):
        self.browser.setUrl(QUrl(self.home_url))

    def open_tools_menu(self):
        menu = QMenu(self)

        tools = {
            "Open Terminal": "terminal",
            "Open Task Manager": "taskmgr",
            "Open Explorer": "explorer",
            "Open Settings": "ctrl",
            "Open Run": "run",
        }

        for label, cmd in tools.items():
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, js_cmd=cmd: self.exec_js_command(f'w96.sys.execCmd("{js_cmd}")'))
            menu.addAction(action)

        button_pos = self.toolbar.mapToGlobal(QPoint(0, self.toolbar.height()))
        menu.popup(button_pos)

    def open_dev_console(self):
        if not hasattr(self, "dev_console") or self.dev_console is None:
            self.dev_console = DevConsole(self.browser.page())
        self.dev_console.show()
        self.dev_console.raise_()
        self.dev_console.activateWindow()

    def exec_js_command(self, js_code: str):
        try:
            self.browser.page().runJavaScript(js_code)
        except Exception as e:
            print(f"Error executing JS: {e}")


class CreateStorageDialog(QDialog):
    def __init__(self, versions):
        super().__init__()
        self.setWindowTitle("Create Windows 96 Local Storage")
        self.setMinimumSize(300, 150)
        self.form_layout = QFormLayout()
        self.setLayout(self.form_layout)

        self.name_input = QLineEdit()
        self.version_combo = QComboBox()
        self.version_combo.addItems(versions)

        self.enable_limit_checkbox = QCheckBox("Enable Max Size Limit")
        self.enable_limit_checkbox.setChecked(False)
        self.enable_limit_checkbox.toggled.connect(self.toggle_size_input)

        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText("e.g., 500 (MB)")

        self.form_layout.addRow("Storage Name:", self.name_input)
        self.form_layout.addRow("Version:", self.version_combo)
        self.form_layout.addRow(self.enable_limit_checkbox)
        self.form_layout.addRow("Max Size (MB):", self.size_input)

        self.create_btn = QPushButton("Create")
        self.create_btn.clicked.connect(self.accept)
        self.form_layout.addWidget(self.create_btn)

    def toggle_size_input(self, enabled):
        self.size_input.setVisible(enabled)
        label = self.form_layout.labelForField(self.size_input)
        if label:
            label.setVisible(enabled)

    def get_data(self):
        return (
            self.name_input.text(),
            self.version_combo.currentText(),
            self.enable_limit_checkbox.isChecked(),
            self.size_input.text()
        )


    def get_data(self):
        return (
            self.name_input.text(),
            self.version_combo.currentText(),
            self.enable_limit_checkbox.isChecked(),
            self.size_input.text()
        )




class WebLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windows 96Box")
        self.setGeometry(100, 100, 600, 400)

        self.websites = {
            "Live Version [Up-to-Date]": "https://windows96.net/",
            "Version 3.0 [Valentines Edition]": "https://rel3-wf2514.windows96.net/",
            "Version 2.0 [Service Pack 2]": "https://rel2sp2.windows96.net/",
            "Version 2.0 [Service Pack 1]": "https://rel2sp1.windows96.net/",
            "Version 2.0": "https://rel2.windows96.net/",
            "Version 1.0": "https://rel1.windows96.net/",
            "Version 0.5": "https://rel05.windows96.net/",
            "Version 0.4": "https://rel04.windows96.net/",
            "Version 0.3": "https://rel03.windows96.net/",
            "Version 0.2": "https://rel02.windows96.net/",
            "Version 0.1": "https://rel01.windows96.net/",
            "Windows 96 NTXP": "https://exp1.windows96.net/",
        }

        self.storages = self.load_storages()
        self.open_windows = []
        self.init_ui()

    def toggle_toolbar(self, checked):
        self.toolbar.setVisible(checked)


    def show_info(self, item):
        name = item.text()
        data = self.storages.get(name, {})
        base_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        storage_path = os.path.join(base_path, f"Profile_{name}")

        size_bytes = 0
        for root, _, files in os.walk(storage_path):
            for f in files:
                fp = os.path.join(root, f)
                size_bytes += os.path.getsize(fp)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        info_text = (
            f"Name: {name}\n"
            f"Created: {data.get('created', 'Unknown')}\n"
            f"Last Launched: {data.get('last_launched', 'Never')}\n"
            f"Size: {size_mb} MB"
        )

        limit_enabled = data.get("limit_enabled", False)
        info_text += f"\nLimit Enabled: {'Yes' if limit_enabled else 'No'}"

        if limit_enabled and "max_size_mb" in data:
            info_text += f"\nMax Allowed Size: {data['max_size_mb']} MB"
            if size_mb > data["max_size_mb"]:
                info_text += f"\n⚠️ Warning: Exceeds limit!"

        QMessageBox.information(self, f"Storage Info - {name}", info_text)




    def create_profile(self, name):
        base_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        storage_path = os.path.join(base_path, f"Profile_{name}")
        os.makedirs(storage_path, exist_ok=True)

        profile = QWebEngineProfile(f"Windows96Profile_{name}", self)
        profile.setPersistentStoragePath(storage_path)
        profile.setCachePath(storage_path)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        return profile

    def load_storages(self):
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_storages(self):
        with open(STORAGE_FILE, "w") as f:
            json.dump(self.storages, f)

    def init_ui(self):
        main_layout = QHBoxLayout()
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(20, 20, 20, 20)
        sidebar.setSpacing(15)

        list_group = QGroupBox("Local Storage Instances")
        list_layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.setStyleSheet("background-color: #1e1e1e; color: white;")
        list_layout.addWidget(self.list_widget)
        list_group.setLayout(list_layout)

        sidebar.addWidget(list_group)

        button_style = """
            QPushButton {
                background-color: #0078d7;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #005ea6;
            }
        """

        self.launch_btn = QPushButton("Launch")
        self.launch_btn.setStyleSheet(button_style)
        self.launch_btn.setMinimumHeight(40)
        self.launch_btn.clicked.connect(self.launch_website)
        sidebar.addWidget(self.launch_btn)

        self.local_storage_btn = QPushButton("Create New Storage")
        self.local_storage_btn.setStyleSheet(button_style)
        self.local_storage_btn.setMinimumHeight(40)
        self.local_storage_btn.clicked.connect(self.create_local_storage)
        sidebar.addWidget(self.local_storage_btn)

        sidebar.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        container = QWidget()
        main_layout.addLayout(sidebar, stretch=1)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        for name, data in self.storages.items():
            if isinstance(data, dict) and "version" in data and "created" in data:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setFont(QFont("Segoe UI", 10))
                item.setForeground(QColor("white"))
                self.list_widget.addItem(item)


    def show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if item:
            menu = QMenu()
            delete_action = menu.addAction("Delete")
            rename_action = menu.addAction("Rename")
            info_action = menu.addAction("Info")
            action = menu.exec(self.list_widget.mapToGlobal(position))
            if action == info_action:
                self.show_info(item)
            elif action == rename_action:
                self.rename_storage(item)
            elif action == delete_action:
                self.delete_storage(item)


    def delete_storage(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        if name in self.storages:
            confirm = QMessageBox.question(
                self,
                "Confirm Deletion",
                "Are you sure you wanna delete this storage?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                del self.storages[name]
                self.save_storages()
                self.list_widget.takeItem(self.list_widget.row(item))

                base_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
                storage_path = os.path.join(base_path, f"Profile_{name}")
                if os.path.exists(storage_path):
                    try:
                        import shutil
                        shutil.rmtree(storage_path)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to delete storage files: {e}")


    def rename_storage(self, item):
        old_name = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename Storage", "Enter new name:", text=old_name)
        if ok and new_name and new_name != old_name and new_name not in self.storages:
            self.storages[new_name] = self.storages.pop(old_name)
            self.save_storages()
            display = f"{new_name}\n(v: {self.storages[new_name]['version']}, created: {self.storages[new_name]['created']})"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, new_name)

    def launch_website(self):   
        selected = self.list_widget.currentItem()
        if selected:
            name = selected.data(Qt.ItemDataRole.UserRole)
            data = self.storages.get(name)
            if data:
                self.storages[name]["last_launched"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_storages()

                base_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
                storage_path = os.path.join(base_path, f"Profile_{name}")

                size_bytes = 0
                for root, _, files in os.walk(storage_path):
                    for f in files:
                        fp = os.path.join(root, f)
                        size_bytes += os.path.getsize(fp)
                size_mb = round(size_bytes / (1024 * 1024), 2)

                limit_enabled = data.get("limit_enabled", False)
                max_size = data.get("max_size_mb", 0)

                profile = self.create_profile(name)

                if limit_enabled and size_mb > max_size:
                    html = """
                    <html>
                    <head><style>
                        body {
                            background-color: black;
                            color: lime;
                            font-family: "Lucida Console", monospace;
                            padding: 40px;
                            font-size: 16px;
                        }
                        .border {
                            border: 2px solid lime;
                            padding: 20px;
                            max-width: 600px;
                            margin: auto;
                        }
                        h1 {
                            color: red;
                            font-size: 20px;
                        }
                    </style></head>
                    <body>
                        <div class="border">
                            <h1>*** DISK ERROR ***</h1>
                            <p>LOCAL STORAGE HAS EXCEEDED ITS MAXIMUM ALLOWED SIZE.</p>
                            <p>Please free up space or increase the size limit.</p>
                        </div>
                        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
                        <script>
                            document.body.addEventListener("keydown", () => {
                                if (typeof pyBridge !== "undefined") {
                                    pyBridge.closeWindow();
                                }
                            });
                        </script>
                    </body>
                    </html>
                    """
                    browser_window = BrowserWindow(f"Storage Full - {name}", "about:blank", profile)
                    browser_window.browser.setHtml(html)
                    bridge = CloseBridge(browser_window)
                    channel = QWebChannel()
                    channel.registerObject("pyBridge", bridge)
                    browser_window.browser.page().setWebChannel(channel)

                    browser_window.browser.page().runJavaScript("""
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            window.pyBridge = channel.objects.pyBridge;
                        });
                    """)
                    browser_window.show()
                    self.open_windows.append(browser_window)
                    return

                url = self.websites.get(data["version"])
                if url:
                    browser_window = BrowserWindow(f"{data['version']} ({name})", url, profile)
                    browser_window.show()
                    self.open_windows.append(browser_window)



    def create_local_storage(self):
        dialog = CreateStorageDialog(self.websites.keys())
        if dialog.exec():
            name, version, enable_limit, max_size = dialog.get_data()
            if not name.strip():
                QMessageBox.warning(self, "Invalid Name", "Storage name cannot be empty.")
                return
            if name in self.storages:
                QMessageBox.warning(self, "Duplicate Name", "Storage with this name already exists.")
                return

            entry = {
                "version": version,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            if enable_limit:
                try:
                    size_limit = int(max_size)
                    entry["limit_enabled"] = True
                    entry["max_size_mb"] = size_limit
                except ValueError:
                    QMessageBox.warning(self, "Invalid Size", "Please enter a valid number for max size.")
                    return
            else:
                entry["limit_enabled"] = False

            self.storages[name] = entry
            self.save_storages()

            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFont(QFont("Arial", 10))
            item.setForeground(QColor("white"))
            self.list_widget.addItem(item)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = WebLauncher()
    launcher.show()
    sys.exit(app.exec())
