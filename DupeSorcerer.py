import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QAction
from PyQt5.QtCore import Qt

from duplicate_cleaner import DuplicateFilesManager
from copy_no_dupe import CopyNoDupeWindow
from preferences import PreferencesDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DupeSorcerer")
        self.setMinimumSize(480, 260)
        self._open_windows = []  # keep references to prevent garbage collection

        menubar = self.menuBar()
        actions_menu = menubar.addMenu("Actions")

        copy_action = QAction("Copie sans doublons", self)
        copy_action.triggered.connect(self.open_copy_no_dupe)
        actions_menu.addAction(copy_action)

        clean_action = QAction("Nettoyer les doublons", self)
        clean_action.triggered.connect(self.open_duplicate_cleaner)
        actions_menu.addAction(clean_action)

        actions_menu.addSeparator()

        prefs_action = QAction("Paramètres", self)
        prefs_action.triggered.connect(self.open_preferences)
        actions_menu.addAction(prefs_action)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        title = QLabel("DupeSorcerer")
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("Gestionnaire de doublons pour grandes collections de fichiers")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        hint = QLabel("Utilisez le menu <b>Actions</b> pour commencer.")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def open_duplicate_cleaner(self):
        win = DuplicateFilesManager()
        self._open_windows.append(win)
        win.show()

    def open_copy_no_dupe(self):
        win = CopyNoDupeWindow()
        self._open_windows.append(win)
        win.show()

    def open_preferences(self):
        dialog = PreferencesDialog(self)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
