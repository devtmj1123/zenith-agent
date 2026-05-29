from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import shutil

app = FastAPI()

# In-memory database
users_db = {}

class User(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

@app.post("/users/", response_model=User)
async def create_user(user: UserCreate):
    user_id = str(uuid.uuid4())
    user_data = user.model_dump()
    user_data["id"] = user_id
    user_data["avatar_url"] = None
    users_db[user_id] = user_data
    return user_data

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.put("/users/{user_id}/avatar", response_model=User)
async def upload_avatar(user_id: str, file: UploadFile = File(...)):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: .jpg, .jpeg, .png")

    # Check file size (read and check length)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    # Save file
    filename = f"{user_id}_{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Update user profile
    users_db[user_id]["avatar_url"] = f"/uploads/{filename}"
    return users_db[user_id]
