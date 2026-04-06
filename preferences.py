import json
import os

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QGroupBox, QRadioButton, QPushButton)

PREFS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preferences.json")

DEFAULT_PREFS = {
    "comparison_method": "name_size"   # "name_size" or "checksum"
}


def load_prefs():
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, encoding="utf-8") as f:
                prefs = json.load(f)
            for key, val in DEFAULT_PREFS.items():
                prefs.setdefault(key, val)
            return prefs
        except Exception as e:
            print(f"Error loading preferences: {e}")
    return DEFAULT_PREFS.copy()


def save_prefs(prefs):
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving preferences: {e}")


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(380)
        self.prefs = load_prefs()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Méthode d'identification des doublons")
        group_layout = QVBoxLayout(group)

        self.radio_name_size = QRadioButton("Nom + Taille  (rapide)")
        self.radio_checksum = QRadioButton("Contenu / Checksum SHA-256  (fiable, plus lent)")

        if self.prefs.get("comparison_method") == "checksum":
            self.radio_checksum.setChecked(True)
        else:
            self.radio_name_size.setChecked(True)

        group_layout.addWidget(self.radio_name_size)
        group_layout.addWidget(self.radio_checksum)
        layout.addWidget(group)

        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(self.save_and_close)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def save_and_close(self):
        self.prefs["comparison_method"] = (
            "checksum" if self.radio_checksum.isChecked() else "name_size"
        )
        save_prefs(self.prefs)
        self.accept()
