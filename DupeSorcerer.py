import sys
import os
import hashlib # Added import
import math    # Added import
import datetime # Added import for logging timestamp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QLabel, QRadioButton, QButtonGroup,
                             QScrollArea, QFrame, QMessageBox, QProgressBar, QTextEdit, QDialog,
                             QCheckBox) # Added QCheckBox for dialog
from PyQt5.QtCore import Qt, pyqtSignal # Added pyqtSignal

# Added helper function
def calculate_sha256(filepath, buffer_size=65536):
    """Calculates the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                sha256_hash.update(data)
        return sha256_hash.hexdigest()
    except IOError as e:
        # Handle file reading errors (e.g., permission denied)
        print(f"Error hashing file {filepath}: {e}") # Log error
        return None
    except Exception as e: # Catch other potential errors
        print(f"Unexpected error hashing file {filepath}: {e}")
        return None

class DuplicateFile:
    # Modified __init__
    def __init__(self, name, size, file_hash=None): # Added hash parameter
        self.name = name # Typically the name of the first file encountered in the group
        self.size = size # Size of the files in the group
        self.hash = file_hash # Hash if calculated, else None
        self.paths = []  # List of full paths for all files in this duplicate group
        self.keep = []  # List of booleans (1=keep, 0=delete) corresponding to self.paths

class DoublonFolder:
    def __init__(self, path):
        self.path = path
        self.duplicate_count = 0  # Number of duplicate files residing in this folder
        self.todo = 1  # 1=Ne rien faire, 2=Effacer (duplicates in this folder), 3=Garder (duplicates in this folder)

class DuplicateFilesManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestionnaire de fichiers en double v0.3")
        self.setMinimumSize(800, 600)

        self.duplicate_files = []  # List of DuplicateFile objects
        self.doublon_folders = []  # List of DoublonFolder objects
        self.folder_path = ""
        self.current_folder_index = 0 # Index for folder review loop
        self.behaviors = [] # List to store saved behaviors for last copy protection
        self.log_file = None # File object for logging deletions
        self.test_content = False # Added flag, True for hash comparison, False for name+size

        self.init_ui()

    def init_ui(self):
        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Layout principal
        main_layout = QVBoxLayout(main_widget)

        # Section pour sélectionner le dossier
        select_layout = QHBoxLayout()
        self.path_label = QLabel("Aucun dossier sélectionné")
        self.select_button = QPushButton("Sélectionner un dossier")
        self.select_button.clicked.connect(self.select_folder)
        select_layout.addWidget(self.path_label, 1) # Give label more space
        select_layout.addWidget(self.select_button)
        main_layout.addLayout(select_layout)

        # Section for comparison method - Added
        self.comparison_group = QButtonGroup(self)
        self.radio_name_size = QRadioButton("Nom + Taille")
        self.radio_name_size.setChecked(True) # Default
        self.radio_hash = QRadioButton("Contenu (Hash)")
        self.comparison_group.addButton(self.radio_name_size, 0)
        self.comparison_group.addButton(self.radio_hash, 1)
        # Connect signal AFTER buttons are created
        self.comparison_group.buttonClicked[int].connect(self.set_comparison_method)

        comparison_layout = QHBoxLayout()
        comparison_layout.addWidget(QLabel("Comparer par:"))
        comparison_layout.addWidget(self.radio_name_size)
        comparison_layout.addWidget(self.radio_hash)
        comparison_layout.addStretch()
        # Use a QWidget as a container for the layout
        self.comparison_widget = QWidget()
        self.comparison_widget.setLayout(comparison_layout)
        main_layout.addWidget(self.comparison_widget) # Add the container widget

        # Bouton pour analyser les doublons
        self.analyze_button = QPushButton("Analyser les doublons")
        self.analyze_button.clicked.connect(self.analyze_duplicates)
        main_layout.addWidget(self.analyze_button)

        # Label for detection phase
        self.detection_label = QLabel("Détection en cours...")
        self.detection_label.setVisible(False)
        main_layout.addWidget(self.detection_label)

        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True) # Show percentage
        main_layout.addWidget(self.progress_bar)

        # Label for review phase
        self.review_label = QLabel("Revue des dossiers:")
        self.review_label.setVisible(False)
        main_layout.addWidget(self.review_label)

        # Progress bar for review phase
        self.review_progress_bar = QProgressBar()
        self.review_progress_bar.setVisible(False)
        self.review_progress_bar.setTextVisible(True) # Show progress like x/y
        main_layout.addWidget(self.review_progress_bar)

        # Zone de défilement pour afficher les dossiers avec doublons / logs
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area, 1) # Allow scroll area to expand

        # Widget contenant les dossiers avec doublons ou les logs
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop) # Align content to top
        scroll_area.setWidget(self.content_widget)

        # Sous-widget pour les dossiers (utilisé pendant la phase de revue/confirmation)
        self.folders_widget = QWidget()
        self.folders_layout = QVBoxLayout(self.folders_widget)
        self.folders_layout.setAlignment(Qt.AlignTop) # Align folders to top
        self.content_layout.addWidget(self.folders_widget)

        # Zone de texte pour les logs (utilisé pendant la phase de suppression)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setVisible(False) # Initially hidden
        self.content_layout.addWidget(self.log_text)

        # Boutons pour la navigation
        self.buttons_layout = QHBoxLayout()

        # Boutons pour la phase de revue des dossiers
        self.ok_button = QPushButton("Suivant") # Changed label
        self.ok_button.setDefault(True) # Make this the default button
        self.ok_button.clicked.connect(self.process_folder_choice)
        self.ok_button.setVisible(False) # Initially hidden

        self.cancel_button = QPushButton("Tout Passer") # Changed label
        self.cancel_button.setToolTip("Passer la revue de tous les dossiers restants et aller à la confirmation.")
        self.cancel_button.clicked.connect(self.cancel_process)
        self.cancel_button.setVisible(False) # Initially hidden

        # Button for processing now (skip review entirely)
        self.process_now_button = QPushButton("Tout Traiter") # Changed label
        self.process_now_button.setToolTip("Marquer tous les dossiers pour suppression (sauf protection) et aller à la confirmation.")
        self.process_now_button.clicked.connect(self.process_now)
        self.process_now_button.setVisible(False) # Initially hidden

        # Boutons pour la phase de suppression
        self.delete_button = QPushButton("Confirmer Suppression")
        self.delete_button.clicked.connect(self.start_deletion)
        self.delete_button.setVisible(False) # Initially hidden

        self.final_cancel_button = QPushButton("Annuler / Fermer")
        self.final_cancel_button.clicked.connect(self.close) # Simple close for now
        self.final_cancel_button.setVisible(True) # Always visible, maybe disable

        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.buttons_layout.addWidget(self.process_now_button)
        self.buttons_layout.addStretch() # Push delete/cancel to the right
        self.buttons_layout.addWidget(self.delete_button)
        self.buttons_layout.addWidget(self.final_cancel_button)

        main_layout.addLayout(self.buttons_layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier racine")
        if folder:
            self.folder_path = folder
            self.path_label.setText(f"Dossier: {folder}")
            # Reset UI to initial state before analysis
            self.analyze_button.setVisible(True)
            self.comparison_widget.setVisible(True)
            self.select_button.setVisible(True)
            self.ok_button.setVisible(False)
            self.cancel_button.setVisible(False)
            self.process_now_button.setVisible(False)
            self.delete_button.setVisible(False)
            self.review_label.setVisible(False)
            self.review_progress_bar.setVisible(False)
            self.log_text.setVisible(False)
            self.folders_widget.setVisible(True) # Ensure folder area is visible
            # Clear previous results
            self.clear_layout(self.folders_layout)
            self.log_text.clear()


    def set_comparison_method(self, method_id):
        """Sets the comparison method based on radio button selection."""
        self.test_content = (method_id == 1) # 1 corresponds to Content (Hash)

    def analyze_duplicates(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Attention", "Veuillez d'abord sélectionner un dossier.")
            return

        # --- UI Setup for Analysis ---
        self.analyze_button.setEnabled(False) # Disable analyze button during analysis
        self.select_button.setVisible(False)
        self.comparison_widget.setVisible(False) # Hide comparison options
        self.clear_layout(self.folders_layout) # Clear previous results display
        self.log_text.setVisible(False)
        self.folders_widget.setVisible(True) # Ensure folder area is visible for potential messages

        # Reset results
        self.duplicate_files = []
        self.doublon_folders = []
        self.behaviors = [] # Reset behaviors on new analysis

        # Show progress bar and label
        self.detection_label.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Recherche fichiers: %v/%m")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        # --- Étape 1: Trouver tous les fichiers dans le dossier ---
        all_file_details = [] # List to store (file_path, file_name, file_size)
        total_files = 0

        # First pass: Collect file paths and count for progress bar
        try:
            for root, _, files in os.walk(self.folder_path):
                if not files: # Skip empty directories
                    continue
                for file_name in files:
                     try:
                         file_path = os.path.join(root, file_name)
                         # Basic check if it's a file and readable, get size
                         if os.path.isfile(file_path):
                             file_size = os.path.getsize(file_path)
                             all_file_details.append((file_path, file_name, file_size))
                             total_files += 1
                     except OSError as e:
                         print(f"Warning: Cannot access file info {file_path}: {e}")
                     except Exception as e:
                         print(f"Unexpected error accessing file info {file_path}: {e}")

                # Update progress bar during file discovery (optional, can be slow)
                # self.progress_bar.setValue(total_files)
                # QApplication.processEvents()

        except OSError as e:
             QMessageBox.critical(self, "Erreur", f"Impossible de parcourir le dossier: {e}")
             self.reset_ui_after_analysis_error()
             return
        except Exception as e: # Catch other potential errors during walk
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

        # --- Étape 2: Identifier les doublons ---
        file_dict = {}  # Dictionnaire pour stocker les fichiers par clé (hash ou name+size)

        for i, (file_path, file_name, file_size) in enumerate(all_file_details):
            key = None
            current_hash = None # Store hash if calculated

            try:
                if self.test_content:
                    # Compare by hash
                    current_hash = calculate_sha256(file_path)
                    if current_hash: # Only proceed if hash calculation was successful
                        key = current_hash
                    # else: error already printed in calculate_sha256, skip file
                else:
                    # Compare by name + size
                    key = (file_name, file_size)

                if key: # If a valid key was generated
                    if key not in file_dict:
                         file_dict[key] = {'paths': [], 'name': file_name, 'size': file_size, 'hash': current_hash}
                    # Append path even if key exists
                    file_dict[key]['paths'].append(file_path)

            except Exception as e: # Catch unexpected errors during key generation/dict access
                print(f"Unexpected error processing file {file_path}: {e}")

            # Mettre à jour la progression
            self.progress_bar.setValue(i + 1)
            if i % 50 == 0: # Update UI periodically to avoid freezing
                QApplication.processEvents()

        # Ensure final UI update for progress bar
        QApplication.processEvents()

        # --- Filtrer pour ne garder que les groupes de doublons ---
        for key, data in file_dict.items():
            if len(data['paths']) > 1:  # C'est un doublon
                # Use name/size from the dictionary entry (represents the group)
                duplicate = DuplicateFile(data['name'], data['size'], data['hash'])
                duplicate.paths = data['paths']
                duplicate.keep = [1] * len(data['paths'])  # Par défaut, on garde tous les fichiers
                self.duplicate_files.append(duplicate)

        # --- Étape 3: Établir la liste des dossiers contenant des doublons ---
        folder_dict = {}  # Dictionnaire pour compter les doublons par dossier {folder_path: count}

        for duplicate in self.duplicate_files:
            for path in duplicate.paths:
                folder = os.path.dirname(path)
                folder_dict[folder] = folder_dict.get(folder, 0) + 1

        # Créer les objets DoublonFolder
        self.doublon_folders = []
        for folder_path, count in folder_dict.items():
            doublon_folder = DoublonFolder(folder_path)
            doublon_folder.duplicate_count = count
            self.doublon_folders.append(doublon_folder)

        # Trier par nombre de doublons décroissant
        self.doublon_folders.sort(key=lambda x: x.duplicate_count, reverse=True)

        # --- Finaliser l'UI après analyse ---
        self.progress_bar.setVisible(False)
        self.detection_label.setVisible(False)
        self.analyze_button.setEnabled(True) # Re-enable analyze button

        if self.doublon_folders:
            # Hide the analyze button if duplicates found and review starts
            self.analyze_button.setVisible(False)

            # Show review UI elements
            self.review_label.setVisible(True)
            self.review_progress_bar.setVisible(True)
            self.review_progress_bar.setMaximum(len(self.doublon_folders))
            self.review_progress_bar.setFormat("Dossier %v / %m")
            self.review_progress_bar.setValue(0) # Start at 0

            # Show review buttons
            self.ok_button.setVisible(True)
            self.cancel_button.setVisible(True)
            self.process_now_button.setVisible(True)
            self.delete_button.setVisible(False) # Hide delete confirmation button

            self.current_folder_index = 0
            self.show_current_folder() # Display the first folder for review
        else:
            QMessageBox.information(self, "Information", "Aucun doublon trouvé.")
            # Ensure comparison options and select button are visible again
            self.reset_ui_after_analysis_error() # Use helper to reset


    def reset_ui_after_analysis_error(self):
        """Resets UI elements to pre-analysis state, e.g., after an error or no duplicates found."""
        self.comparison_widget.setVisible(True)
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
        """Displays the current folder and related folders for review."""
        self.clear_layout(self.folders_layout) # Clear previous folder display

        # Update review progress bar (index is 0-based, display is 1-based)
        self.review_progress_bar.setValue(self.current_folder_index + 1)

        if self.current_folder_index >= len(self.doublon_folders):
             # Should not happen if called correctly, but as safeguard:
             print("Warning: show_current_folder called out of bounds.")
             self.show_deletion_confirmation() # Go to confirmation if review is somehow finished
             return

        # Obtenir le dossier courant
        current_folder_obj = self.doublon_folders[self.current_folder_index]

        # Afficher le dossier courant
        self.folders_layout.addWidget(QLabel(f"<b>Dossier actuel ({current_folder_obj.duplicate_count} doublons):</b>"))
        self.add_folder_choice(current_folder_obj) # Display choices for the current folder

        # Trouver les dossiers contenant les mêmes doublons que ceux présents dans le dossier courant
        related_folder_objects = set()
        processed_duplicates = set() # Avoid processing the same duplicate group multiple times

        # Find all duplicate groups that have at least one file in the current folder
        for duplicate in self.duplicate_files:
             # Check if any path in this duplicate group belongs to the current folder
             in_current_folder = any(os.path.dirname(path) == current_folder_obj.path for path in duplicate.paths)

             if in_current_folder:
                 # If this duplicate group involves the current folder, find all other folders involved
                 for path in duplicate.paths:
                     folder_path = os.path.dirname(path)
                     if folder_path != current_folder_obj.path:
                         # Find the DoublonFolder object for this related folder
                         related_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                         # Add the object if found (regardless of its todo state)
                         if related_obj: # MODIFIED LINE
                             related_folder_objects.add(related_obj) # Add the object itself

         # Afficher les dossiers liés (tous, même ceux déjà traités)
        if related_folder_objects:
            self.folders_layout.addWidget(QLabel("<b>Dossiers liés (non traités):</b>"))

            # Sort related folders for consistent display
            sorted_related_folders = sorted(list(related_folder_objects), key=lambda f: f.path)
            # Corrected indentation for the loop and the focus setting
            for folder_obj in sorted_related_folders:
                self.add_folder_choice(folder_obj) # Display choices for related folders

        # Explicitly set focus to the default button (ensure this is inside the method scope)
        self.ok_button.setFocus()

    def add_folder_choice(self, folder_obj):
        """Adds a widget to the UI for selecting action on a specific folder."""
        folder_frame = QFrame()
        folder_frame.setFrameShape(QFrame.StyledPanel)
        folder_layout = QVBoxLayout(folder_frame)

        # Afficher le chemin du dossier
        folder_layout.addWidget(QLabel(f"{folder_obj.path} ({folder_obj.duplicate_count} doublons)"))

        # Créer les boutons radio
        radio_layout = QHBoxLayout()
        radio_group = QButtonGroup(folder_frame)
        # Store the folder object itself for easier access later
        # Note: Storing Python objects directly with setProperty might be tricky depending on Qt version/bindings.
        # A safer alternative might be to store the folder_path and look it up again.
        # Let's try storing the object first.
        radio_group.setProperty("folder_object", folder_obj)

        radio1 = QRadioButton("Ne rien faire")
        radio2 = QRadioButton("Effacer")
        radio3 = QRadioButton("Garder")
        radio_group.addButton(radio1, 1)
        radio_group.addButton(radio2, 2)
        radio_group.addButton(radio3, 3)

        # Select the button based on the folder's current 'todo' state
        current_todo = folder_obj.todo
        if current_todo == 1:
            radio1.setChecked(True)
        elif current_todo == 2:
            radio2.setChecked(True)
        elif current_todo == 3:
            radio3.setChecked(True)
        else: # Default fallback
             radio1.setChecked(True)
             folder_obj.todo = 1 # Ensure state consistency

        radio_layout.addWidget(radio1)
        radio_layout.addWidget(radio2)
        radio_layout.addWidget(radio3)
        folder_layout.addLayout(radio_layout)

        self.folders_layout.addWidget(folder_frame)


    def process_folder_choice(self):
        """Processes the choices made for the currently displayed folders and moves to the next folder that requires review."""
        # Update the 'todo' status for all folders currently displayed in the UI
        # (This part remains the same as original)
        for i in range(self.folders_layout.count()):
            widget = self.folders_layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                button_group = widget.findChild(QButtonGroup)
                if button_group:
                    folder_obj = button_group.property("folder_object")
                    if folder_obj: # Check if object is valid
                        choice = button_group.checkedId()
                        folder_obj.todo = choice
                        # processed_folders_in_view.add(folder_obj.path) # Not strictly needed anymore

        # --- Start modification: Find the next folder needing review ---
        self.current_folder_index += 1

        while self.current_folder_index < len(self.doublon_folders):
            next_folder_obj = self.doublon_folders[self.current_folder_index]

            # Check if this folder and all its related folders are already processed
            related_folders_for_next = set()
            for duplicate in self.duplicate_files:
                # Check if any path in this duplicate group belongs to the next folder
                in_next_folder = any(os.path.dirname(p) == next_folder_obj.path for p in duplicate.paths)
                if in_next_folder:
                    # If yes, find all folders involved in this duplicate group
                    for path in duplicate.paths:
                        folder_path = os.path.dirname(path)
                        # Find the DoublonFolder object (including itself)
                        related_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                        if related_obj:
                            related_folders_for_next.add(related_obj)

            # Check if all involved folders have a decided state (not 1)
            all_processed = all(folder.todo != 1 for folder in related_folders_for_next)

            if all_processed:
                # Skip this folder, move to the next
                self.current_folder_index += 1
            else:
                # This folder needs review, break the loop
                break
        # --- End modification ---

        # Now show the folder found (or confirmation if end of list)
        if self.current_folder_index < len(self.doublon_folders):
            self.show_current_folder() # Show the folder that needs review
        else:
            # End of review, show confirmation screen
            self.show_deletion_confirmation()


    def cancel_process(self):
        """Skips the rest of the folder review process."""
        reply = QMessageBox.question(self, "Confirmation",
                                    "Passer la revue de tous les dossiers restants et aller à la confirmation?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # No need to change 'todo' status, just jump to the end
            self.current_folder_index = len(self.doublon_folders)  # Mark review as done
            self.show_deletion_confirmation()


    def process_now(self):
        """Marks all folders for deletion (respecting 'Garder') and jumps to confirmation."""
        reply = QMessageBox.question(self, "Confirmation",
                                    "Marquer tous les dossiers pour suppression (sauf ceux marqués 'Garder') et aller à la confirmation?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for folder in self.doublon_folders:
                if folder.todo != 3: # If not explicitly marked 'Garder'
                    folder.todo = 2 # Mark for deletion
            self.current_folder_index = len(self.doublon_folders)  # Mark review as done
            self.show_deletion_confirmation()


    def show_deletion_confirmation(self):
        """Displays a summary of actions before final deletion."""
        # --- UI Setup for Confirmation ---
        self.ok_button.setVisible(False)
        self.cancel_button.setVisible(False)
        self.process_now_button.setVisible(False)
        self.review_label.setVisible(False)
        self.review_progress_bar.setVisible(False)

        self.delete_button.setVisible(True) # Show confirmation button
        self.final_cancel_button.setText("Annuler") # Change button text

        self.clear_layout(self.folders_layout) # Clear folder review widgets
        self.log_text.setVisible(False) # Hide log text view
        self.folders_widget.setVisible(True) # Show folder area for summary

        # --- Calculate Summary ---
        folders_to_delete = [f for f in self.doublon_folders if f.todo == 2]
        folders_to_keep = [f for f in self.doublon_folders if f.todo == 3]
        folders_ignored = [f for f in self.doublon_folders if f.todo == 1]

        files_to_delete_count = 0
        files_to_keep_count = 0
        potential_last_copy_issues = 0

        # Determine which files will actually be deleted/kept based on folder choices
        temp_keep_lists = {} # Store calculated keep list for each duplicate group {duplicate_obj: [keep_list]}
        for duplicate in self.duplicate_files:
            keep_list = [1] * len(duplicate.paths) # Default to keep
            for i, path in enumerate(duplicate.paths):
                folder_path = os.path.dirname(path)
                folder_obj = next((f for f in self.doublon_folders if f.path == folder_path), None)
                if folder_obj:
                    if folder_obj.todo == 2: # Delete folder
                        keep_list[i] = 0
                    elif folder_obj.todo == 3: # Keep folder
                        keep_list[i] = 1
                    # else: todo == 1 (Ignore folder), keep_list[i] remains 1 (keep)

            # Check for last copy issue *before* final count
            if all(k == 0 for k in keep_list) and len(keep_list) > 0:
                 potential_last_copy_issues += 1
                 # Tentatively mark first file to keep for summary count
                 # The actual dialog will handle the choice later
                 keep_list[0] = 1

            temp_keep_lists[duplicate] = keep_list
            files_to_delete_count += keep_list.count(0)
            files_to_keep_count += keep_list.count(1)

        # --- Display Summary ---
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
            warning_label = QLabel(f"<font color='orange'>Attention: {potential_last_copy_issues} groupe(s) de doublons n'ont de copies que dans des dossiers marqués 'Effacer'. Vous devrez choisir quelle copie conserver lors de la suppression.</font>")
            warning_label.setWordWrap(True)
            self.folders_layout.addWidget(warning_label)

        if files_to_delete_count == 0 and potential_last_copy_issues == 0:
             self.delete_button.setEnabled(False)
             self.folders_layout.addWidget(QLabel("\nAucun fichier à supprimer."))
        else:
             self.delete_button.setEnabled(True)


    def start_deletion(self):
        """Executes the deletion process after confirmation."""
        # Use the pre-calculated keep lists from show_deletion_confirmation if possible,
        # otherwise recalculate here for safety. Let's recalculate.
        folder_choices = {folder.path: folder.todo for folder in self.doublon_folders}
        final_keep_lists = {} # {duplicate_obj: [keep_list]}

        for duplicate in self.duplicate_files:
            keep_list = [1] * len(duplicate.paths) # Default keep
            for i, path in enumerate(duplicate.paths):
                folder_path = os.path.dirname(path)
                choice = folder_choices.get(folder_path, 1) # Default ignore
                if choice == 2: keep_list[i] = 0
                elif choice == 3: keep_list[i] = 1
                # else choice == 1, keep_list[i] remains 1
            final_keep_lists[duplicate] = keep_list

        # Count files genuinely marked for deletion before asking confirmation
        actual_files_to_delete = sum(lst.count(0) for lst in final_keep_lists.values())
        last_copy_groups = [dup for dup, lst in final_keep_lists.items() if all(k==0 for k in lst) and len(lst)>0]

        if actual_files_to_delete == 0 and not last_copy_groups:
             QMessageBox.information(self, "Information", "Aucune suppression à effectuer selon les choix.")
             return

        confirmation_message = f"Êtes-vous sûr de vouloir supprimer environ {actual_files_to_delete} fichier(s)?"
        if last_copy_groups:
             confirmation_message += f"\n\nNote: {len(last_copy_groups)} groupe(s) nécessiteront une confirmation manuelle pour conserver la dernière copie."

        reply = QMessageBox.question(self, "Confirmation de suppression",
                                    confirmation_message,
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # --- UI Setup for Deletion Log ---
            self.folders_widget.setVisible(False) # Hide the summary area
            self.delete_button.setEnabled(False)
            self.delete_button.setVisible(False)
            self.final_cancel_button.setText("Terminé") # Change close button text
            self.final_cancel_button.setEnabled(False) # Disable until finished

            # Show log area
            self.log_text.setVisible(True)
            self.log_text.clear()
            self.log_text.append("<b>Début de la suppression des fichiers en double...</b>")
            QApplication.processEvents()

            # --- Setup Logging ---
            try:
                log_dir = "logs"
                os.makedirs(log_dir, exist_ok=True)
                log_file_path = os.path.join(log_dir, "deletions.log")
                self.log_file = open(log_file_path, "a", encoding='utf-8') # Append mode, utf-8
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.log_file.write(f"\n--- Session Start: {timestamp} ---\n")
                self.log_file.write(f"Root folder: {self.folder_path}\n")
                self.log_file.write(f"Comparison: {'Content (Hash)' if self.test_content else 'Name + Size'}\n\n")
            except Exception as e:
                self.log_text.append(f"<font color='red'>Erreur ouverture fichier log '{log_file_path}': {str(e)}</font>")
                self.log_file = None

            # --- Show Progress Bar ---
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Suppression: %v/%m")
            self.progress_bar.setMaximum(len(self.duplicate_files)) # Progress per group

            # --- Deletion Loop ---
            files_deleted_count = 0
            deletion_cancelled_by_user = False

            for i, duplicate in enumerate(self.duplicate_files):
                # Get the final keep/delete list for this group
                current_keep_list = final_keep_lists[duplicate]

                log_group_header = f"Groupe: {duplicate.name} ({self.format_size(duplicate.size)})"
                if self.test_content and duplicate.hash:
                    log_group_header += f" Hash: {duplicate.hash[:12]}..."
                self.log_text.append(f"<b>{log_group_header}</b>")
                if self.log_file: self.log_file.write(f"\n{log_group_header}\n")
                QApplication.processEvents()

                # --- Last Copy Protection Check ---
                if all(k == 0 for k in current_keep_list) and len(current_keep_list) > 0:
                    log_entry = "Protection dernière copie: Tous les fichiers sont dans des dossiers marqués 'Effacer'."
                    self.log_text.append(f"<font color='orange'>{log_entry}</font>")
                    if self.log_file: self.log_file.write(f"WARNING: {log_entry}\n")

                    # Check for saved behavior
                    current_folder_structure = sorted([os.path.dirname(p) for p in duplicate.paths])
                    matched_behavior = next((b for b in self.behaviors if sorted(b['folders']) == current_folder_structure), None)

                    if matched_behavior:
                        log_entry = "Application du comportement enregistré."
                        self.log_text.append(log_entry)
                        if self.log_file: self.log_file.write(f"INFO: {log_entry}\n")
                        # Apply behavior
                        temp_keep_list = [0] * len(duplicate.paths)
                        for k_idx, k_path in enumerate(duplicate.paths):
                            k_folder = os.path.dirname(k_path)
                            if matched_behavior['choices'].get(k_folder, 0) == 1:
                                temp_keep_list[k_idx] = 1
                        # Ensure at least one kept if behavior deleted all
                        if all(k == 0 for k in temp_keep_list): temp_keep_list[0] = 1
                        current_keep_list = temp_keep_list # Update the list for deletion below
                        final_keep_lists[duplicate] = current_keep_list # Update master list too

                    else:
                        # Show dialog - IMPORTANT: Pass a copy or manage state carefully
                        # The dialog modifies the 'keep' list of the passed object.
                        dialog_duplicate_copy = DuplicateFile(duplicate.name, duplicate.size, duplicate.hash)
                        dialog_duplicate_copy.paths = list(duplicate.paths)
                        dialog_duplicate_copy.keep = [0] * len(duplicate.paths) # Start dialog with all marked delete

                        dialog = LastCopyProtectionDialog(dialog_duplicate_copy, self)
                        result = dialog.exec_()

                        # Get the result from the dialog's copy
                        current_keep_list = list(dialog_duplicate_copy.keep)
                        final_keep_lists[duplicate] = current_keep_list # Update master list

                        if dialog.action_taken == 'cancel':
                            log_entry = "Suppression annulée par l'utilisateur via dialogue."
                            self.log_text.append(f"<b><font color='red'>{log_entry}</font></b>")
                            if self.log_file: self.log_file.write(f"ACTION: {log_entry}\n")
                            deletion_cancelled_by_user = True
                            break # Stop processing further groups

                        elif dialog.action_taken == 'apply_to_all':
                            behavior = {
                                'folders': current_folder_structure,
                                'choices': {os.path.dirname(path): keep_status for path, keep_status in zip(duplicate.paths, current_keep_list)}
                            }
                            self.behaviors.append(behavior)
                            log_entry = "Comportement enregistré pour cette configuration."
                            self.log_text.append(f"<font color='blue'>{log_entry}</font>")
                            if self.log_file: self.log_file.write(f"INFO: {log_entry}\n")

                        # Ensure at least one file is kept after dialog
                        if all(k == 0 for k in current_keep_list):
                            log_entry = "Ajustement: Au moins une copie doit être conservée."
                            self.log_text.append(f"<font color='orange'>{log_entry}</font>")
                            if self.log_file: self.log_file.write(f"WARNING: {log_entry}\n")
                            current_keep_list[0] = 1
                            final_keep_lists[duplicate] = current_keep_list # Update master list

                # --- Perform Deletion based on final list ---
                for j, path in enumerate(duplicate.paths):
                    if current_keep_list[j] == 0: # If marked for deletion
                        try:
                            os.remove(path)
                            log_entry = f"Supprimé: {path}"
                            self.log_text.append(log_entry)
                            if self.log_file: self.log_file.write(f"DELETED: {path}\n")
                            files_deleted_count += 1
                        except OSError as e:
                            log_entry = f"Erreur suppression: {path} - {e}"
                            self.log_text.append(f"<font color='red'>{log_entry}</font>")
                            if self.log_file: self.log_file.write(f"ERROR: {log_entry}\n")
                        except Exception as e: # Catch other unexpected errors
                             log_entry = f"Erreur inattendue suppression: {path} - {e}"
                             self.log_text.append(f"<font color='red'>{log_entry}</font>")
                             if self.log_file: self.log_file.write(f"ERROR: {log_entry}\n")
                    else:
                        # Only log kept files to file, not UI, to reduce clutter
                        if self.log_file: self.log_file.write(f"KEPT:    {path}\n")

                # Update progress bar after processing each group
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents() # Keep UI responsive

            # --- End of Deletion Loop ---
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

            # --- Final UI state ---
            self.progress_bar.setVisible(False)
            self.final_cancel_button.setEnabled(True) # Re-enable close button


    def format_size(self, size_bytes):
        """Formats a size in bytes into a human-readable string."""
        if size_bytes is None or size_bytes < 0: return "N/A"
        if size_bytes == 0: return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        try:
            i = int(math.floor(math.log(size_bytes, 1024)))
            if i >= len(size_name): i = len(size_name) - 1 # Handle extremely large sizes
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)
            return f"{s} {size_name[i]}"
        except ValueError: # math domain error for log(0) or negative
            return "Invalid Size"
        except Exception: # Catch any other unexpected math errors
             return "Error Size"

    def clear_layout(self, layout):
        """Removes all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    # If the item is a layout, clear it recursively
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self.clear_layout(sub_layout)

    def closeEvent(self, event):
        """Handle closing the window."""
        # Clean up log file if open
        if self.log_file:
            try:
                self.log_file.close()
            except Exception as e:
                print(f"Error closing log file on exit: {e}")
        event.accept()


# --- LastCopyProtectionDialog Class ---
class LastCopyProtectionDialog(QDialog):
    """Dialog to force user to select at least one file to keep."""
    # Signal to indicate action taken (optional, could use return value)
    # actionCompleted = pyqtSignal(str) # 'resume', 'apply_to_all', 'cancel'

    def __init__(self, duplicate_file, parent=None):
        super().__init__(parent)
        self.duplicate_file = duplicate_file # Reference to the DuplicateFile object
        self.parent_manager = parent # Reference to the main window if needed
        self.action_taken = 'resume' # Default action

        self.setWindowTitle("Protection Dernière Copie")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info_text = (f"Toutes les copies du fichier '{self.duplicate_file.name}' "
                     f"({self.parent_manager.format_size(self.duplicate_file.size)}) "
                     f"se trouvent dans des dossiers marqués pour suppression.\n"
                     f"Veuillez sélectionner au moins une copie à conserver:")
        layout.addWidget(QLabel(info_text))

        self.checkboxes = [] # Changed from radio_buttons
        # Removed self.button_group = QButtonGroup(self)
        # Removed self.button_group.setExclusive(True)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)

        for i, path in enumerate(self.duplicate_file.paths):
            checkbox = QCheckBox(path) # Changed from QRadioButton
            # Store index to easily update the keep list
            checkbox.setProperty("file_index", i)
            scroll_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox) # Changed from radio_buttons
            # Removed self.button_group.addButton(radio)

        # Do not select any by default - force user choice
        # if self.checkboxes:
        #     self.checkboxes[0].setChecked(True)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # --- Buttons ---
        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("Conserver Sélection")
        self.ok_button.clicked.connect(self.accept_selection)

        self.apply_all_button = QPushButton("Conserver & Appliquer à Tous")
        self.apply_all_button.setToolTip("Conserver ce fichier et appliquer ce choix à tous les groupes futurs ayant la même structure de dossiers.")
        self.apply_all_button.clicked.connect(self.accept_and_apply_all)

        self.cancel_button = QPushButton("Annuler Suppression Globale")
        self.cancel_button.clicked.connect(self.cancel_all_deletions)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.apply_all_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def accept_selection(self):
        self.update_keep_list()
        # --- Added Validation ---
        if not any(k == 1 for k in self.duplicate_file.keep):
            QMessageBox.warning(self, "Sélection Requise", "Veuillez sélectionner au moins un fichier à conserver.")
            return # Do not close dialog
        # --- End Validation ---
        self.action_taken = 'resume'
        self.accept() # Close dialog with QDialog.Accepted

    def accept_and_apply_all(self):
        self.update_keep_list()
        # --- Added Validation ---
        if not any(k == 1 for k in self.duplicate_file.keep):
            QMessageBox.warning(self, "Sélection Requise", "Veuillez sélectionner au moins un fichier à conserver.")
            return # Do not close dialog
        # --- End Validation ---
        self.action_taken = 'apply_to_all'
        self.accept() # Close dialog with QDialog.Accepted

    def cancel_all_deletions(self):
        self.action_taken = 'cancel'
        # self.actionCompleted.emit('cancel')
        self.reject() # Close dialog with QDialog.Rejected

    def update_keep_list(self):
        """Updates the keep list based on the checked checkboxes."""
        # Initialize keep list to all zeros (delete)
        self.duplicate_file.keep = [0] * len(self.duplicate_file.paths)
        # Iterate through checkboxes and update keep list
        for checkbox in self.checkboxes:
            if checkbox.isChecked():
                index = checkbox.property("file_index")
                if 0 <= index < len(self.duplicate_file.keep):
                    self.duplicate_file.keep[index] = 1
                else:
                    # Corrected indentation for lines within the else block
                    print(f"Warning: Invalid checkbox index {index} found in protection dialog.")
                    # Fallback: keep the first one if index is invalid
                    # Note: This fallback might not be ideal. Consider if simply printing the warning is enough.
                    # For now, keeping the fallback logic but ensuring indentation is correct.
                    if self.duplicate_file.keep: self.duplicate_file.keep[0] = 1 # Ensure this is indented under the 'else'

# Removed the redundant 'else' block below that was related to radio buttons

# --- Main Execution Block ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Apply a style for better look and feel (optional)
    # app.setStyle('Fusion')
    manager = DuplicateFilesManager()
    manager.show()
    sys.exit(app.exec_())