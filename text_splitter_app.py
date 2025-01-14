# text_splitter_app.py

import sys
import re
import pyperclip

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QLabel, QMessageBox
)


class TextSplitterApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Text Splitter App")
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        self.input_label = QLabel("Вставьте текст в поле ниже:")
        layout.addWidget(self.input_label)
        self.input_text = QTextEdit()
        layout.addWidget(self.input_text)

        self.split_button = QPushButton("Разделить текст")
        self.split_button.clicked.connect(self.split_text)
        layout.addWidget(self.split_button)

        self.output_label = QLabel("Результат:")
        layout.addWidget(self.output_label)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        self.copy_button = QPushButton("Копировать в буфер обмена")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.copy_button)

        self.setLayout(layout)

    def split_text(self):
        """
        Получает текст из поля ввода (или из буфера) и разбивает на строки
        по шаблону "English | Russian".
        """
        input_data = self.input_text.toPlainText()
        if not input_data:
            # Если поле пустое, пробуем прочитать из буфера
            input_data = pyperclip.paste()

        if input_data:
            result_lines = self.process_text(input_data)
            self.output_text.setPlainText("\n".join(result_lines))
        else:
            self.output_text.setPlainText("Нет текста для обработки.")

    def process_text(self, input_data: str) -> list:
        """
        Использует регэксп для поиска пар:
        (латиница, цифры, знаки) | (кириллица, знаки).
        """
        pattern = re.compile(
            r'([a-zA-Z0-9\s\.\,\!\?\'\(\)]+)\s*\|\s*([\u0400-\u04FF\s\.\,\!\?\'\(\)]+)'
        )
        matches = pattern.findall(input_data)
        result_lines = []
        for match in matches:
            english_part = match[0].strip()
            russian_part = match[1].strip()
            result_lines.append(f"{english_part} | {russian_part}")
        return result_lines

    def copy_to_clipboard(self):
        """
        Копирует результат в буфер обмена.
        """
        result = self.output_text.toPlainText()
        if result:
            pyperclip.copy(result)
            QMessageBox.information(self, "Успех", "Результат скопирован в буфер обмена!")


def text_splitter_app_main():
    """
    Альтернативная точка входа из кода (если нужно).
    """
    app = QApplication(sys.argv)
    window = TextSplitterApp()
    window.show()
    sys.exit(app.exec_())
