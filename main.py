from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database import ensure_database
from app.ui.main_window import MainWindow


def main() -> int:
    ensure_database()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

