# translator_app.py

import os
import sys

# Сторонние библиотеки
from googletrans import Translator
from bs4 import BeautifulSoup
from lxml import etree
from Levenshtein import distance as lev_distance

# PyQt5
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QPushButton, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView, QProgressBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent

# Наши внутренние модули
from translation_pairs_dialog import TranslationPairsDialog
from utils import remove_amp


class TranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XML Translator with Structure")
        self.setGeometry(100, 100, 1200, 700)

        # ---------- Графический интерфейс ----------
        # Центральный контейнер и общий layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 1) Кнопки сверху
        self.buttons_layout = QHBoxLayout()
        self.open_folder_button = QPushButton("Выбрать папку модов", self)
        self.open_folder_button.clicked.connect(self.select_main_folder)
        self.buttons_layout.addWidget(self.open_folder_button)

        self.auto_translate_button = QPushButton("Автоперевод", self)
        self.auto_translate_button.clicked.connect(self.generate_auto_translation)
        self.buttons_layout.addWidget(self.auto_translate_button)

        self.import_pairs_button = QPushButton("Импорт пар перевода", self)
        self.import_pairs_button.clicked.connect(self.import_translation_pairs)
        self.buttons_layout.addWidget(self.import_pairs_button)

        self.translate_button = QPushButton("Применить перевод", self)
        self.translate_button.clicked.connect(self.apply_translation)
        self.buttons_layout.addWidget(self.translate_button)

        self.main_layout.addLayout(self.buttons_layout)

        # 2) Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # 3) Разделитель для структуры слева (дерево) и таблицы справа
        self.splitter = QSplitter()
        self.main_layout.addWidget(self.splitter)

        # 3.1) Дерево слева
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Моды и XML файлы"])
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.splitter.addWidget(self.tree)

        # 3.2) Таблица справа
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Оригинал", "Перевод"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | 
            QAbstractItemView.EditKeyPressed | 
            QAbstractItemView.AnyKeyPressed
        )
        self.splitter.addWidget(self.table)

        # Клик по ячейке "Оригинал" копирует текст в "Перевод"
        self.table.itemDoubleClicked.connect(self.on_table_item_double_clicked)

        # ---------- Логика состояния ----------
        self.main_folder = None
        self.mods_data = {}
        self.current_mod_name = None
        self.current_xml_path = None
        self.current_contents = []

        # Переводчик Googletrans (вместо моделей transformer)
        self.translator = Translator()

    # ---------- Логика автоперевода ----------
    def translate_single_sentence(self, sentence: str) -> str:
        """
        Переводит один текст через Google Translate (en→ru).
        """
        try:
            result = self.translator.translate(sentence, src='en', dest='ru')
            return result.text
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при переводе: {str(e)}")
            return ""

    # ---------- Управление таблицей (копирование, очистка и т.п.) ----------
    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_C:  # CTRL + C
                self.copy_selected_cells()
            elif event.key() == Qt.Key_Backspace:  # CTRL + Backspace
                self.clear_selected_cells()
        super().keyPressEvent(event)

    def copy_selected_cells(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.clear()

        text = [item.text() for item in selected_items]
        clipboard.setText("\n".join(text))

    def clear_selected_cells(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            item.setText("")

    def on_table_item_double_clicked(self, item: QTableWidgetItem):
        """При двойном клике по ячейке с оригиналом копируем текст в колонку перевода."""
        row = item.row()
        if item.column() == 0:  # колонка "Оригинал"
            original_text = item.text()
            self.table.setItem(row, 1, QTableWidgetItem(original_text))

    # ---------- Логика работы с директориями и файлами XML ----------
    def select_main_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку, где находится UnpackedMods")
        if folder_path:
            self.main_folder = folder_path
            self.load_mods()

    def load_mods(self):
        from PyQt5.QtWidgets import QApplication, QTreeWidgetItem

        self.tree.clear()
        self.mods_data.clear()

        unpacked_mods_path = os.path.join(self.main_folder, "UnpackedMods")
        if not os.path.exists(unpacked_mods_path):
            QMessageBox.critical(self, "Ошибка", f"Папка UnpackedMods не найдена: {self.main_folder}")
            return

        mods = [m for m in os.listdir(unpacked_mods_path)
                if os.path.isdir(os.path.join(unpacked_mods_path, m))]

        if not mods:
            QMessageBox.information(self, "Нет модов", "В папке UnpackedMods нет доступных модов.")
            return

        # Включаем прогресс-бар
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(mods))

        for i, mod_name in enumerate(mods):
            mod_path = os.path.join(unpacked_mods_path, mod_name)

            # Ищем english.xml и russian.xml
            english_xml = self.find_english_xml(mod_path)
            russian_xml = self.find_russian_xml(mod_path)

            mod_item = QTreeWidgetItem([mod_name])
            self.tree.addTopLevelItem(mod_item)
            self.mods_data[mod_name] = {}

            # Добавляем данные по english.xml
            if english_xml:
                contents = self.extract_contents(english_xml)
                if contents:
                    self.mods_data[mod_name][english_xml] = contents
                    xml_item = QTreeWidgetItem([os.path.basename(english_xml)])
                    mod_item.addChild(xml_item)

            # Если есть russian.xml — добавим как отдельный узел
            if russian_xml:
                russian_item = QTreeWidgetItem([os.path.basename(russian_xml)])
                mod_item.addChild(russian_item)

            # Если нет английского, пытаемся загрузить все прочие XML
            all_xml = self.find_all_xml(mod_path)
            for x in all_xml:
                if x not in (english_xml, russian_xml):
                    contents = self.extract_contents(x)
                    if contents:
                        self.mods_data[mod_name][x] = contents
                        xml_item = QTreeWidgetItem([os.path.basename(x)])
                        mod_item.addChild(xml_item)

            mod_item.setExpanded(False)
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()

        # Скрываем все ветки
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(False)

        self.progress_bar.setVisible(False)

    def find_russian_xml(self, mod_path: str) -> str:
        """
        Ищет файл russian.xml внутри папки `Localization/Russian`.
        """
        russian_path = os.path.join(mod_path, "Localization", "Russian")
        if os.path.exists(russian_path):
            for file in os.listdir(russian_path):
                if file.lower() == "russian.xml":
                    return os.path.join(russian_path, file)
        return None

    def find_english_xml(self, mod_path: str) -> str:
        """
        Ищет файл english.xml по дереву папок, где есть папка Localization.
        """
        for root, dirs, files in os.walk(mod_path):
            if "Localization" in root:
                for file in files:
                    if file.lower() == "english.xml":
                        return os.path.join(root, file)
        return None

    def find_all_xml(self, mod_path: str) -> list:
        """
        Ищет все файлы *.xml в папках Localization.
        """
        result = []
        for root, dirs, files in os.walk(mod_path):
            if "Localization" in root:
                for file in files:
                    if file.lower().endswith(".xml"):
                        result.append(os.path.join(root, file))
        return result

    def extract_contents(self, xml_path: str) -> list:
        """
        Извлекает содержимое <content>...</content> из XML-файла.
        """
        try:
            with open(xml_path, 'r', encoding='utf-8') as file:
                xml_content = file.read()

            soup = BeautifulSoup(xml_content, 'xml')
            contents = []
            for c in soup.find_all('content'):
                if c.string:
                    original_text = c.decode_contents()
                    contents.append([original_text.strip(), ""])
                else:
                    contents.append(["", ""])
            return contents
        except Exception:
            return []

    # ---------- Логика выбора и отображения содержимого XML в таблицу ----------
    def on_tree_selection_changed(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        parent = item.parent()

        # Если кликнули по конкретному XML-файлу, а не по названию мода
        if parent is not None:
            mod_name = parent.text(0)
            xml_file_name = item.text(0)
            # Найдём в self.mods_data полным путём
            for path_ in self.mods_data[mod_name].keys():
                if os.path.basename(path_) == xml_file_name:
                    self.current_mod_name = mod_name
                    self.current_xml_path = path_
                    self.generate_original_for_translation()
                    return
        else:
            # Кликнули по моду
            self.current_mod_name = None
            self.current_xml_path = None

    def generate_original_for_translation(self):
        """
        Заполняет таблицу "Оригинал | Перевод" данными из self.mods_data,
        соответствующими текущему пути self.current_xml_path.
        """
        if not self.current_xml_path or not self.current_mod_name:
            QMessageBox.warning(self, "Ошибка", "Выберите XML файл слева.")
            return

        self.current_contents = self.mods_data[self.current_mod_name][self.current_xml_path]
        self.table.clearContents()
        self.table.setRowCount(len(self.current_contents))

        for i, (orig, trans) in enumerate(self.current_contents):
            orig_item = QTableWidgetItem(orig)
            # Запрещаем редактировать колонку оригинала
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, orig_item)
            self.table.setItem(i, 1, QTableWidgetItem(trans))

    # ---------- Автоперевод всей таблицы (Google Translate) ----------
    def generate_auto_translation(self):
        if not self.current_xml_path or not self.current_mod_name:
            QMessageBox.warning(self, "Ошибка", "Выберите XML файл из дерева слева.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Ошибка", "Сначала выведите оригинал для перевода.")
            return

        from PyQt5.QtWidgets import QApplication
        row_count = self.table.rowCount()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, row_count)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i in range(row_count):
                original_item = self.table.item(i, 0)
                if original_item:
                    original_text = original_item.text().strip()
                    if original_text:
                        translated_text = self.translate_single_sentence(original_text)
                        self.table.setItem(i, 1, QTableWidgetItem(translated_text))

                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при автопереводе: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setVisible(False)

    # ---------- Импорт пар перевода из диалогового окна ----------
    def import_translation_pairs(self):
        if not self.current_xml_path or not self.current_mod_name:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите XML-файл из дерева слева.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Ошибка", "Сначала выведите оригинал для перевода, чтобы были строки для сопоставления.")
            return

        # Собираем строки, у которых перевод пустой, чтобы предложить импорт
        pairs_text = []
        for i in range(self.table.rowCount()):
            original = self.table.item(i, 0).text()
            translation = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            if not translation.strip():
                pairs_text.append(f"{original}|")

        if not pairs_text:
            QMessageBox.information(self, "Нет пустых переводов", "Все переводы уже заполнены.")
            return

        initial_text = "\n".join(pairs_text)
        dialog = TranslationPairsDialog(self, initial_text=initial_text)
        if dialog.exec_():
            pairs = dialog.get_pairs()
            import_method = dialog.get_import_method()

            if pairs:
                from PyQt5.QtWidgets import QApplication
                row_count = self.table.rowCount()
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, row_count)

                # Пробуем применить пары напрямую
                for i in range(row_count):
                    original = self.table.item(i, 0).text()
                    translation = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
                    if not translation.strip() and original in pairs:
                        cleaned_translation = remove_amp(pairs[original]).strip()
                        self.table.setItem(i, 1, QTableWidgetItem(cleaned_translation))

                    self.progress_bar.setValue(i + 1)
                    QApplication.processEvents()

                # Если выбран метод "levenshtein", применяем fuzzy-сопоставление
                if import_method == 'levenshtein':
                    self.apply_levenshtein_matching(pairs)

                QMessageBox.information(self, "Готово", "Пары перевода применены к таблице.")
                self.progress_bar.setVisible(False)
            else:
                QMessageBox.information(self, "Нет пар", "Пары не найдены или неправильный формат.")

    def apply_levenshtein_matching(self, pairs: dict):
        """
        Применяем перевод для строк, которые похожи на оригинал
        с учётом расстояния Левенштейна.
        """
        for original, translation in pairs.items():
            for i in range(self.table.rowCount()):
                comparison = self.table.item(i, 0).text().strip()
                # Если расстояние Левенштейна <= 3, считаем, что строки похожи
                if lev_distance(original, comparison) <= 3:
                    current_translation = self.table.item(i, 1).text()
                    if not current_translation.strip():
                        cleaned_translation = remove_amp(translation).strip()
                        self.table.setItem(i, 1, QTableWidgetItem(cleaned_translation))

    # ---------- Сохранение перевода в russian.xml ----------
    def apply_translation(self):
        if not self.current_xml_path or not self.current_mod_name:
            QMessageBox.warning(self, "Ошибка", "Выберите XML файл из дерева слева.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет данных для применения перевода.")
            return

        # Обновляем self.current_contents из таблицы
        for i in range(self.table.rowCount()):
            trans = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            cleaned_trans = remove_amp(trans).strip()
            self.current_contents[i][1] = cleaned_trans

        # Применяем перевод к исходному XML
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(self.current_xml_path, parser)
            root = tree.getroot()

            contents_elems = root.findall('.//content')
            for i, c_elem in enumerate(contents_elems):
                if i < len(self.current_contents):
                    if self.current_contents[i][1].strip():
                        c_elem.text = self.current_contents[i][1]

            # Сохраняем результат в папке Russian
            localization_dir = os.path.join(os.path.dirname(self.current_xml_path), "..", "Russian")
            os.makedirs(localization_dir, exist_ok=True)
            output_file = os.path.join(localization_dir, "russian.xml")

            tree.write(output_file, encoding="utf-8", xml_declaration=True, pretty_print=True)

            # Удаляем "amp;" из итогового файла (если где-то затесалось)
            with open(output_file, 'r', encoding='utf-8') as file:
                content = file.read()
            content = content.replace("amp;", "")
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(content)

            QMessageBox.information(self, "Сохранено", f"Перевод сохранён в: {output_file}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении перевода: {str(e)}")
