# main_text_splitter.py

import sys
from PyQt5.QtWidgets import QApplication
from text_splitter_app import TextSplitterApp

def main():
    app = QApplication(sys.argv)
    window = TextSplitterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
