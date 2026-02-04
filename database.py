"""Database models and setup for user authentication and subscriptions."""
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from enum import Enum

db = SQLAlchemy()  # database object that will be initialized with Flask app

class SubscriptionTier(Enum):  # subscription levels for monetization
    FREE = "free"  # free tier: 10 automations/month
    PRO = "pro"  # pro tier: $9.99/month, unlimited automations
    BUSINESS = "business"  # business tier: $29.99/month, team features + API

class User(db.Model):  # user account model for authentication and subscriptions
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)  # unique user ID
    email = db.Column(db.String(120), unique=True, nullable=False)  # user email (unique, required)
    password_hash = db.Column(db.String(255), nullable=False)  # hashed password (bcrypt hash)
    subscription_tier = db.Column(db.String(20), default=SubscriptionTier.FREE.value)  # subscription level (default: free)
    stripe_customer_id = db.Column(db.String(255), nullable=True)  # Stripe customer ID for billing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # account creation timestamp
    automations_count = db.Column(db.Integer, default=0)  # track how many automations user has run this month
    
    # Relationship to automations (one user can have many automations)
    automations = db.relationship("Automation", backref="user", lazy=True)  # link to Automation model
    # Relationship to integrations (one user can have many integrations)
    integrations = db.relationship("Integration", backref="owner_user", lazy=True)

    def get_lead_gen_stats(self):
        """Calculate real stats for the AI Sales Engine tracker across all niches."""
        from database import Lead
        
        # 1. Total Leads Found (across all niches)
        leads_found = Lead.query.filter_by(user_id=self.id).count()
        
        # 2. Total Pitches Sent (count automations that sent pitches)
        pitches_sent = 0
        for auto in self.automations:
            if auto.status == "completed" and auto.result:
                if "email sent" in auto.result.lower() or "pitch sent" in auto.result.lower():
                    pitches_sent += 1
        
        # 3. Dynamic Estimated Value (R15,000 for Security, R10,000 for Logistics, R8,000 for Solar)
        # We'll calculate a weighted average based on the leads in the CRM
        total_value = 0
        user_leads = Lead.query.filter_by(user_id=self.id).all()
        for lead in user_leads:
            niche = (lead.niche or "").lower()
            if "security" in niche:
                total_value += 15000
            elif "logistics" in niche:
                total_value += 10000
            elif "solar" in niche:
                total_value += 8000
            else:
                total_value += 5000 # Default value for other niches
        
        # 4. Get the most active niche for the UI title
        active_niche = "Multi-Niche"
        if user_leads:
            from collections import Counter
            niches = [l.niche for l in user_leads if l.niche]
            if niches:
                active_niche = Counter(niches).most_common(1)[0][0]

        return {
            "leads_found": leads_found,
            "pitches_sent": pitches_sent,
            "estimated_value": f"R {total_value:,}",
            "active_niche": active_niche
        }

    def is_authenticated(self):  # Flask-Login requirement
        return True
    
    def is_active(self):  # Flask-Login requirement
        return True
    
    def is_anonymous(self):  # Flask-Login requirement
        return False
    
    def get_id(self):  # Flask-Login requirement - returns user ID as string
        return str(self.id)
    
    def can_run_automation(self) -> bool:  # check if user can run automation based on subscription tier
        # Builder mode bypass for local testing
        import os
        if os.getenv("BUILDER_MODE", "false").lower() == "true":
            return True
        if self.subscription_tier == SubscriptionTier.FREE.value:
            return self.automations_count < 3  # free tier: max 3 for testing (was 10)
        return True  # pro and business: unlimited

    def can_access_leads(self) -> bool:
        import os
        if os.getenv("BUILDER_MODE", "false").lower() == "true":
            return True
        return self.subscription_tier in [SubscriptionTier.PRO.value, SubscriptionTier.BUSINESS.value]

    def can_export_leads(self) -> bool:
        return self.can_access_leads()
    
    def increment_automation_count(self):  # increment usage counter after running automation
        self.automations_count += 1
        db.session.commit()

class Automation(db.Model):  # stores user's automation runs and history
    __tablename__ = "automations"
    
    id = db.Column(db.Integer, primary_key=True)  # unique automation ID
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # link to user who created it
    goal = db.Column(db.String(500), nullable=False)  # user's goal (e.g., "Email Sarah the daily summary")
    recipient_email = db.Column(db.String(120), nullable=True) # The email where the summary will be sent
    frequency = db.Column(db.String(50), default="once") # once, daily, weekly, custom
    scheduled_time = db.Column(db.String(20), nullable=True) # e.g., "09:00"
    scheduled_days = db.Column(db.String(100), nullable=True) # e.g., "mon,wed,fri" for weekly/custom
    end_date = db.Column(db.DateTime, nullable=True)  # when the scheduled automation should stop
    is_active = db.Column(db.Boolean, default=True)  # for pausing/stopping scheduled jobs
    last_run = db.Column(db.DateTime, nullable=True)  # when this automation last ran
    run_count = db.Column(db.Integer, default=0)  # how many times this has run
    next_run_at = db.Column(db.DateTime, nullable=True)  # next scheduled run (UTC)
    locked_at = db.Column(db.DateTime, nullable=True)  # lock for distributed schedulers
    status = db.Column(db.String(50), default="pending")  # automation status: pending, running, completed, failed, scheduled
    result = db.Column(db.Text, nullable=True)  # result message from agent execution
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # when automation was created
    completed_at = db.Column(db.DateTime, nullable=True)  # when automation finished

class Integration(db.Model):  # stores user's connected services (e.g., Trello, Slack)
    __tablename__ = "integrations"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_name = db.Column(db.String(50), nullable=False) # e.g., 'trello', 'slack'
    credentials_json = db.Column(db.Text, nullable=False) # Store API keys, tokens as JSON string
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Lead(db.Model):  # stores found leads for sales prospecting
    __tablename__ = "leads"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    website = db.Column(db.String(200), nullable=True)
    niche = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default="new") # new, pitched, interested, closed
    is_unlocked = db.Column(db.Boolean, default=False) # New field for Platform-Only strategy
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db(app):  # initialize database with Flask app (called from app.py)
    db.init_app(app)  # connect database to Flask app
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    auto_create = os.getenv("AUTO_CREATE_DB", "true").lower() == "true"
    # Only auto-create tables for local SQLite or when explicitly enabled.
    if auto_create and (db_url.startswith("sqlite:///") or db_url.startswith("sqlite:")):
        with app.app_context():
            db.create_all()


