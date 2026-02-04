"""Create a test user account for quick login."""
from app import app
from database import db, User
import bcrypt

with app.app_context():
    # Create test user with valid email format (q@q.com for easy login)
    test_email = "q@q.com"
    test_user = User.query.filter_by(email=test_email).first()
    
    if test_user:
        print("Test user already exists!")
        print(f"Email: {test_email}")
        print(f"Password: q")
    else:
        # Create test user with valid email format
        password_hash = bcrypt.hashpw("q".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        test_user = User(email=test_email, password_hash=password_hash, subscription_tier="free")
        db.session.add(test_user)
        db.session.commit()
        print("Test user created successfully!")
        print(f"Email: {test_email}")
        print(f"Password: q")
        print("\nYou can now login with:")
        print(f"  Email: {test_email}")
        print("  Password: q")
