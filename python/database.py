import sqlite3
import threading
from datetime import datetime


class Database:
    def __init__(self, db_path="data/dashboard.db"):
        self.db_path = db_path
        self.local = threading.local()
        self._init_db()

    def _get_connection(self):
        """获取线程本地的数据库连接"""
        if not hasattr(self.local, "connection"):
            self.local.connection = sqlite3.connect(
                self.db_path, check_same_thread=False
            )
            self.local.connection.row_factory = sqlite3.Row
        return self.local.connection

    def _init_db(self):
        """初始化数据库表"""
        import os

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 设置表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 分组表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                order_num INTEGER DEFAULT 999,
                is_nas_service BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 服务表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url_public TEXT,
                url_local TEXT,
                icon TEXT,
                order_num INTEGER DEFAULT 999,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE
            )
        """
        )

        # 检查是否存在NAS服务分组
        cursor.execute("SELECT COUNT(*) as count FROM groups WHERE is_nas_service = 1")
        if cursor.fetchone()["count"] == 0:
            cursor.execute(
                """
                INSERT INTO groups (name, order_num, is_nas_service) 
                VALUES ('NAS服务', 1, 1)
            """
            )

        conn.commit()

    def get_setting(self, key):
        """获取设置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_setting(self, key, value):
        """设置配置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            (key, value),
        )
        conn.commit()

    def get_all_groups(self):
        """获取所有分组及其服务"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, name, order_num, is_nas_service 
            FROM groups 
            ORDER BY order_num, id
        """
        )
        groups = []
        for row in cursor.fetchall():
            group = {
                "id": row["id"],
                "name": row["name"],
                "order": row["order_num"],
                "is_nas_service": bool(row["is_nas_service"]),
                "services": [],
            }

            cursor.execute(
                """
                SELECT id, name, url_public, url_local, icon, order_num
                FROM services
                WHERE group_id = ?
                ORDER BY order_num, id
            """,
                (row["id"],),
            )

            for service_row in cursor.fetchall():
                group["services"].append(
                    {
                        "id": service_row["id"],
                        "name": service_row["name"],
                        "url_public": service_row["url_public"],
                        "url_local": service_row["url_local"],
                        "icon": service_row["icon"],
                        "order": service_row["order_num"],
                    }
                )

            groups.append(group)

        return groups

    def create_group(self, name, order=999, is_nas_service=False):
        """创建分组"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO groups (name, order_num, is_nas_service)
            VALUES (?, ?, ?)
        """,
            (name, order, is_nas_service),
        )
        conn.commit()
        return cursor.lastrowid

    def update_group(self, group_id, name, order=None):
        """更新分组"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if order is not None:
            cursor.execute(
                """
                UPDATE groups SET name = ?, order_num = ? WHERE id = ?
            """,
                (name, order, group_id),
            )
        else:
            cursor.execute(
                """
                UPDATE groups SET name = ? WHERE id = ?
            """,
                (name, group_id),
            )
        conn.commit()

    def delete_group(self, group_id):
        """删除分组"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        conn.commit()

    def create_service(
        self, group_id, name, url_public="", url_local="", icon="", order=999
    ):
        """创建服务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO services (group_id, name, url_public, url_local, icon, order_num)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (group_id, name, url_public, url_local, icon, order),
        )
        conn.commit()
        return cursor.lastrowid

    def update_service(
        self, service_id, name, url_public=None, url_local=None, icon=None, order=None
    ):
        """更新服务"""
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = ["name = ?"]
        params = [name]

        if url_public is not None:
            updates.append("url_public = ?")
            params.append(url_public)
        if url_local is not None:
            updates.append("url_local = ?")
            params.append(url_local)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if order is not None:
            updates.append("order_num = ?")
            params.append(order)

        params.append(service_id)

        cursor.execute(
            f"""
            UPDATE services SET {', '.join(updates)} WHERE id = ?
        """,
            params,
        )
        conn.commit()

    def delete_service(self, service_id):
        """删除服务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
        conn.commit()
