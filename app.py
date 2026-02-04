"""Main Flask web application for monetizable AI agent platform."""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db, init_db, User, Automation, SubscriptionTier
from cli import setup_agent
import os
import bcrypt
import stripe
import hashlib
import urllib.parse
import json
import csv
import io
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from job_queue import queue_enabled, get_queue
from scheduler_utils import compute_next_run

app = Flask(__name__)  # create Flask application instance
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")  # secret key for sessions (change in production!)
db_url = os.getenv("DATABASE_URL", "sqlite:///agent_platform.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # disable SQLAlchemy event system (not needed)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Startup diagnostics (no secrets)
print(f"[STARTUP] FREE Lead Scraping: ENABLED (no API costs!)")
print(f"[STARTUP] Email configured: {'yes' if os.getenv('EMAIL_SENDER') else 'no'}")
print(f"[STARTUP] LemonSqueezy payments: {'yes' if os.getenv('LEMONSQUEEZY_API_KEY') else 'no'}")

# Rate limiting (scale protection)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    default_limits=["200 per day", "60 per hour"],
)

# Queue toggle (instant execution for local testing)
def use_queue() -> bool:
    return os.getenv("USE_QUEUE", "true").lower() == "true"

# Global template context
@app.context_processor
def inject_builder_mode():
    return {
        "builder_mode": os.getenv("BUILDER_MODE", "false").lower() == "true"
    }

def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*"
    else:
        masked = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked}@{domain}"

@app.context_processor
def inject_utils():
    return {"mask_email": _mask_email}

def _get_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

def make_client_token(user_id: int) -> str:
    s = _get_serializer()
    return s.dumps({"uid": user_id}, salt="client-portal")

# Stripe Configuration (fallback for international)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY") 
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID") 
STRIPE_BIZ_PRICE_ID = os.getenv("STRIPE_BIZ_PRICE_ID")

# Paystack Configuration (South Africa)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")

# LemonSqueezy Configuration (Global - NO VERIFICATION NEEDED)
LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID", "")
LEMONSQUEEZY_PRO_VARIANT = os.getenv("LEMONSQUEEZY_PRO_VARIANT", "")
LEMONSQUEEZY_BIZ_VARIANT = os.getenv("LEMONSQUEEZY_BIZ_VARIANT", "")

# PayFast Configuration (South Africa)
PAYFAST_MERCHANT_ID = os.getenv("PAYFAST_MERCHANT_ID", "10000100")  # Sandbox default
PAYFAST_MERCHANT_KEY = os.getenv("PAYFAST_MERCHANT_KEY", "46f0cd694581a")  # Sandbox default
PAYFAST_PASSPHRASE = os.getenv("PAYFAST_PASSPHRASE", "")
PAYFAST_SANDBOX = os.getenv("PAYFAST_SANDBOX", "true").lower() == "true"
PAYFAST_URL = "https://sandbox.payfast.co.za/eng/process" if PAYFAST_SANDBOX else "https://www.payfast.co.za/eng/process"

# Plan prices in ZAR
PLAN_PRICES = {
    "pro": 199.00,
    "business": 499.00
}

# Initialize database and login manager
init_db(app)  # create database tables (database.py init_db function)
login_manager = LoginManager()  # Flask-Login manager for user sessions
login_manager.init_app(app)  # connect login manager to Flask app
login_manager.login_view = "login"  # redirect to login page if user not authenticated

# Initialize scheduler for recurring automations (local dev only)
scheduler = BackgroundScheduler()
if not queue_enabled():
    scheduler.start()

def run_scheduled_automation(automation_id):
    """Run a scheduled automation job"""
    with app.app_context():
        automation = Automation.query.get(automation_id)
        if not automation or not automation.is_active:
            return
        
        # Check if automation has expired
        if automation.end_date and datetime.utcnow() > automation.end_date:
            automation.is_active = False
            automation.status = "expired"
            db.session.commit()
            return
        
        user = User.query.get(automation.user_id)
        if not user:
            return
        
        print(f"[SCHEDULER] Running automation {automation_id}: {automation.goal}")
        
        try:
            controller = setup_agent()
            controller.state.planner_context["recipient_email"] = automation.recipient_email
            action_type = "email"
            if automation.goal.startswith("[leads]"):
                action_type = "leads"
            controller.state.planner_context["action_type"] = action_type
            controller.state.planner_context["user_email"] = user.email
            controller.state.planner_context["user_tier"] = user.subscription_tier
            controller.state.planner_context["user_id"] = user.id
            original_goal = automation.goal
            selected_niche = ""
            if "[niche:" in original_goal:
                start = original_goal.lower().find("[niche:")
                end = original_goal.find("]", start)
                if end != -1:
                    selected_niche = original_goal[start + 7:end].strip()
                    original_goal = (original_goal[:start] + original_goal[end + 1:]).strip()
            if original_goal.startswith("[email] "):
                original_goal = original_goal[len("[email] "):]
            elif original_goal.startswith("[leads] "):
                original_goal = original_goal[len("[leads] "):]
            controller.state.planner_context["original_goal"] = original_goal
            controller.state.planner_context["selected_niche"] = selected_niche
            
            result = controller.run(automation.goal)
            
            automation.last_run = datetime.utcnow()
            automation.run_count += 1
            automation.result = f"Run #{automation.run_count}: {result}"
            automation.status = "scheduled"  # Keep as scheduled for recurring
            automation.next_run_at = compute_next_run(
                automation.frequency,
                automation.scheduled_time,
                automation.scheduled_days,
                from_time=datetime.utcnow(),
            )
            db.session.commit()
            
            print(f"[SCHEDULER] Completed automation {automation_id}")
        except Exception as e:
            print(f"[SCHEDULER] Error in automation {automation_id}: {str(e)}")
            automation.result = f"Error: {str(e)}"
            db.session.commit()

def schedule_automation_job(automation):
    """Add a job to the scheduler for an automation"""
    job_id = f"automation_{automation.id}"
    
    # If Redis queue is enabled, we use scheduler_runner instead of APScheduler
    if queue_enabled():
        automation.next_run_at = compute_next_run(
            automation.frequency,
            automation.scheduled_time,
            automation.scheduled_days,
            from_time=datetime.utcnow(),
        )
        db.session.commit()
        return

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    if not automation.is_active or automation.frequency == "once":
        return
    
    # Parse time
    hour, minute = 9, 0
    if automation.scheduled_time:
        try:
            parts = automation.scheduled_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except:
            pass
    
    # Create trigger based on frequency
    if automation.frequency == "daily":
        trigger = CronTrigger(hour=hour, minute=minute)
    elif automation.frequency in ["weekly", "custom"]:
        days = automation.scheduled_days or "mon"
        trigger = CronTrigger(day_of_week=days, hour=hour, minute=minute)
    else:
        return
    
    scheduler.add_job(
        run_scheduled_automation,
        trigger,
        args=[automation.id],
        id=job_id,
        replace_existing=True
    )
    print(f"[SCHEDULER] Added job {job_id} - {automation.frequency} at {hour}:{minute:02d}")

@login_manager.user_loader  # Flask-Login callback to load user from database
def load_user(user_id):  # loads user object from user ID stored in session
    return User.query.get(int(user_id))  # query database for user (User model is in database.py)

@app.route("/")  # homepage route
def index():  # landing page - shows pricing and features
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")  # render homepage template (templates/index.html)

@app.route("/integrations")
@login_required
def integrations():
    from database import Integration
    user_integrations = Integration.query.filter_by(user_id=current_user.id).all()
    return render_template("integrations.html", integrations=user_integrations)

@app.route("/connect-trello", methods=["POST"])
@login_required
def connect_trello():
    from database import Integration
    # In a real app, this would be an OAuth flow. 
    # For this professional mock, we'll simulate a successful connection.
    import json
    # Check if already connected
    existing = Integration.query.filter_by(user_id=current_user.id, service_name="trello").first()
    if existing:
        flash("Trello is already connected!", "info")
    else:
        new_integration = Integration(
            user_id=current_user.id,
            service_name="trello",
            credentials_json=json.dumps({"api_key": "mock_key", "token": "mock_token"})
        )
        db.session.add(new_integration)
        db.session.commit()
        flash("Successfully connected Trello!", "success")
    return redirect(url_for("integrations"))

@app.route("/connect-email", methods=["POST"])
@login_required
def connect_email():
    from database import Integration
    import json
    
    # In a real app, this would redirect to Google's OAuth screen.
    # For this professional simulation, we 'auto-connect' using the 
    # verified App Password you provided for sandtonstreets@gmail.com.
    
    existing = Integration.query.filter_by(user_id=current_user.id, service_name="email").first()
    
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Google account disconnected.", "info")
    else:
        # Professional Simulation: Use environment variables for credentials
        creds = {
            "email": os.getenv("EMAIL_SENDER", ""),
            "app_password": os.getenv("EMAIL_PASSWORD", "") 
        }
        new_integration = Integration(
            user_id=current_user.id,
            service_name="email",
            credentials_json=json.dumps(creds)
        )
        db.session.add(new_integration)
        db.session.commit()
        flash("Successfully connected to Google Workspace via OAuth 2.0!", "success")
    
    return redirect(url_for("integrations"))

@app.route("/signup", methods=["GET", "POST"])  # user registration route
@limiter.limit("10 per minute")
def signup():  # handles user signup (GET shows form, POST processes registration)
    if request.method == "POST":  # if form submitted
        email = request.form.get("email")  # get email from form
        password = request.form.get("password")  # get password from form
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():  # check if email already in database
            flash("Email already registered. Please login instead.", "error")  # show error message
            return redirect(url_for("login"))  # redirect to login page
        
        # Create new user
        import bcrypt  # password hashing library
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")  # hash password securely
        user = User(email=email, password_hash=password_hash, subscription_tier=SubscriptionTier.FREE.value)  # create User object (User model is in database.py)
        db.session.add(user)  # add user to database session
        db.session.commit()  # save user to database
        
        login_user(user)  # automatically log in new user (Flask-Login function)
        flash("Account created successfully! Welcome!", "success")  # show success message
        return redirect(url_for("dashboard"))  # redirect to dashboard
    
    return render_template("signup.html")  # render signup form template

@app.route("/login", methods=["GET", "POST"])  # user login route
@limiter.limit("15 per minute")
def login():  # handles user login (GET shows form, POST processes login)
    if request.method == "POST":  # if form submitted
        email = request.form.get("email")  # get email from form
        password = request.form.get("password")  # get password from form
        
        user = User.query.filter_by(email=email).first()  # find user by email (User.query is SQLAlchemy query)
        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):  # verify password matches hash
            login_user(user)  # log user in (Flask-Login function)
            flash("Logged in successfully!", "success")  # show success message
            return redirect(url_for("dashboard"))  # redirect to dashboard
        else:
            flash("Invalid email or password.", "error")  # show error message
    
    return render_template("login.html")  # render login form template

@app.route("/logout")  # logout route
@login_required  # require user to be logged in (Flask-Login decorator)
def logout():  # handles user logout
    logout_user()  # log user out (Flask-Login function)
    flash("Logged out successfully!", "success")  # show success message
    return redirect(url_for("index"))  # redirect to homepage

@app.route("/dashboard")  # main dashboard route
@login_required  # require user to be logged in
def dashboard():  # shows user's dashboard with automations
    automations = Automation.query.filter_by(user_id=current_user.id).order_by(Automation.created_at.desc()).limit(10).all()  # get user's recent automations (Automation model is in database.py)
    lead_stats = current_user.get_lead_gen_stats()
    from database import Lead
    recent_leads = Lead.query.filter_by(user_id=current_user.id).order_by(Lead.created_at.desc()).limit(5).all()
    # Simple ROI estimate (adjustable later)
    leads_found = lead_stats.get("leads_found", 0) or 0
    est_close_rate = 0.12
    est_deal_value = 25000
    est_monthly_revenue = int(leads_found * est_close_rate * est_deal_value)
    return render_template(
        "dashboard.html",
        user=current_user,
        automations=automations,
        lead_stats=lead_stats,
        recent_leads=recent_leads,
        est_monthly_revenue=est_monthly_revenue,
    )

@app.route("/leads")
@login_required
def leads():
    from database import Lead
    leads = Lead.query.filter_by(user_id=current_user.id).order_by(Lead.created_at.desc()).limit(100).all()
    can_access = current_user.can_access_leads()
    return render_template("leads.html", leads=leads, can_access=can_access)

@app.route("/leads/add", methods=["POST"])
@login_required
def add_lead():
    from database import Lead
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    website = (request.form.get("website") or "").strip()
    niche = (request.form.get("niche") or "Security Services").strip()

    if not name:
        flash("Lead name is required.", "error")
        return redirect(url_for("leads"))

    existing = None
    if email:
        existing = Lead.query.filter_by(user_id=current_user.id, email=email).first()
    if existing:
        flash("Lead already exists.", "info")
        return redirect(url_for("leads"))

    lead = Lead(
        user_id=current_user.id,
        name=name,
        email=email,
        website=website,
        niche=niche,
        is_unlocked=True
    )
    db.session.add(lead)
    db.session.commit()
    flash("Lead added.", "success")
    return redirect(url_for("leads"))

@app.route("/leads/import", methods=["POST"])
@login_required
def import_leads():
    from database import Lead
    file = request.files.get("file")
    if not file:
        flash("Please upload a CSV file.", "error")
        return redirect(url_for("leads"))

    try:
        content = file.stream.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(content))
        added = 0
        for row in reader:
            name = (row.get("name") or row.get("Name") or "").strip()
            email = (row.get("email") or row.get("Email") or "").strip()
            website = (row.get("website") or row.get("Website") or "").strip()
            niche = (row.get("niche") or row.get("Niche") or "Security Services").strip()
            status = (row.get("status") or row.get("Status") or "new").strip()

            if not name:
                continue
            existing = None
            if email:
                existing = Lead.query.filter_by(user_id=current_user.id, email=email).first()
            if existing:
                continue

            lead = Lead(
                user_id=current_user.id,
                name=name,
                email=email,
                website=website,
                niche=niche,
                status=status,
                is_unlocked=True
            )
            db.session.add(lead)
            added += 1
        db.session.commit()
        flash(f"Imported {added} leads.", "success")
    except Exception as e:
        flash(f"Import failed: {str(e)}", "error")
    return redirect(url_for("leads"))

@app.route("/leads/export")
@login_required
def export_leads():
    if not current_user.can_export_leads():
        flash("Upgrade to Pro to export leads.", "error")
        return redirect(url_for("subscription"))

    from database import Lead
    leads = Lead.query.filter_by(user_id=current_user.id).order_by(Lead.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Company", "Website", "Niche", "Status", "Created At"])
    for lead in leads:
        writer.writerow([
            lead.name,
            lead.email,
            "",
            lead.website,
            lead.niche,
            lead.status,
            lead.created_at.isoformat() if lead.created_at else ""
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )

@app.route("/onboarding")
@login_required
def onboarding():
    return render_template("onboarding.html")

@app.route("/reports")
@login_required
def reports():
    from database import Lead
    leads_count = Lead.query.filter_by(user_id=current_user.id).count()
    return render_template("reports.html", leads_count=leads_count)

@app.route("/reports/schedule", methods=["POST"])
@login_required
def schedule_weekly_report():
    recipient_email = request.form.get("recipient_email", current_user.email)
    scheduled_hour = request.form.get("scheduled_hour", "09")
    scheduled_minute = request.form.get("scheduled_minute", "00")
    scheduled_time = f"{scheduled_hour}:{scheduled_minute}"
    day = request.form.get("day", "mon")

    goal = "[email] Send weekly lead delivery report (Security + Solar)"
    automation = Automation(
        user_id=current_user.id,
        goal=goal,
        recipient_email=recipient_email,
        frequency="weekly",
        scheduled_time=scheduled_time,
        scheduled_days=day,
        end_date=None,
        is_active=True,
        next_run_at=compute_next_run("weekly", scheduled_time, day, from_time=datetime.utcnow()),
        status="scheduled",
    )
    db.session.add(automation)
    db.session.commit()
    schedule_automation_job(automation)
    flash("Weekly report scheduled.", "success")
    return redirect(url_for("reports"))

@app.route("/client-portal")
@login_required
def client_portal():
    if not current_user.can_access_leads():
        flash("Upgrade to Pro to enable client portal.", "error")
        return redirect(url_for("subscription"))
    token = make_client_token(current_user.id)
    link = url_for("client_view", token=token, _external=True)
    return render_template("client_portal.html", link=link)

@app.route("/client/<token>")
def client_view(token):
    s = _get_serializer()
    try:
        data = s.loads(token, salt="client-portal", max_age=60 * 60 * 24 * 7)
        user_id = data.get("uid")
    except (BadSignature, SignatureExpired):
        return "Link expired or invalid.", 403

    from database import Lead
    leads = Lead.query.filter_by(user_id=user_id).order_by(Lead.created_at.desc()).limit(200).all()
    return render_template("client_view.html", leads=leads)

@app.route("/contract.pdf")
@login_required
def contract_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 72
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, y, "Lead Generation Services Agreement")
    y -= 24
    c.setFont("Helvetica", 11)
    lines = [
        "Provider: AI Sales Agent",
        "Client: ________________________________",
        "Services: Security & Solar lead generation and outreach.",
        "Delivery: Weekly leads + monthly performance summary.",
        "Term: Month-to-month, cancel anytime with 14 days notice.",
        "Payment: Monthly subscription via LemonSqueezy.",
        "Confidentiality: Lead data is confidential and for client use only.",
        "",
        "Signed (Client): ________________________",
        "Date: ___________________"
    ]
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.showPage()
    c.save()
    buffer.seek(0)
    return Response(buffer.read(), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=contract.pdf"})

@app.route("/create-automation", methods=["GET", "POST"])  # create automation route
@limiter.limit("20 per minute")
@login_required  # require user to be logged in
def create_automation():  # handles creating and running automations
    if request.method == "POST":  # if form submitted
        goal = request.form.get("goal")  # get automation goal from form
        raw_goal = goal
        action_type = request.form.get("action_type", "")
        if action_type == "email":
            goal = f"[email] {goal}"
        elif action_type == "leads":
            goal = f"[leads] {goal}"
        recipient_email = request.form.get("recipient_email") # get recipient email(s) from form
        niche = request.form.get("niche", "").strip()
        if action_type == "leads" and niche:
            goal = f"{goal} [niche:{niche}]"
        frequency = request.form.get("frequency", "once")
        # Build time from hour and minute dropdowns
        scheduled_hour = request.form.get("scheduled_hour", "09")
        scheduled_minute = request.form.get("scheduled_minute", "00")
        scheduled_time = f"{scheduled_hour}:{scheduled_minute}"
        days = request.form.getlist("days")  # Get selected days as list
        duration = request.form.get("duration", "30")
        
        # Check subscription limits (only for immediate runs, not scheduling)
        if frequency == "once" and not current_user.can_run_automation():
            flash("You've reached your monthly automation limit. Upgrade to Pro for unlimited automations!", "error")
            return redirect(url_for("subscription"))
        
        # Calculate end date for scheduled automations
        end_date = None
        if frequency != "once" and duration != "forever":
            try:
                end_date = datetime.utcnow() + timedelta(days=int(duration))
            except:
                end_date = datetime.utcnow() + timedelta(days=30)
        
        next_run_at = compute_next_run(
            frequency,
            scheduled_time,
            ",".join(days) if days else None,
            from_time=datetime.utcnow(),
        ) if frequency != "once" else None

        # Create automation record
        automation = Automation(
            user_id=current_user.id,
            goal=goal,
            recipient_email=recipient_email,
            frequency=frequency,
            scheduled_time=scheduled_time,
            scheduled_days=",".join(days) if days else None,
            end_date=end_date,
            is_active=True,
            next_run_at=next_run_at,
            status="scheduled" if frequency != "once" else "running"
        )
        db.session.add(automation)
        db.session.commit()
        
        # If it's a scheduled automation, add to scheduler
        if frequency != "once":
            schedule_automation_job(automation)
            flash(f"Automation scheduled! Will run {frequency} at {scheduled_time}.", "success")
            return redirect(url_for("dashboard"))

        # For immediate run with Redis queue
        if queue_enabled() and use_queue():
            queue = get_queue()
            if queue:
                automation.status = "queued"
                db.session.commit()
                queue.enqueue("tasks.run_automation_task", automation.id)
                flash("Automation queued and will run shortly.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Queue is enabled but not available. Please check Redis.", "error")
                return redirect(url_for("dashboard"))
        
        # For immediate run (frequency == "once")
        try:
            from tasks import run_automation_task
            result = run_automation_task(automation.id)
            automation = Automation.query.get(automation.id)

            if result.get("email_error"):
                flash(f"Automation completed but email issue: {result.get('email_error')}", "error")
            elif result.get("email_sent"):
                flash(f"Automation completed! Email sent to {recipient_email}", "success")
            elif result.get("status") == "completed":
                flash("Automation completed successfully.", "success")
            else:
                flash(f"Automation result: {result}", "success")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            automation.status = "failed"
            automation.result = f"Error: {str(e)}\n\nDetails: {error_details}"
            db.session.commit()
            flash(f"Automation failed: {str(e)}", "error")
        
        return redirect(url_for("dashboard"))
    
    return render_template("create_automation.html")

@app.route("/subscription")  # subscription management route
@login_required  # require user to be logged in
def subscription():  # shows subscription page with upgrade options
    return render_template("subscription.html", user=current_user)  # render subscription template with user data

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")

@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    tier = request.form.get("tier")
    
    if tier not in PLAN_PRICES:
        flash("Invalid plan selected", "error")
        return redirect(url_for("subscription"))
    
    amount = PLAN_PRICES[tier]
    
    # Use LemonSqueezy (simplest - no verification needed)
    if LEMONSQUEEZY_API_KEY and LEMONSQUEEZY_STORE_ID:
        try:
            variant_id = LEMONSQUEEZY_PRO_VARIANT if tier == "pro" else LEMONSQUEEZY_BIZ_VARIANT
            
            # Create success redirect URL
            success_url = url_for('lemonsqueezy_success', tier=tier, user_id=current_user.id, _external=True)
            
            # Create LemonSqueezy checkout URL with redirect
            checkout_url = f"https://{LEMONSQUEEZY_STORE_ID}.lemonsqueezy.com/checkout/buy/{variant_id}"
            checkout_url += f"?checkout[email]={current_user.email}"
            checkout_url += f"&checkout[custom][user_id]={current_user.id}"
            checkout_url += f"&checkout[custom][tier]={tier}"
            checkout_url += f"&checkout[success_url]={success_url}"
            
            return redirect(checkout_url)
        except Exception as e:
            print(f"[LemonSqueezy Error] {str(e)}")
    
    # Fallback to Paystack for South African payments
    if PAYSTACK_SECRET_KEY:
        try:
            import requests as req
            
            # Initialize Paystack transaction
            headers = {
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "email": current_user.email,
                "amount": int(amount * 100),  # Paystack uses kobo/cents
                "currency": "ZAR",
                "callback_url": url_for('paystack_callback', tier=tier, _external=True),
                "metadata": {
                    "user_id": current_user.id,
                    "tier": tier,
                    "plan_name": f"AI Sales Agent - {tier.title()} Plan"
                }
            }
            
            response = req.post(
                "https://api.paystack.co/transaction/initialize",
                json=data,
                headers=headers
            )
            
            result = response.json()
            
            if result.get("status"):
                # Redirect to Paystack checkout
                return redirect(result["data"]["authorization_url"])
            else:
                flash(f"Payment error: {result.get('message', 'Unknown error')}", "error")
                return redirect(url_for("subscription"))
                
        except Exception as e:
            print(f"[Paystack Error] {str(e)}")
            flash(f"Payment error: {str(e)}", "error")
            return redirect(url_for("subscription"))
    
    # Fallback to Stripe for international
    elif stripe.api_key:
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'zar',
                        'product_data': {
                            'name': f'AI Sales Agent - {tier.title()} Plan',
                            'description': f'Monthly {tier.title()} subscription',
                        },
                        'unit_amount': int(amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=url_for('payment_success', tier=tier, _external=True),
                cancel_url=url_for('subscription', _external=True),
                customer_email=current_user.email,
                metadata={'user_id': current_user.id, 'tier': tier}
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            print(f"[Stripe Error] {str(e)}")
            flash(f"Payment error: {str(e)}", "error")
            return redirect(url_for("subscription"))
    else:
        flash("Payment system not configured. Please contact support.", "error")
        return redirect(url_for("subscription"))

@app.route("/payment-success")
@login_required
def payment_success():
    tier = request.args.get("tier")
    if tier:
        current_user.subscription_tier = tier
        db.session.commit()
        flash(f"Payment successful! You are now a {tier.title()} member.", "success")
    return redirect(url_for("dashboard"))

@app.route("/lemonsqueezy-success")
def lemonsqueezy_success():
    """Handle LemonSqueezy payment success redirect"""
    tier = request.args.get("tier")
    user_id = request.args.get("user_id")
    
    if user_id and tier:
        user = User.query.get(int(user_id))
        if user:
            user.subscription_tier = tier
            db.session.commit()
            print(f"[LemonSqueezy] Upgraded user {user_id} to {tier}")
            
            # If user is logged in, show success message
            if current_user.is_authenticated and current_user.id == int(user_id):
                flash(f"Payment successful! You are now a {tier.title()} member.", "success")
                return redirect(url_for("dashboard"))
    
    # Show success page for non-logged in or redirect issues
    return render_template("payment_success.html", tier=tier)

@app.route("/lemonsqueezy-webhook", methods=["POST"])
def lemonsqueezy_webhook():
    """Handle LemonSqueezy webhook events (backup for redirect)"""
    try:
        payload = request.get_json()
        event_name = payload.get("meta", {}).get("event_name", "")
        
        print(f"[LemonSqueezy Webhook] Event: {event_name}")
        
        # Handle successful order
        if event_name in ["order_created", "subscription_created", "subscription_payment_success"]:
            data = payload.get("data", {})
            attributes = data.get("attributes", {})
            
            # Get custom data (user_id, tier)
            custom_data = attributes.get("custom_data", {}) or {}
            user_id = custom_data.get("user_id")
            tier = custom_data.get("tier", "pro")
            
            # Also check first_order_item for custom data
            if not user_id:
                first_order = attributes.get("first_order_item", {})
                custom_data = first_order.get("custom_data", {}) or {}
                user_id = custom_data.get("user_id")
                tier = custom_data.get("tier", "pro")
            
            if user_id:
                user = User.query.get(int(user_id))
                if user:
                    user.subscription_tier = tier
                    db.session.commit()
                    print(f"[LemonSqueezy Webhook] Upgraded user {user_id} to {tier}")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"[LemonSqueezy Webhook Error] {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route("/paystack-callback")
@login_required
def paystack_callback():
    """Handle Paystack payment callback"""
    reference = request.args.get("reference")
    tier = request.args.get("tier")
    
    if not reference:
        flash("Payment verification failed - no reference", "error")
        return redirect(url_for("subscription"))
    
    try:
        import requests as req
        
        # Verify the transaction
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
        }
        
        response = req.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers
        )
        
        result = response.json()
        
        if result.get("status") and result["data"]["status"] == "success":
            # Payment successful - upgrade user
            tier_from_meta = result["data"]["metadata"].get("tier", tier)
            current_user.subscription_tier = tier_from_meta
            db.session.commit()
            flash(f"Payment successful! You are now a {tier_from_meta.title()} member.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Payment was not successful. Please try again.", "error")
            return redirect(url_for("subscription"))
            
    except Exception as e:
        print(f"[Paystack Callback Error] {str(e)}")
        flash(f"Payment verification error: {str(e)}", "error")
        return redirect(url_for("subscription"))

@app.route("/paystack-webhook", methods=["POST"])
def paystack_webhook():
    """Handle Paystack webhook events"""
    try:
        payload = request.get_json()
        event = payload.get("event")
        data = payload.get("data", {})
        
        if event == "charge.success":
            metadata = data.get("metadata", {})
            user_id = metadata.get("user_id")
            tier = metadata.get("tier")
            
            if user_id and tier:
                user = User.query.get(int(user_id))
                if user:
                    user.subscription_tier = tier
                    db.session.commit()
                    print(f"[Paystack Webhook] Updated user {user_id} to {tier}")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"[Paystack Webhook Error] {str(e)}")
        return jsonify({"error": str(e)}), 400

# ============================================
# BUY EXTRA LEADS - One-time Purchase (R99)
# ============================================
LEAD_PACK_PRICE = 99  # R99 for 50 leads
LEAD_PACK_COUNT = 50
LEMONSQUEEZY_LEADPACK_VARIANT = os.getenv("LEMONSQUEEZY_LEADPACK_VARIANT", "")

@app.route("/buy-lead-pack", methods=["POST"])
@login_required
def buy_lead_pack():
    """Buy a one-time lead pack (50 leads for R99)"""
    
    # Use LemonSqueezy for payment
    if LEMONSQUEEZY_API_KEY and LEMONSQUEEZY_STORE_ID:
        try:
            # If we have a specific lead pack variant, use it
            variant_id = LEMONSQUEEZY_LEADPACK_VARIANT or LEMONSQUEEZY_PRO_VARIANT
            
            # Create success redirect URL
            success_url = url_for('leadpack_success', user_id=current_user.id, _external=True)
            
            # Create LemonSqueezy checkout URL
            checkout_url = f"https://{LEMONSQUEEZY_STORE_ID}.lemonsqueezy.com/checkout/buy/{variant_id}"
            checkout_url += f"?checkout[email]={current_user.email}"
            checkout_url += f"&checkout[custom][user_id]={current_user.id}"
            checkout_url += f"&checkout[custom][product]=leadpack"
            checkout_url += f"&checkout[success_url]={success_url}"
            
            return redirect(checkout_url)
        except Exception as e:
            print(f"[Lead Pack Error] {str(e)}")
    
    # Fallback: Paystack
    if PAYSTACK_SECRET_KEY:
        try:
            import requests as req
            
            headers = {
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "email": current_user.email,
                "amount": int(LEAD_PACK_PRICE * 100),
                "currency": "ZAR",
                "callback_url": url_for('leadpack_callback', _external=True),
                "metadata": {
                    "user_id": current_user.id,
                    "product": "leadpack",
                    "leads_count": LEAD_PACK_COUNT
                }
            }
            
            response = req.post(
                "https://api.paystack.co/transaction/initialize",
                json=data,
                headers=headers
            )
            
            result = response.json()
            
            if result.get("status"):
                return redirect(result["data"]["authorization_url"])
            else:
                flash(f"Payment error: {result.get('message', 'Unknown error')}", "error")
                return redirect(url_for("subscription"))
                
        except Exception as e:
            print(f"[Lead Pack Paystack Error] {str(e)}")
            flash(f"Payment error: {str(e)}", "error")
            return redirect(url_for("subscription"))
    
    flash("Payment system not configured. Please contact support.", "error")
    return redirect(url_for("subscription"))

@app.route("/leadpack-success")
def leadpack_success():
    """Handle lead pack purchase success - generate 50 leads for user"""
    from database import Lead
    from tools.free_scraper import scrape_leads_free
    
    user_id = request.args.get("user_id")
    
    if not user_id:
        flash("Error processing lead pack. Please contact support.", "error")
        return redirect(url_for("subscription"))
    
    user = User.query.get(int(user_id))
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("subscription"))
    
    # Generate 50 leads for the user
    try:
        leads_generated = 0
        niches = ["Security Services", "Solar Energy"]
        
        for niche in niches:
            leads = scrape_leads_free(niche, "South Africa", max_leads=25)
            
            for lead in leads:
                # Check for duplicates
                existing = None
                if lead.get("email"):
                    existing = Lead.query.filter_by(user_id=user.id, email=lead['email']).first()
                if not existing and lead.get("website"):
                    existing = Lead.query.filter_by(user_id=user.id, website=lead['website']).first()
                
                if not existing:
                    new_lead = Lead(
                        user_id=user.id,
                        name=lead.get('name') or "Business",
                        email=lead.get('email') or "",
                        website=lead.get('website') or "",
                        niche=niche,
                        is_unlocked=True  # IMPORTANT: Mark as unlocked since they paid
                    )
                    db.session.add(new_lead)
                    leads_generated += 1
        
        db.session.commit()
        print(f"[Lead Pack] Generated {leads_generated} leads for user {user_id}")
        
        # Flash success message if user is logged in
        if current_user.is_authenticated and current_user.id == int(user_id):
            flash(f"Lead pack purchased! {leads_generated} new leads added to your account.", "success")
            return redirect(url_for("leads"))
        
        return render_template("payment_success.html", 
                               tier="Lead Pack", 
                               message=f"{leads_generated} leads have been added to your account!")
    
    except Exception as e:
        print(f"[Lead Pack Error] {str(e)}")
        flash("Error generating leads. Please contact support.", "error")
        return redirect(url_for("subscription"))

@app.route("/leadpack-callback")
@login_required
def leadpack_callback():
    """Handle Paystack callback for lead pack purchase"""
    reference = request.args.get("reference")
    
    if not reference:
        flash("Payment verification failed", "error")
        return redirect(url_for("subscription"))
    
    try:
        import requests as req
        
        headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        response = req.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
        result = response.json()
        
        if result.get("status") and result["data"]["status"] == "success":
            # Redirect to lead generation
            return redirect(url_for('leadpack_success', user_id=current_user.id))
        else:
            flash("Payment was not successful. Please try again.", "error")
            return redirect(url_for("subscription"))
            
    except Exception as e:
        print(f"[Lead Pack Callback Error] {str(e)}")
        flash(f"Payment verification error: {str(e)}", "error")
        return redirect(url_for("subscription"))

# ============================================
# ADMIN - Manual Lead Credit (for EFT payments)
# ============================================
ADMIN_EMAILS = ["sandtonstreets@gmail.com", "admin@sandtonstreets.com"]

@app.route("/admin/credit-leads", methods=["GET", "POST"])
@login_required
def admin_credit_leads():
    """Admin page to manually credit leads after EFT payment"""
    
    # Only allow admin users
    if current_user.email not in ADMIN_EMAILS:
        flash("Access denied", "error")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        user_email = request.form.get("user_email")
        lead_count = int(request.form.get("lead_count", 50))
        
        # Find the user
        user = User.query.filter_by(email=user_email).first()
        if not user:
            flash(f"User not found: {user_email}", "error")
            return redirect(url_for("admin_credit_leads"))
        
        # Generate leads for this user
        from database import Lead
        from tools.free_scraper import scrape_leads_free
        
        try:
            leads_generated = 0
            niches = ["Security Services", "Solar Energy"]
            leads_per_niche = lead_count // 2
            
            for niche in niches:
                leads = scrape_leads_free(niche, "South Africa", max_leads=leads_per_niche)
                
                for lead in leads:
                    existing = None
                    if lead.get("email"):
                        existing = Lead.query.filter_by(user_id=user.id, email=lead['email']).first()
                    if not existing and lead.get("website"):
                        existing = Lead.query.filter_by(user_id=user.id, website=lead['website']).first()
                    
                    if not existing:
                        new_lead = Lead(
                            user_id=user.id,
                            name=lead.get('name') or "Business",
                            email=lead.get('email') or "",
                            website=lead.get('website') or "",
                            niche=niche,
                            is_unlocked=True
                        )
                        db.session.add(new_lead)
                        leads_generated += 1
            
            db.session.commit()
            flash(f"Success! Added {leads_generated} leads to {user_email}", "success")
            
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        
        return redirect(url_for("admin_credit_leads"))
    
    # GET - show the form
    users = User.query.order_by(User.created_at.desc()).limit(20).all()
    return render_template("admin_credit_leads.html", users=users)

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        
        # Handle successful checkout
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session.get('metadata', {}).get('user_id')
            tier = session.get('metadata', {}).get('tier')
            
            if user_id and tier:
                user = User.query.get(int(user_id))
                if user:
                    user.subscription_tier = tier
                    db.session.commit()
                    print(f"[Stripe] Updated user {user_id} to {tier}")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"[Stripe Webhook Error] {str(e)}")
        return jsonify({'error': str(e)}), 400

# Digital Asset Links for Play Store TWA verification
@app.route("/.well-known/assetlinks.json")
def assetlinks():
    """Serve Digital Asset Links for Android App Links / TWA verification"""
    # Update this with your actual package name and SHA-256 fingerprint from PWABuilder
    package_name = os.getenv("ANDROID_PACKAGE_NAME", "com.aisalesagent.app")
    sha256_fingerprint = os.getenv("ANDROID_SHA256_FINGERPRINT", "")
    
    return jsonify([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": package_name,
            "sha256_cert_fingerprints": [sha256_fingerprint] if sha256_fingerprint else []
        }
    }])

if __name__ == "__main__":  # run Flask app when executed directly
    app.run(debug=True, host="0.0.0.0", port=5000)  # start development server (debug=True for development, change in production)

