from app import app
from database import db

def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset successfully! All tables created with new columns.")

if __name__ == "__main__":
    reset_db()
