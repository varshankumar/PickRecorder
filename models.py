from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import os

client = MongoClient(os.getenv('MONGO_URI'))
db = client.users
users = db.user_info

class User(UserMixin):
    def __init__(self, username, email, password_hash=None):
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def save(self):
        users.insert_one({
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash
        })

    @staticmethod
    def get(username):
        user_data = users.find_one({'username': username})
        if user_data:
            return User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash']
            )
        return None

    def get_id(self):
        return self.username