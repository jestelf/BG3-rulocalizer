# translation_pairs_dialog.py

import re

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QRadioButton, QDialogButtonBox
)
from PyQt5.QtCore import QSettings


class TranslationPairsDialog(QDialog):
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("Импорт пар перевода")
        self.resize(600, 400)  # Увеличиваем размер окна

        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "Отредактируйте пары в формате: Оригинал|Перевод\nКаждая пара на новой строке."
        )
        layout.addWidget(self.info_label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.text_edit)

        # Радиокнопки для выбора метода импорта
        self.basic_import_radio = QRadioButton("Основной метод импорта")
        self.levenshtein_import_radio = QRadioButton("Использовать Левенштейна для сопоставлений")

        # Читаем из QSettings ранее сохранённые настройки
        self.settings = QSettings("MyCompany", "MyApp")
        import_method = self.settings.value("import_method", "basic")
        if import_method == "levenshtein":
            self.levenshtein_import_radio.setChecked(True)
        else:
            self.basic_import_radio.setChecked(True)

        layout.addWidget(self.basic_import_radio)
        layout.addWidget(self.levenshtein_import_radio)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def process_text_for_splitting(self, input_data: str) -> str:
        """
        Повторяет логику из TextSplitterApp:
        ищет пары вида `english|russian` и делает переносы.
        """
        pattern = re.compile(r'([a-zA-Z0-9\s\.\,\!\?\'\(\)]+)\s*\|\s*([\u0400-\u04FF\s\.\,\!\?\'\(\)]+)')
        matches = pattern.findall(input_data)
        result_lines = []
        for match in matches:
            english_part = match[0].strip()
            russian_part = match[1].strip()
            result_lines.append(f"{english_part}|{russian_part}")
        return "\n".join(result_lines)

    def get_pairs(self) -> dict:
        """
        Собирает все пары (оригинал|перевод) из текстового поля.
        Если все пары были в одной строке, process_text_for_splitting
        разносит их построчно.
        """
        text_input = self.text_edit.toPlainText().strip()
        splitted = self.process_text_for_splitting(text_input)
        if splitted:
            text_input = splitted

        lines = text_input.split('\n')
        translation_map = {}
        for line in lines:
            line = line.strip()
            if '|' in line:
                parts = line.split('|', 1)
                original = parts[0].strip()
                translated = parts[1].strip()
                if original:
                    translation_map[original] = translated
        return translation_map

    def get_import_method(self) -> str:
        """
        Сохраняет выбранный пользователем метод в QSettings
        и возвращает название метода ('basic' или 'levenshtein').
        """
        if self.levenshtein_import_radio.isChecked():
            self.settings.setValue("import_method", "levenshtein")
            return 'levenshtein'
        else:
            self.settings.setValue("import_method", "basic")
            return 'basic'
