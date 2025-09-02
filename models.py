# models.py
from flask_login import UserMixin
from config import get_db_connection

class User(UserMixin):
    def __init__(self, id, username, email, full_name, is_admin):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.is_admin = is_admin

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user_data:
            return None
        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            is_admin=user_data['is_admin']
        )

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user_data:
            return None
        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            is_admin=user_data['is_admin']
        )