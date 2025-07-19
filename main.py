from fastapi import FastAPI, Depends, HTTPException, status, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta, timezone
import mysql.connector
import ollama
import schedule
import time
import threading
import logging
import urllib.parse

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = "mysql+mysqlconnector://root:Vishu%40123@localhost/hrm"
try:
    engine = create_engine(DATABASE_URL)
    logger.debug("Database connection established")
except Exception as e:
    logger.error(f"Failed to connect to database: {str(e)}")
    raise Exception(f"Database connection failed: {str(e)}")

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    name = Column(String(255))
    role = Column(String(50))

class Availability(Base):
    __tablename__ = "availability"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    week_start = Column(Date)
    monday_available = Column(Boolean)
    monday_hours = Column(Integer)
    monday_notes = Column(Text)
    tuesday_available = Column(Boolean)
    tuesday_hours = Column(Integer)
    tuesday_notes = Column(Text)
    wednesday_available = Column(Boolean)
    wednesday_hours = Column(Integer)
    wednesday_notes = Column(Text)
    thursday_available = Column(Boolean)
    thursday_hours = Column(Integer)
    thursday_notes = Column(Text)
    submitted_at = Column(DateTime)

class Login(Base):
    __tablename__ = "logins"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    login_time = Column(DateTime)

# Drop and recreate tables
try:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.debug("Database tables created successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {str(e)}")
    raise Exception(f"Database table creation failed: {str(e)}")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Get current user from cookie
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    email = request.cookies.get("user_email")
    if email:
        email = urllib.parse.unquote(email)
    logger.debug(f"Checking cookie user_email: {email}")
    if not email:
        logger.error("No user_email cookie found")
        raise HTTPException(status_code=401, detail="Session expired or not logged in")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        logger.error(f"User not found for email: {email}")
        raise HTTPException(status_code=401, detail="User not found")
    logger.debug(f"User authenticated: {user.email}, role: {user.role}")
    return user

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_login(request: Request):
    logger.debug("Serving login page")
    try:
        response = templates.TemplateResponse("login.html", {"request": request})
        response.delete_cookie("user_email", path="/")
        logger.debug("Cleared user_email cookie on login page")
        return response
    except Exception as e:
        logger.error(f"Template rendering error for login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    logger.debug(f"Login attempt for email: {email}")
    if not email.endswith("@gmail.com"):
        logger.error("Invalid email: not a Gmail address")
        raise HTTPException(status_code=400, detail="Please use a Gmail address")
    
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.password = password
            user.name = email.split("@")[0].capitalize()
            user.role = "Admin" if email == "admin@gmail.com" else "Employee"
            logger.debug(f"Updated user: {email}")
        else:
            user = User(
                email=email,
                password=password,
                name=email.split("@")[0].capitalize(),
                role="Admin" if email == "admin@gmail.com" else "Employee"
            )
            db.add(user)
            logger.debug(f"Created new user: {email}")
        
        login_record = Login(user_id=user.id, login_time=datetime.now(timezone.utc))
        db.add(login_record)
        db.commit()
        logger.debug(f"Login recorded for user: {email}")
        
        response = RedirectResponse(url="/dashboard", status_code=303)
        encoded_email = urllib.parse.quote(email)
        response.set_cookie(
            key="user_email",
            value=encoded_email,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=3600,
            path="/"
        )
        logger.debug(f"Set user_email cookie: {encoded_email}")
        response.headers["X-Cookie-Set"] = encoded_email
        return response
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, user: User = Depends(get_current_user)):
    logger.debug(f"Rendering dashboard for user: {user.email}, role: {user.role}")
    try:
        response = templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "user_name": user.name,
            "user_role": user.role
        })
        logger.debug("Dashboard template rendered successfully")
        return response
    except Exception as e:
        logger.error(f"Template rendering error for dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")

@app.get("/logout")
async def logout():
    logger.debug("Logging out user")
    response = RedirectResponse(url="/")
    response.delete_cookie("user_email", path="/")
    logger.debug("Cleared user_email cookie on logout")
    return response

@app.post("/api/availability")
async def submit_availability(
    week_start: str = Form(...),
    monday_available: bool = Form(False),
    monday_hours: int = Form(0),
    monday_notes: str = Form(""),
    tuesday_available: bool = Form(False),
    tuesday_hours: int = Form(0),
    tuesday_notes: str = Form(""),
    wednesday_available: bool = Form(False),
    wednesday_hours: int = Form(0),
    wednesday_notes: str = Form(""),
    thursday_available: bool = Form(False),
    thursday_hours: int = Form(0),
    thursday_notes: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.debug(f"Submitting availability for user: {user.email}")
        total_hours = monday_hours + tuesday_hours + wednesday_hours + thursday_hours
        if total_hours != 36:
            logger.error(f"Invalid total hours: {total_hours}")
            raise HTTPException(status_code=400, detail="Total hours must equal 36")
        
        availability = Availability(
            user_id=user.id,
            week_start=datetime.strptime(week_start, "%Y-%m-%d").date(),
            monday_available=monday_available,
            monday_hours=monday_hours,
            monday_notes=monday_notes,
            tuesday_available=tuesday_available,
            tuesday_hours=tuesday_hours,
            tuesday_notes=tuesday_notes,
            wednesday_available=wednesday_available,
            wednesday_hours=wednesday_hours,
            wednesday_notes=wednesday_notes,
            thursday_available=thursday_available,
            thursday_hours=thursday_hours,
            thursday_notes=thursday_notes,
            submitted_at=datetime.now(timezone.utc)
        )
        db.add(availability)
        db.commit()
        logger.debug("Availability submitted successfully")
        return {"message": "Availability submitted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Database error in submit_availability: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/availability/status")
async def get_availability_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        logger.debug(f"Fetching availability status for user: {user.email}")
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=today.weekday())
        availability = db.query(Availability).filter(
            Availability.user_id == user.id,
            Availability.week_start == week_start
        ).first()
        logger.debug(f"Availability status: {'Submitted' if availability else 'Not submitted'}")
        return {
            "submitted": availability is not None,
            "week_start": week_start.isoformat()
        }
    except Exception as e:
        logger.error(f"Database error in get_availability_status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/performance")
async def get_performance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        logger.debug(f"Fetching performance data for user: {user.email}")
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=today.weekday())
        
        availability = db.query(Availability).filter(
            Availability.user_id == user.id,
            Availability.week_start == week_start
        ).first()
        
        logins = db.query(Login).filter(
            Login.user_id == user.id,
            Login.login_time >= week_start,
            Login.login_time < week_start + timedelta(days=7)
        ).all()
        
        planned_hours = 0
        summary = []
        if availability:
            planned_hours = (availability.monday_hours + availability.tuesday_hours +
                             availability.wednesday_hours + availability.thursday_hours)
            summary = [
                {"day": "Monday", "hours": availability.monday_hours, "notes": availability.monday_notes},
                {"day": "Tuesday", "hours": availability.tuesday_hours, "notes": availability.tuesday_notes},
                {"day": "Wednesday", "hours": availability.wednesday_hours, "notes": availability.wednesday_notes},
                {"day": "Thursday", "hours": availability.thursday_hours, "notes": availability.thursday_notes}
            ]
        
        login_days = len(set(login.login_time.date() for login in logins))
        actual_hours = login_days * 9
        variance = planned_hours - actual_hours
        
        try:
            prompt = f"User planned {planned_hours} hours but worked {actual_hours} hours this week. Variance: {variance} hours. Provide concise performance feedback."
            ollama_response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
            feedback = ollama_response["message"]["content"]
        except:
            feedback = "Fallback: Maintain consistent login to meet planned hours."
        
        logger.debug("Performance data retrieved successfully")
        return {
            "planned_hours": planned_hours,
            "actual_hours": actual_hours,
            "variance": variance,
            "days_worked": login_days,
            "summary": summary,
            "feedback": feedback
        }
    except Exception as e:
        logger.error(f"Database error in get_performance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/ai-settings")
async def ai_settings(prompt: dict):
    try:
        logger.debug("Fetching AI settings")
        response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt.get("prompt", "Provide a brief HR tip")}])
        return {"response": response["message"]["content"]}
    except Exception as e:
        logger.error(f"Error in ai_settings: {str(e)}")
        return {"response": "Ollama not available. Please ensure it's running."}

# Notification Scheduler
def send_notifications():
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()
        if today.weekday() == 6:
            week_start = today - timedelta(days=today.weekday())
            users = db.query(User).all()
            for user in users:
                availability = db.query(Availability).filter(
                    Availability.user_id == user.id,
                    Availability.week_start == week_start
                ).first()
                if not availability:
                    logger.info(f"Notification: {user.email} has not submitted availability for {week_start}")
    except Exception as e:
        logger.error(f"Error in send_notifications: {str(e)}")
    finally:
        db.close()

def run_scheduler():
    schedule.every().sunday.at("00:00").do(send_notifications)
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.on_event("startup")
async def startup_event():
    logger.debug("Starting scheduler")
    threading.Thread(target=run_scheduler, daemon=True).start()

# Health check endpoint
@app.get("/health")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "Server is running"}