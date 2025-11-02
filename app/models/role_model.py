from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.session import Base

class RoleModel(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    role_number = Column(Integer, unique=True, index=True)

    # Relació amb els usuaris
    users = relationship("UserModel", back_populates="role", lazy="joined")