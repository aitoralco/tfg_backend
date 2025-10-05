from app.db.session import Base, engine
from app.models import user_model 

Base.metadata.create_all(bind=engine)

print("Database initialized with all tables.")