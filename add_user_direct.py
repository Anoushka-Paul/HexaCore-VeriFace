from auth_service.database import SessionLocal, User
from auth_service.auth import hash_password

db = SessionLocal()
user = User(username='autouser_direct', hashed_password=hash_password('autopass'), role='admin')
db.add(user)
db.commit()
print('Inserted user id', user.id)