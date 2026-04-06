import os
import shutil

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QLabel, QProgressBar,
                             QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt

from utils import calculate_sha256, format_size
from preferences import load_prefs


class CopyNoDupeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Copie sans doublons — DupeSorcerer")
        self.setMinimumSize(700, 500)
        self.source_folder = ""
        self.dest_folder = ""
        self.to_copy = []
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Source folder
        src_layout = QHBoxLayout()
        self.src_label = QLabel("Source (A): aucun dossier sélectionné")
        src_btn = QPushButton("Choisir dossier source (A)")
        src_btn.clicked.connect(self.select_source)
        src_layout.addWidget(self.src_label, 1)
        src_layout.addWidget(src_btn)
        layout.addLayout(src_layout)

        # Destination folder
        dst_layout = QHBoxLayout()
        self.dst_label = QLabel("Destination (B): aucun dossier sélectionné")
        dst_btn = QPushButton("Choisir dossier destination (B)")
        dst_btn.clicked.connect(self.select_dest)
        dst_layout.addWidget(self.dst_label, 1)
        dst_layout.addWidget(dst_btn)
        layout.addLayout(dst_layout)

        # Method info
        self.method_label = QLabel("")
        self.method_label.setStyleSheet("color: gray;")
        layout.addWidget(self.method_label)

        # Analyze button
        self.analyze_btn = QPushButton("Analyser")
        self.analyze_btn.clicked.connect(self.analyze)
        layout.addWidget(self.analyze_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Log / results area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copier les fichiers manquants vers B")
        self.copy_btn.clicked.connect(self.do_copy)
        self.copy_btn.setVisible(False)
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self._refresh_method_label()

    def _refresh_method_label(self):
        prefs = load_prefs()
        method = prefs.get("comparison_method", "name_size")
        label = "checksum SHA-256" if method == "checksum" else "nom + taille"
        self.method_label.setText(f"Méthode d'identification : {label}  (modifiable dans Paramètres)")

    def select_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Dossier source (A) — fichiers à copier")
        if folder:
            self.source_folder = folder
            self.src_label.setText(f"Source (A): {folder}")
            self._reset_results()

    def select_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Dossier destination (B) — cible")
        if folder:
            self.dest_folder = folder
            self.dst_label.setText(f"Destination (B): {folder}")
            self._reset_results()

    def _reset_results(self):
        self.to_copy = []
        self.copy_btn.setVisible(False)
        self.log_text.clear()

    def analyze(self):
        if not self.source_folder or not self.dest_folder:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner les deux dossiers.")
            return
        if os.path.abspath(self.source_folder) == os.path.abspath(self.dest_folder):
            QMessageBox.warning(self, "Attention", "Les dossiers source et destination sont identiques.")
            return

        self._refresh_method_label()
        prefs = load_prefs()
        use_checksum = prefs.get("comparison_method") == "checksum"

        self.log_text.clear()
        self._reset_results()
        self.analyze_btn.setEnabled(False)

        # --- Scan destination ---
        self.log_text.append("<b>Scan du dossier destination (B)…</b>")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # indeterminate spinner
        QApplication.processEvents()

        dest_keys = set()
        dest_file_count = 0
        try:
            for root, _, files in os.walk(self.dest_folder):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        if use_checksum:
                            key = calculate_sha256(fpath)
                        else:
                            key = (fname, os.path.getsize(fpath))
                        if key:
                            dest_keys.add(key)
                            dest_file_count += 1
                    except OSError:
                        pass
                QApplication.processEvents()
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de parcourir la destination: {e}")
            self._finish_analyze()
            return

        self.log_text.append(f"{dest_file_count} fichier(s) indexé(s) dans la destination.")

        # --- Scan source ---
        self.log_text.append("<b>Scan du dossier source (A)…</b>")
        QApplication.processEvents()

        src_files = []
        try:
            for root, _, files in os.walk(self.source_folder):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        src_files.append((fpath, fname, os.path.getsize(fpath)))
                    except OSError:
                        pass
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de parcourir la source: {e}")
            self._finish_analyze()
            return

        self.progress_bar.setMaximum(len(src_files))
        self.progress_bar.setValue(0)

        already_present = 0
        for i, (fpath, fname, fsize) in enumerate(src_files):
            try:
                key = calculate_sha256(fpath) if use_checksum else (fname, fsize)
                if key and key not in dest_keys:
                    self.to_copy.append(fpath)
                else:
                    already_present += 1
            except OSError:
                pass
            self.progress_bar.setValue(i + 1)
            if i % 50 == 0:
                QApplication.processEvents()

        # --- Results ---
        self.log_text.append(f"\n<b>Résultat :</b>")
        self.log_text.append(f"  {already_present} fichier(s) déjà présent(s) dans la destination — ignoré(s).")
        self.log_text.append(f"  {len(self.to_copy)} fichier(s) à copier.")

        if self.to_copy:
            total_size = sum(os.path.getsize(p) for p in self.to_copy if os.path.exists(p))
            self.log_text.append(f"  Taille totale à copier : {format_size(total_size)}")
            self.log_text.append("\n<b>Fichiers à copier :</b>")
            for p in self.to_copy:
                self.log_text.append(f"  {p}")
            self.copy_btn.setVisible(True)
        else:
            self.log_text.append("\nAucun fichier à copier — la destination est déjà à jour.")

        self._finish_analyze()

    def _finish_analyze(self):
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)

    def do_copy(self):
        if not self.to_copy:
            return

        total_size = sum(os.path.getsize(p) for p in self.to_copy if os.path.exists(p))
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Copier {len(self.to_copy)} fichier(s) ({format_size(total_size)}) vers :\n{self.dest_folder} ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.copy_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.to_copy))
        self.progress_bar.setValue(0)
        self.log_text.append("\n<b>Copie en cours…</b>")

        copied = 0
        errors = 0
        for i, src_path in enumerate(self.to_copy):
            fname = os.path.basename(src_path)
            dst_path = os.path.join(self.dest_folder, fname)

            # Resolve filename collision (different content, same name)
            if os.path.exists(dst_path):
                base, ext = os.path.splitext(fname)
                counter = 1
                while os.path.exists(dst_path):
                    dst_path = os.path.join(self.dest_folder, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.copy2(src_path, dst_path)
                self.log_text.append(f"Copié : {src_path}  →  {os.path.basename(dst_path)}")
                copied += 1
            except OSError as e:
                self.log_text.append(f"<font color='red'>Erreur : {src_path} — {e}</font>")
                errors += 1

            self.progress_bar.setValue(i + 1)
            if i % 10 == 0:
                QApplication.processEvents()

        self.progress_bar.setVisible(False)
        self.log_text.append(
            f"\n<b>{copied} fichier(s) copié(s)"
            + (f", {errors} erreur(s)." if errors else ".")
            + "</b>"
        )
        self.copy_btn.setEnabled(True)
        self.copy_btn.setVisible(False)
        self.to_copy = []
