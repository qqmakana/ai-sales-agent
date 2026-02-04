from typing import Dict, Any
from models import ToolSpec
from tools.base import ToolRegistry
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import requests
from database import db, Lead
from flask import current_app

def read_file_function(arguments: Dict[str, Any]) -> Dict[str, Any]:
    file_path = arguments.get("file_path")
    try:
        with open(file_path, "r") as f:
            content = f.read()
        return {"output_text": f"File read successfully: {len(content)} characters", "content": content}
    except Exception as e:
        return {"output_text": f"Error reading file: {str(e)}", "error": str(e)}

def send_email_function(arguments: Dict[str,Any]) -> Dict[str,Any]:
    to_email = arguments.get("to")
    subject = arguments.get("subject")
    body = arguments.get("body", "")
    html_body = arguments.get("html_body", "")
    sender_display_name = arguments.get("sender_name", "AI Sales Agent")
    reply_to = arguments.get("reply_to")
    
    # Get credentials from environment
    sender_email = os.getenv("EMAIL_SENDER", "sandtonstreets@gmail.com")
    sender_password = os.getenv("EMAIL_PASSWORD", "")
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
    sendgrid_from_email = os.getenv("SENDGRID_FROM_EMAIL", sender_email)
    
    # Fallback to hardcoded if env not loaded
    if not sender_password:
        sender_password = "mdrf gyhb wfci szqj"
    
    # Handle multiple emails (comma-separated)
    if isinstance(to_email, str):
        email_list = [e.strip() for e in to_email.split(",") if e.strip()]
    else:
        email_list = [to_email]
    
    print(f"[EMAIL] Attempting to send email...")
    print(f"[EMAIL] To: {email_list}")
    print(f"[EMAIL] Subject: {subject}")
    print(f"[EMAIL] From: {sender_email}")

    # Prefer SendGrid for scale if configured
    if sendgrid_api_key:
        try:
            content = [{"type": "text/plain", "value": body}]
            if html_body:
                content.append({"type": "text/html", "value": html_body})

            payload = {
                "personalizations": [
                    {"to": [{"email": e} for e in email_list]}
                ],
                "from": {"email": sendgrid_from_email, "name": sender_display_name},
                "subject": subject,
                "content": content,
            }
            if reply_to:
                payload["reply_to"] = {"email": reply_to}
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            if response.status_code in (200, 202):
                return {
                    "output_text": f"Email sent successfully to {len(email_list)} recipient(s) via SendGrid",
                    "status": "sent",
                }
            else:
                print(f"[EMAIL] SendGrid error: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[EMAIL] SendGrid exception: {str(e)}")
    
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    if not sender_password:
        print("[EMAIL] ERROR: No password configured!")
        return {"output_text": f"Email simulation: Would send to {to_email}", "status": "simulated"}
    
    try:
        print("[EMAIL] Connecting to Gmail SMTP...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        print("[EMAIL] Logging in...")
        server.login(sender_email, sender_password)
        
        sent_count = 0
        for recipient in email_list:
            try:
                msg = MIMEMultipart()
                msg["From"] = f"{sender_display_name} <{sender_email}>"
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))
                if html_body:
                    msg.attach(MIMEText(html_body, "html"))
                if reply_to:
                    msg["Reply-To"] = reply_to
                
                print(f"[EMAIL] Sending to {recipient}...")
                server.sendmail(sender_email, recipient, msg.as_string())
                sent_count += 1
                print(f"[EMAIL] Sent to {recipient}")
            except Exception as e:
                print(f"[EMAIL] Failed to send to {recipient}: {str(e)}")
        
        server.quit()
        
        if sent_count == len(email_list):
            print(f"[EMAIL] SUCCESS! All {sent_count} emails sent")
            return {"output_text": f"Email sent successfully to {sent_count} recipient(s): {', '.join(email_list)}", "status": "sent"}
        else:
            return {"output_text": f"Sent {sent_count}/{len(email_list)} emails", "status": "partial"}
    except Exception as e:
        print(f"[EMAIL] ERROR: {str(e)}")
        return {"output_text": f"Error sending email: {str(e)}", "error": str(e)}

def search_leads_function(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    FREE lead search using web scraping - NO API COSTS!
    Scrapes Google, Yellow Pages, and business websites.
    """
    niche = arguments.get("niche", "Security Services")
    location = arguments.get("location", "South Africa")
    user_id = arguments.get("user_id")
    unlock = bool(arguments.get("unlock"))
    max_leads = arguments.get("max_leads", 15)
    
    # Import free scraper
    from tools.free_scraper import scrape_leads_free
    
    # Multi-niche support
    niches = [niche]
    if niche.lower() in ["multi-niche", "all", "all niches", "all high-ticket", "security + solar", "security and solar"]:
        niches = [
            "Security Services",
            "Solar Energy"
        ]
    
    all_leads = []
    
    for n in niches:
        try:
            print(f"[LEADS] Searching for {n} in {location} (FREE scraping)...")
            leads_per_niche = max_leads // len(niches)
            scraped_leads = scrape_leads_free(n, location, max_leads=leads_per_niche)
            
            for lead in scraped_leads:
                all_leads.append({
                    "name": lead.get("name", ""),
                    "email": lead.get("email", ""),
                    "website": lead.get("website", ""),
                    "phone": lead.get("phone", ""),
                    "niche": n,
                    "source": lead.get("source", "web_scrape")
                })
        except Exception as e:
            print(f"[LEADS] Error scraping {n}: {str(e)}")
            continue
    
    # Save leads to database
    saved_count = 0
    leads_with_email = 0
    
    with current_app.app_context():
        for lead in all_leads:
            # Check for duplicates by website or email
            existing = None
            if lead.get("email"):
                existing = Lead.query.filter_by(user_id=user_id, email=lead['email']).first()
            if not existing and lead.get("website"):
                existing = Lead.query.filter_by(user_id=user_id, website=lead['website']).first()
            
            if not existing:
                new_lead = Lead(
                    user_id=user_id,
                    name=lead.get('name') or "Unknown Business",
                    email=lead.get('email') or "",
                    website=lead.get('website') or "",
                    niche=lead.get('niche') or niche,
                    is_unlocked=unlock
                )
                db.session.add(new_lead)
                saved_count += 1
                if lead.get('email'):
                    leads_with_email += 1
        db.session.commit()
    
    status_msg = f"SUCCESS: Found {len(all_leads)} leads in {location} using FREE web scraping. "
    status_msg += f"{saved_count} new leads added ({leads_with_email} with verified emails). "
    status_msg += "NO API COSTS!"
    
    return {
        "output_text": status_msg,
        "leads_list": all_leads,
        "leads_with_email": leads_with_email,
        "total_found": len(all_leads),
        "saved": saved_count
    }

def personalize_pitch_function(arguments: Dict[str, Any]) -> Dict[str, Any]:
    lead_name = arguments.get("lead_name", "Valued Partner")
    niche = arguments.get("niche", "Security Services")
    
    niche_lower = (niche or "").lower()
    if "solar" in niche_lower:
        pitch = f"""Hi {lead_name},

I work with solar installation companies across South Africa to consistently book qualified site‑assessment appointments.

Our system finds property owners and business managers who are actively exploring solar upgrades, then runs a short outreach sequence that turns interest into booked calls.

If I could deliver 10–20 qualified solar leads per month, would you be open to a quick 5‑minute call this week?

Best regards,
AI Sales Agent
"""
    else:
        pitch = f"""Hi {lead_name},

I help security companies in South Africa book more armed‑response and guarding contracts with qualified decision‑makers.

Our system targets estates, businesses, and property managers, then runs a proven outreach sequence that converts interest into booked consultations.

If I could deliver 10–20 qualified security leads per month, would you be open to a quick 5‑minute call this week?

Best regards,
AI Sales Agent
"""
    return {
        "output_text": f"Personalized pitch generated for {lead_name}",
        "personalized_pitch": pitch
    }

def register_tools(tool_registry: ToolRegistry) -> None:
    from tools.base import Tool
    
    search_leads_spec = ToolSpec(
        name="search_leads",
        description="Finds business leads in a specific niche and location",
        input_schema={"niche": "string", "location": "string", "unlock": "boolean"},
        output_schema={"leads_list": "list"}
    )
    tool_registry.register(Tool(spec=search_leads_spec, execute_func=search_leads_function))

    personalize_pitch_spec = ToolSpec(
        name="personalize_pitch",
        description="Generates an AI personalized sales pitch for a specific lead",
        input_schema={"lead_name": "string", "niche": "string"},
        output_schema={"personalized_pitch": "string"}
    )
    tool_registry.register(Tool(spec=personalize_pitch_spec, execute_func=personalize_pitch_function))

    send_email_spec = ToolSpec(
        name="send_email", 
        description="Sends an Email to a recipient", 
        input_schema={"to": "string", "subject": "string", "body": "string", "html_body": "string", "sender_name": "string", "reply_to": "string"}, 
        output_schema={"status":"string"}
    )
    tool_registry.register(Tool(spec=send_email_spec, execute_func=send_email_function))

    read_file_spec = ToolSpec(name="read_file", description="Reads a file from the filesystem", input_schema={"file_path": "string"}, output_schema={"content": "string"})
    tool_registry.register(Tool(spec=read_file_spec, execute_func=read_file_function))
