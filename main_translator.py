# main_translator.py

import sys
from PyQt5.QtWidgets import QApplication
from translator_app import TranslatorApp

def main():
    app = QApplication(sys.argv)
    translator_app = TranslatorApp()
    translator_app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
