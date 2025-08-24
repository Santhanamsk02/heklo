import os
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib, ssl
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- Config ---
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_SSL = os.getenv("SMTP_SSL", "true").lower() == "true"

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB ---
client = AsyncIOMotorClient(MONGO_URI)
db = client["project_db"]
collection = db["projects"]

# --- Models ---
class Project(BaseModel):
    clientName: str
    projectName: str
    budget: str
    deadline: str
    email: str
    phone: str
    address: str
    description: str
    requirements: str
    status: str

# --- Helpers ---
def serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["_id"] = str(doc.get("_id"))
    return doc

def send_email_to_admin(project: Project):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = f"New Project Submitted: {project.projectName}"

    body = (
        f"Client: {project.clientName}\n"
        f"Project: {project.projectName}\n"
        f"Budget: {project.budget}\n"
        f"Deadline: {project.deadline}\n"
        f"Email: {project.email}\n"
        f"Phone: {project.phone}\n"
        f"Address: {project.address}\n"
        f"Description: {project.description}\n"
        f"Requirements: {project.requirements}\n"
        f"Status: {project.status}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    if SMTP_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, ADMIN_EMAIL, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, ADMIN_EMAIL, msg.as_string())

# --- Routes ---
@app.get("/", tags=["health"])
async def health():
    return {"status": "ok"}

@app.post("/project", tags=["projects"])
async def create_project(project: Project):
    await collection.insert_one(project.model_dump())
    # Send email to admin (non-async but fast enough here)
    send_email_to_admin(project)
    return {"message": "Project stored and emailed to admin."}

@app.get("/projects", tags=["projects"])
async def get_projects():
    docs = await collection.find().to_list(500)
    return [serialize(d) for d in docs]
