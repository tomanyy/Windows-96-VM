import sys
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QToolBar, QMenu,
    QMessageBox, QLineEdit, QPushButton, QComboBox,
    QDialog, QVBoxLayout as QVBoxDialogLayout, QFormLayout, QTextEdit, QInputDialog, QListWidgetItem
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, QStandardPaths, QSize, QPoint, Qt
from PyQt6.QtGui import QAction, QFont, QColor

STORAGE_FILE = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation), "storages.json")

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

    def run_command(self):
        cmd = self.input.text()
        if cmd.strip() == "":
            return
        self.output.append(f"> {cmd}")
        self.input.clear()

        def handle_result(result):
            self.output.append(str(result))

        def handle_error(_):
            self.output.append("Error running command.")

        try:
            self.web_page.runJavaScript(cmd, handle_result)
        except Exception as e:
            self.output.append(f"Exception: {e}")


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
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)

        self.browser.setPage(page)
        self.browser.setUrl(QUrl(url))
        self.setCentralWidget(self.browser)

        self.toolbar = QToolBar("Browser Toolbar")
        self.toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(self.toolbar)

        reload_action = QAction("Restart", self)
        reload_action.triggered.connect(self.browser.reload)
        self.toolbar.addAction(reload_action)

        dev_action = QAction("Dev Console", self)
        dev_action.triggered.connect(self.open_dev_console)
        self.toolbar.addAction(dev_action)

        tools_menu_button = QAction("Open Apps", self)
        tools_menu_button.triggered.connect(self.open_tools_menu)
        self.toolbar.addAction(tools_menu_button)

        resolution_menu_button = QAction("Resolution", self)
        resolution_menu_button.triggered.connect(self.open_resolution_menu)
        self.toolbar.addAction(resolution_menu_button)




    def open_resolution_menu(self):
        menu = QMenu(self)

        sizes = {
            "800x400": (800, 400),
            "1024x768": (1024, 768),
            "1280x720": (1280, 720),
            "1920x1080": (1920, 1080),
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
        layout = QFormLayout()

        self.name_input = QLineEdit()
        self.version_combo = QComboBox()
        self.version_combo.addItems(versions)

        layout.addRow("Storage Name:", self.name_input)
        layout.addRow("Version:", self.version_combo)

        self.create_btn = QPushButton("Create")
        self.create_btn.clicked.connect(self.accept)
        layout.addWidget(self.create_btn)

        self.setLayout(layout)

    def get_data(self):
        return self.name_input.text(), self.version_combo.currentText()


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

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        sidebar.addWidget(QLabel("Created Local Storages"))
        sidebar.addWidget(self.list_widget)

        self.launch_btn = QPushButton("Launch Windows 96")
        self.launch_btn.setMinimumHeight(40)
        self.launch_btn.clicked.connect(self.launch_website)
        sidebar.addWidget(self.launch_btn)

        self.local_storage_btn = QPushButton("Create Local Storage Instance")
        self.local_storage_btn.setMinimumHeight(40)
        self.local_storage_btn.clicked.connect(self.create_local_storage)
        sidebar.addWidget(self.local_storage_btn)

        container = QWidget()
        main_layout.addLayout(sidebar)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        for name, data in self.storages.items():
            if isinstance(data, dict) and "version" in data and "created" in data:
                display = name
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setFont(QFont("Arial", 10))
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
                # Remove storage metadata
                del self.storages[name]
                self.save_storages()
                self.list_widget.takeItem(self.list_widget.row(item))

                # Delete associated local storage directory
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
                url = self.websites.get(data["version"])
                self.storages[name]["last_launched"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_storages()

                if url:
                    profile = self.create_profile(name)
                    browser_window = BrowserWindow(f"{data['version']} ({name})", url, profile)
                    browser_window.show()
                    self.open_windows.append(browser_window)

    def create_local_storage(self):
        dialog = CreateStorageDialog(self.websites.keys())
        if dialog.exec():
            name, version = dialog.get_data()
            if not name.strip():
                QMessageBox.warning(self, "Invalid Name", "Storage name cannot be empty.")
                return
            if name in self.storages:
                QMessageBox.warning(self, "Duplicate Name", "Storage with this name already exists.")
                return
            self.storages[name] = {
                "version": version,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save_storages()
            display = name
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFont(QFont("Arial", 10))
            item.setForeground(QColor("white"))
            self.list_widget.addItem(item)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = WebLauncher()
    launcher.show()
    sys.exit(app.exec())
