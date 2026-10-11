"""DB 연결 및 경로 관리."""

import os
import sqlite3

# 프로젝트 루트 기준 절대 경로 (CWD 무관하게 동작)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)
