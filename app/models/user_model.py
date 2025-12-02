from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    #role = Column(Integer, default=0)
    role_number_fk = Column(
        Integer, 
        ForeignKey("roles.role_number"), 
        nullable=False, 
        default=0
    )
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relació amb els roles
    role = relationship(
        "RoleModel", 
        back_populates="users", 
        primaryjoin="UserModel.role_number_fk == RoleModel.role_number",
        lazy="joined"
        )