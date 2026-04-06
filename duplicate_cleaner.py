import os
import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QLabel,
                             QScrollArea, QFrame, QMessageBox, QProgressBar, QTextEdit, QDialog,
                             QCheckBox, QButtonGroup, QRadioButton)
from PyQt5.QtCore import Qt

from utils import calculate_sha256, format_size, clear_layout
from preferences import load_prefs


class DuplicateFile:
    def __init__(self, name, size, file_hash=None):
        self.name = name
        self.size = size
        self.hash = file_hash
        self.paths = []
        self.keep = []


class DoublonFolder:
    def __init__(self, path):
        self.path = path
        self.duplicate_count = 0
        self.todo = 1  # 1=Ne rien faire, 2=Effacer, 3=Garder


class DuplicateFilesManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nettoyer les doublons — DupeSorcerer")
        self.setMinimumSize(800, 600)

        self.duplicate_files = []
        self.doublon_folders = []
        self.folder_path = ""
        self.current_folder_index = 0
        self.behaviors = []
        self.log_file = None
        self.test_content = False  # set from prefs at analysis time

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        select_layout = QHBoxLayout()
        self.path_label = QLabel("Aucun dossier sélectionné")
        self.select_button = QPushButton("Sélectionner un dossier")
        self.select_button.clicked.connect(self.select_folder)
        select_layout.addWidget(self.path_label, 1)
        select_layout.addWidget(self.select_button)
        main_layout.addLayout(select_layout)

        self.analyze_button = QPushButton("Analyser les doublons")
        self.analyze_button.clicked.connect(self.analyze_duplicates)
        main_layout.addWidget(self.analyze_button)

        self.detection_label = QLabel("Détection en cours...")
        self.detection_label.setVisible(False)
        main_layout.addWidget(self.detection_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.review_label = QLabel("Revue des dossiers:")
        self.review_label.setVisible(False)
        main_layout.addWidget(self.review_label)

        self.review_progress_bar = QProgressBar()
        self.review_progress_bar.setVisible(False)
        self.review_progress_bar.setTextVisible(True)
        main_layout.addWidget(self.review_progress_bar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area, 1)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.content_widget)

        self.folders_widget = QWidget()
        self.folders_layout = QVBoxLayout(self.folders_widget)
        self.folders_layout.setAlignment(Qt.AlignTop)
        self.content_layout.addWidget(self.folders_widget)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setVisible(False)
        self.content_layout.addWidget(self.log_text)

        self.buttons_layout = QHBoxLayout()

        self.ok_button = QPushButton("Suivant")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.process_folder_choice)
        self.ok_button.setVisible(False)

        self.cancel_button = QPushButton("Tout Passer")
        self.cancel_button.setToolTip("Passer la revue de tous les dossiers restants et aller à la confirmation.")
        self.cancel_button.clicked.connect(self.cancel_process)
        self.cancel_button.setVisible(False)

        self.process_now_button = QPushButton("Tout Traiter")
        self.process_now_button.setToolTip("Marquer tous les dossiers pour suppression (sauf protection) et aller à la confirmation.")
        self.process_now_button.clicked.connect(self.process_now)
        self.process_now_button.setVisible(False)

        self.delete_button = QPushButton("Confirmer Suppression")
        self.delete_button.clicked.connect(self.start_deletion)
        self.delete_button.setVisible(False)

        self.final_cancel_button = QPushButton("Annuler / Fermer")
        self.final_cancel_button.clicked.connect(self.close)
        self.final_cancel_button.setVisible(True)

        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.buttons_layout.addWidget(self.process_now_button)
        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.delete_button)
        self.buttons_layout.addWidget(self.final_cancel_button)

        main_layout.addLayout(self.buttons_layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier racine")
        if folder:
            self.folder_path = folder
            self.path_label.setText(f"Dossier: {folder}")
            self.analyze_button.setVisible(True)
            self.select_button.setVisible(True)
            self.ok_button.setVisible(False)
            self.cancel_button.setVisible(False)
            self.process_now_button.setVisible(False)
            self.delete_button.setVisible(False)
            self.review_label.setVisible(False)
            self.review_progress_bar.setVisible(False)
            self.log_text.setVisible(False)
            self.folders_widget.setVisible(True)
            clear_layout(self.folders_layout)
            self.log_text.clear()

    def analyze_duplicates(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Attention", "Veuillez d'abord sélectionner un dossier.")
            return

        # Read comparison method from preferences at analysis time
        prefs = load_prefs()
        self.test_content = prefs.get("comparison_method") == "checksum"

        self.analyze_button.setEnabled(False)
        self.select_button.setVisible(False)
        clear_layout(self.folders_layout)
        self.log_text.setVisible(False)
        self.folders_widget.setVisible(True)

        self.duplicate_files = []
        self.doublon_folders = []
        self.behaviors = []

        self.detection_label.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Recherche fichiers: %v/%m")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        all_file_details = []
        total_files = 0

        try:
            for root, _, files in os.walk(self.folder_path):
                if not files:
                    continue
                for file_name in files:
                    try:
                        file_path = os.path.join(root, file_name)
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path)
                            all_file_details.append((file_path, file_name, file_size))
                            total_files += 1
                    except OSError as e:
                        print(f"Warning: Cannot access file info {file_path}: {e}")
                    except Exception as e:
                        print(f"Unexpected error accessing file info {file_path}: {e}")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de parcourir le dossier: {e}")
            self.reset_ui_after_analysis_error()
            return
        except Exception as e:
            QMessageBox.critical(self, "Erreur Inattendue", f"Erreur lors de la recherche de fichiers: {e}")
            self.reset_ui_after_analysis_error()
            return

        if not all_file_details:
            QMessageBox.information(self, "Information", "Aucun fichier accessible trouvé dans le dossier sélectionné.")
            self.reset_ui_after_analysis_error()
            return

        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setFormat(f"Analyse ({'Hash' if self.test_content else 'Nom+Taille'}): %v/%m")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        file_dict = {}

        for i, (file_path, file_name, file_size) in enumerate(all_file_details):
            key = None
            current_hash = None

            try:
                if self.test_content:
                    current_hash = calculate_sha256(file_path)
                    if current_hash:
                        key = current_hash
                else:
                    key = (file_name, file_size)

                if key:
                    if key not in file_dict:
                        file_dict[key] = {'paths': [], 'name': file_name, 'size': file_size, 'hash': current_hash}
                    file_dict[key]['paths'].append(file_path)

            except Exception as e:
                print(f"Unexpected error processing file {file_path}: {e}")

            self.progress_bar.setValue(i + 1)
            if i % 50 == 0:
                QApplication.processEvents()

        QApplication.processEvents()

        for key, data in file_dict.items():
            if len(data['paths']) > 1:
                duplicate = DuplicateFile(data['name'], data['size'], data['hash'])
                duplicate.paths = data['paths']
                duplicate.keep = [1] * len(data['paths'])
                self.duplicate_files.append(duplicate)

        folder_dict = {}
        for duplicate in self.duplicate_files:
            for path in duplicate.paths:
                folder = os.path.dirname(path)
                folder_dict[folder] = folder_dict.get(folder, 0) + 1

        self.doublon_folders = []
        for folder_path, count in folder_dict.items():
            doublon_folder = DoublonFolder(folder_path)
            doublon_folder.duplicate_count = count
            self.doublon_folders.append(doublon_folder)

        self.doublon_folders.sort(key=lambda x: x.duplicate_count, reverse=True)

        self.progress_bar.setVisible(False)
        self.detection_label.setVisible(False)
        self.analyze_button.setEnabled(True)

        if self.doublon_folders:
            self.analyze_button.setVisible(False)
            self.review_label.setVisible(True)
            self.review_progress_bar.setVisible(True)
            self.review_progress_bar.setMaximum(len(self.doublon_folders))
            self.review_progress_bar.setFormat("Dossier %v / %m")
            self.review_progress_bar.setValue(0)
            self.ok_button.setVisible(True)
            self.cancel_button.setVisible(True)
            self.process_now_button.setVisible(True)
            self.delete_button.setVisible(False)
            self.current_folder_index = 0
            self.show_current_folder()
        else:
            QMessageBox.information(self, "Information", "Aucun doublon trouvé.")
            self.reset_ui_after_analysis_error()

    def reset_ui_after_analysis_error(self):
        self.select_button.setVisible(True)
        self.analyze_button.setVisible(True)
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.detection_label.setVisible(False)
        self.review_label.setVisible(False)
        self.review_progress_bar.setVisible(False)
        self.ok_button.setVisible(False)
        self.cancel_button.setVisible(False)
        self.process_now_button.setVisible(False)
        self.delete_button.setVisible(False)

    def show_current_folder(self):
        clear_layout(self.folders_layout)
        self.review_progress_bar.setValue(self.current_folder_index + 1)

        if self.current_folder_index >= len(self.doublon_folders):
            print("Warning: show_current_folder called out of bounds.")
            self.show_deletion_confirmation()
            return

        current_folder_obj = self.doublon_folders[self.current_folder_index]

        self.folders_layout.addWidget(QLabel(f"<b>Dossier actuel ({current_folder_obj.duplicate_count} doublons):</b>"))
        self.add_folder_choice(current_folder_obj)

        related_folder_objects = set()

        for duplicate in self.duplicate_files:
            in_current_folder = any(os.path.dirname(path) == current_folder_obj.path for path in duplicate.paths)
            if in_current_folder:
                for path in duplicate.paths:
                    folder_path = os.path.dirname(path)
                    if folder_path != current_folder_obj.path:
                        related_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                        if related_obj:
                            related_folder_objects.add(related_obj)

        if related_folder_objects:
            self.folders_layout.addWidget(QLabel("<b>Dossiers liés (non traités):</b>"))
            sorted_related_folders = sorted(list(related_folder_objects), key=lambda f: f.path)
            for folder_obj in sorted_related_folders:
                self.add_folder_choice(folder_obj)

        self.ok_button.setFocus()

    def add_folder_choice(self, folder_obj):
        folder_frame = QFrame()
        folder_frame.setFrameShape(QFrame.StyledPanel)
        folder_layout = QVBoxLayout(folder_frame)

        folder_layout.addWidget(QLabel(f"{folder_obj.path} ({folder_obj.duplicate_count} doublons)"))

        radio_layout = QHBoxLayout()
        radio_group = QButtonGroup(folder_frame)
        radio_group.setProperty("folder_object", folder_obj)

        radio1 = QRadioButton("Ne rien faire")
        radio2 = QRadioButton("Effacer")
        radio3 = QRadioButton("Garder")
        radio_group.addButton(radio1, 1)
        radio_group.addButton(radio2, 2)
        radio_group.addButton(radio3, 3)

        current_todo = folder_obj.todo
        if current_todo == 1:
            radio1.setChecked(True)
        elif current_todo == 2:
            radio2.setChecked(True)
        elif current_todo == 3:
            radio3.setChecked(True)
        else:
            radio1.setChecked(True)
            folder_obj.todo = 1

        radio_layout.addWidget(radio1)
        radio_layout.addWidget(radio2)
        radio_layout.addWidget(radio3)
        folder_layout.addLayout(radio_layout)

        self.folders_layout.addWidget(folder_frame)

    def process_folder_choice(self):
        for i in range(self.folders_layout.count()):
            widget = self.folders_layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                button_group = widget.findChild(QButtonGroup)
                if button_group:
                    folder_obj = button_group.property("folder_object")
                    if folder_obj:
                        choice = button_group.checkedId()
                        folder_obj.todo = choice

        self.current_folder_index += 1

        while self.current_folder_index < len(self.doublon_folders):
            next_folder_obj = self.doublon_folders[self.current_folder_index]

            related_folders_for_next = set()
            for duplicate in self.duplicate_files:
                in_next_folder = any(os.path.dirname(p) == next_folder_obj.path for p in duplicate.paths)
                if in_next_folder:
                    for path in duplicate.paths:
                        folder_path = os.path.dirname(path)
                        related_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                        if related_obj:
                            related_folders_for_next.add(related_obj)

            all_processed = all(folder.todo != 1 for folder in related_folders_for_next)

            if all_processed:
                self.current_folder_index += 1
            else:
                break

        if self.current_folder_index < len(self.doublon_folders):
            self.show_current_folder()
        else:
            self.show_deletion_confirmation()

    def cancel_process(self):
        reply = QMessageBox.question(self, "Confirmation",
                                     "Passer la revue de tous les dossiers restants et aller à la confirmation?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_folder_index = len(self.doublon_folders)
            self.show_deletion_confirmation()

    def process_now(self):
        reply = QMessageBox.question(self, "Confirmation",
                                     "Marquer tous les dossiers pour suppression (sauf ceux marqués 'Garder') et aller à la confirmation?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for folder in self.doublon_folders:
                if folder.todo != 3:
                    folder.todo = 2
            self.current_folder_index = len(self.doublon_folders)
            self.show_deletion_confirmation()

    def show_deletion_confirmation(self):
        self.ok_button.setVisible(False)
        self.cancel_button.setVisible(False)
        self.process_now_button.setVisible(False)
        self.review_label.setVisible(False)
        self.review_progress_bar.setVisible(False)

        self.delete_button.setVisible(True)
        self.final_cancel_button.setText("Annuler")

        clear_layout(self.folders_layout)
        self.log_text.setVisible(False)
        self.folders_widget.setVisible(True)

        folders_to_delete = [f for f in self.doublon_folders if f.todo == 2]
        folders_to_keep = [f for f in self.doublon_folders if f.todo == 3]
        folders_ignored = [f for f in self.doublon_folders if f.todo == 1]

        files_to_delete_count = 0
        files_to_keep_count = 0
        potential_last_copy_issues = 0

        temp_keep_lists = {}
        for duplicate in self.duplicate_files:
            keep_list = [1] * len(duplicate.paths)
            for i, path in enumerate(duplicate.paths):
                folder_path = os.path.dirname(path)
                folder_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                if folder_obj:
                    if folder_obj.todo == 2:
                        keep_list[i] = 0
                    elif folder_obj.todo == 3:
                        keep_list[i] = 1

            if all(k == 0 for k in keep_list) and len(keep_list) > 0:
                potential_last_copy_issues += 1
                keep_list[0] = 1

            temp_keep_lists[duplicate] = keep_list
            files_to_delete_count += keep_list.count(0)
            files_to_keep_count += keep_list.count(1)

        self.folders_layout.addWidget(QLabel("<b>Récapitulatif des actions prévues:</b>"))

        if folders_to_delete:
            self.folders_layout.addWidget(QLabel("\nDossiers où les doublons seront supprimés:"))
            for folder in folders_to_delete:
                self.folders_layout.addWidget(QLabel(f"- {folder.path}"))
        if folders_to_keep:
            self.folders_layout.addWidget(QLabel("\nDossiers où les doublons seront conservés:"))
            for folder in folders_to_keep:
                self.folders_layout.addWidget(QLabel(f"- {folder.path}"))
        if folders_ignored:
            self.folders_layout.addWidget(QLabel("\nDossiers où les doublons seront ignorés:"))
            for folder in folders_ignored:
                self.folders_layout.addWidget(QLabel(f"- {folder.path}"))

        self.folders_layout.addWidget(QLabel(f"\nTotal fichiers à supprimer: env. {files_to_delete_count}"))
        self.folders_layout.addWidget(QLabel(f"Total fichiers à conserver: env. {files_to_keep_count}"))

        if potential_last_copy_issues > 0:
            warning_label = QLabel(
                f"<font color='orange'>Attention: {potential_last_copy_issues} groupe(s) de doublons "
                f"n'ont de copies que dans des dossiers marqués 'Effacer'. "
                f"Vous devrez choisir quelle copie conserver lors de la suppression.</font>"
            )
            warning_label.setWordWrap(True)
            self.folders_layout.addWidget(warning_label)

        if files_to_delete_count == 0 and potential_last_copy_issues == 0:
            self.delete_button.setEnabled(False)
            self.folders_layout.addWidget(QLabel("\nAucun fichier à supprimer."))
        else:
            self.delete_button.setEnabled(True)

    def start_deletion(self):
        folder_choices = {folder.path: folder.todo for folder in self.doublon_folders}
        final_keep_lists = {}

        for duplicate in self.duplicate_files:
            keep_list = [1] * len(duplicate.paths)
            for i, path in enumerate(duplicate.paths):
                folder_path = os.path.dirname(path)
                choice = folder_choices.get(folder_path, 1)
                if choice == 2:
                    keep_list[i] = 0
                elif choice == 3:
                    keep_list[i] = 1
            final_keep_lists[duplicate] = keep_list

        actual_files_to_delete = sum(lst.count(0) for lst in final_keep_lists.values())
        last_copy_groups = [dup for dup, lst in final_keep_lists.items() if all(k == 0 for k in lst) and len(lst) > 0]

        if actual_files_to_delete == 0 and not last_copy_groups:
            QMessageBox.information(self, "Information", "Aucune suppression à effectuer selon les choix.")
            return

        confirmation_message = f"Êtes-vous sûr de vouloir supprimer environ {actual_files_to_delete} fichier(s)?"
        if last_copy_groups:
            confirmation_message += (
                f"\n\nNote: {len(last_copy_groups)} groupe(s) nécessiteront une confirmation "
                f"manuelle pour conserver la dernière copie."
            )

        reply = QMessageBox.question(self, "Confirmation de suppression",
                                     confirmation_message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.folders_widget.setVisible(False)
            self.delete_button.setEnabled(False)
            self.delete_button.setVisible(False)
            self.final_cancel_button.setText("Terminé")
            self.final_cancel_button.setEnabled(False)

            self.log_text.setVisible(True)
            self.log_text.clear()
            self.log_text.append("<b>Début de la suppression des fichiers en double...</b>")
            QApplication.processEvents()

            try:
                log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
                os.makedirs(log_dir, exist_ok=True)
                log_file_path = os.path.join(log_dir, "deletions.log")
                self.log_file = open(log_file_path, "a", encoding="utf-8")
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.log_file.write(f"\n--- Session Start: {timestamp} ---\n")
                self.log_file.write(f"Root folder: {self.folder_path}\n")
                self.log_file.write(f"Comparison: {'Content (Hash)' if self.test_content else 'Name + Size'}\n\n")
            except Exception as e:
                self.log_text.append(f"<font color='red'>Erreur ouverture fichier log: {str(e)}</font>")
                self.log_file = None

            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Suppression: %v/%m")
            self.progress_bar.setMaximum(len(self.duplicate_files))

            files_deleted_count = 0
            deletion_cancelled_by_user = False

            for i, duplicate in enumerate(self.duplicate_files):
                current_keep_list = final_keep_lists[duplicate]

                log_group_header = f"Groupe: {duplicate.name} ({format_size(duplicate.size)})"
                if self.test_content and duplicate.hash:
                    log_group_header += f" Hash: {duplicate.hash[:12]}..."
                self.log_text.append(f"<b>{log_group_header}</b>")
                if self.log_file:
                    self.log_file.write(f"\n{log_group_header}\n")
                QApplication.processEvents()

                if all(k == 0 for k in current_keep_list) and len(current_keep_list) > 0:
                    log_entry = "Protection dernière copie: Tous les fichiers sont dans des dossiers marqués 'Effacer'."
                    self.log_text.append(f"<font color='orange'>{log_entry}</font>")
                    if self.log_file:
                        self.log_file.write(f"WARNING: {log_entry}\n")

                    current_folder_structure = sorted([os.path.dirname(p) for p in duplicate.paths])
                    matched_behavior = next(
                        (b for b in self.behaviors if sorted(b['folders']) == current_folder_structure), None
                    )

                    if matched_behavior:
                        log_entry = "Application du comportement enregistré."
                        self.log_text.append(log_entry)
                        if self.log_file:
                            self.log_file.write(f"INFO: {log_entry}\n")
                        temp_keep_list = [0] * len(duplicate.paths)
                        for k_idx, k_path in enumerate(duplicate.paths):
                            k_folder = os.path.dirname(k_path)
                            if matched_behavior['choices'].get(k_folder, 0) == 1:
                                temp_keep_list[k_idx] = 1
                        if all(k == 0 for k in temp_keep_list):
                            temp_keep_list[0] = 1
                        current_keep_list = temp_keep_list
                        final_keep_lists[duplicate] = current_keep_list
                    else:
                        dialog_duplicate_copy = DuplicateFile(duplicate.name, duplicate.size, duplicate.hash)
                        dialog_duplicate_copy.paths = list(duplicate.paths)
                        dialog_duplicate_copy.keep = [0] * len(duplicate.paths)

                        dialog = LastCopyProtectionDialog(dialog_duplicate_copy, self)
                        dialog.exec_()

                        current_keep_list = list(dialog_duplicate_copy.keep)
                        final_keep_lists[duplicate] = current_keep_list

                        if dialog.action_taken == 'cancel':
                            log_entry = "Suppression annulée par l'utilisateur via dialogue."
                            self.log_text.append(f"<b><font color='red'>{log_entry}</font></b>")
                            if self.log_file:
                                self.log_file.write(f"ACTION: {log_entry}\n")
                            deletion_cancelled_by_user = True
                            break

                        elif dialog.action_taken == 'apply_to_all':
                            behavior = {
                                'folders': current_folder_structure,
                                'choices': {
                                    os.path.dirname(path): keep_status
                                    for path, keep_status in zip(duplicate.paths, current_keep_list)
                                }
                            }
                            self.behaviors.append(behavior)
                            log_entry = "Comportement enregistré pour cette configuration."
                            self.log_text.append(f"<font color='blue'>{log_entry}</font>")
                            if self.log_file:
                                self.log_file.write(f"INFO: {log_entry}\n")

                        if all(k == 0 for k in current_keep_list):
                            log_entry = "Ajustement: Au moins une copie doit être conservée."
                            self.log_text.append(f"<font color='orange'>{log_entry}</font>")
                            if self.log_file:
                                self.log_file.write(f"WARNING: {log_entry}\n")
                            current_keep_list[0] = 1
                            final_keep_lists[duplicate] = current_keep_list

                for j, path in enumerate(duplicate.paths):
                    if current_keep_list[j] == 0:
                        try:
                            os.remove(path)
                            log_entry = f"Supprimé: {path}"
                            self.log_text.append(log_entry)
                            if self.log_file:
                                self.log_file.write(f"DELETED: {path}\n")
                            files_deleted_count += 1
                        except OSError as e:
                            log_entry = f"Erreur suppression: {path} - {e}"
                            self.log_text.append(f"<font color='red'>{log_entry}</font>")
                            if self.log_file:
                                self.log_file.write(f"ERROR: {log_entry}\n")
                        except Exception as e:
                            log_entry = f"Erreur inattendue suppression: {path} - {e}"
                            self.log_text.append(f"<font color='red'>{log_entry}</font>")
                            if self.log_file:
                                self.log_file.write(f"ERROR: {log_entry}\n")
                    else:
                        if self.log_file:
                            self.log_file.write(f"KEPT:    {path}\n")

                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()

            if deletion_cancelled_by_user:
                final_message = "Suppression annulée par l'utilisateur."
                QMessageBox.warning(self, "Annulé", final_message)
            else:
                final_message = f"Suppression terminée. {files_deleted_count} fichier(s) supprimé(s)."
                QMessageBox.information(self, "Terminé", final_message)

            self.log_text.append(f"\n<b>{final_message}</b>")

            if self.log_file:
                self.log_file.write(f"\n--- Session End: {files_deleted_count} deleted ---\n")
                try:
                    self.log_file.close()
                except Exception as e:
                    print(f"Error closing log file: {e}")
                self.log_file = None

            self.progress_bar.setVisible(False)
            self.final_cancel_button.setEnabled(True)

    def closeEvent(self, event):
        if self.log_file:
            try:
                self.log_file.close()
            except Exception as e:
                print(f"Error closing log file on exit: {e}")
        event.accept()


class LastCopyProtectionDialog(QDialog):
    def __init__(self, duplicate_file, parent=None):
        super().__init__(parent)
        self.duplicate_file = duplicate_file
        self.action_taken = 'resume'

        self.setWindowTitle("Protection Dernière Copie")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info_text = (
            f"Toutes les copies du fichier '{self.duplicate_file.name}' "
            f"({format_size(self.duplicate_file.size)}) "
            f"se trouvent dans des dossiers marqués pour suppression.\n"
            f"Veuillez sélectionner au moins une copie à conserver:"
        )
        layout.addWidget(QLabel(info_text))

        self.checkboxes = []

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)

        for i, path in enumerate(self.duplicate_file.paths):
            checkbox = QCheckBox(path)
            checkbox.setProperty("file_index", i)
            scroll_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("Conserver Sélection")
        self.ok_button.clicked.connect(self.accept_selection)

        self.apply_all_button = QPushButton("Conserver & Appliquer à Tous")
        self.apply_all_button.setToolTip(
            "Conserver ce fichier et appliquer ce choix à tous les groupes futurs ayant la même structure de dossiers."
        )
        self.apply_all_button.clicked.connect(self.accept_and_apply_all)

        self.cancel_button = QPushButton("Annuler Suppression Globale")
        self.cancel_button.clicked.connect(self.cancel_all_deletions)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.apply_all_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def accept_selection(self):
        self.update_keep_list()
        if not any(k == 1 for k in self.duplicate_file.keep):
            QMessageBox.warning(self, "Sélection Requise", "Veuillez sélectionner au moins un fichier à conserver.")
            return
        self.action_taken = 'resume'
        self.accept()

    def accept_and_apply_all(self):
        self.update_keep_list()
        if not any(k == 1 for k in self.duplicate_file.keep):
            QMessageBox.warning(self, "Sélection Requise", "Veuillez sélectionner au moins un fichier à conserver.")
            return
        self.action_taken = 'apply_to_all'
        self.accept()

    def cancel_all_deletions(self):
        self.action_taken = 'cancel'
        self.reject()

    def update_keep_list(self):
        self.duplicate_file.keep = [0] * len(self.duplicate_file.paths)
        for checkbox in self.checkboxes:
            if checkbox.isChecked():
                index = checkbox.property("file_index")
                if 0 <= index < len(self.duplicate_file.keep):
                    self.duplicate_file.keep[index] = 1
                else:
                    print(f"Warning: Invalid checkbox index {index} found in protection dialog.")
                    if self.duplicate_file.keep:
                        self.duplicate_file.keep[0] = 1
