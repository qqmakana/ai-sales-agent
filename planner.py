"""Planner module - Decides what actions to take based on user goals."""
from models import AgentState, Task, TaskStatus, ToolSpec, ToolCall
from tools.base import ToolRegistry
from typing import Optional, List
from datetime import datetime


class Planner:
    """Professional AI planner that interprets user goals and executes appropriate actions."""
    
    def __init__(self, state: AgentState, tool_registry: ToolRegistry):
        self.state = state
        self.tool_registry = tool_registry

    def break_goal_into_tasks(self, user_goal: str) -> List[str]:
        """Break user's goal into actionable tasks."""
        goal_lower = user_goal.lower()
        
        # Explicit routing based on UI action type (authoritative)
        action_type = self.state.planner_context.get("action_type", "")
        if action_type == "email" or goal_lower.startswith("[email]"):
            return ["Send email"]
        if action_type == "leads" or goal_lower.startswith("[leads]"):
            return ["Search for leads", "Send results summary"]

        # LEAD GENERATION: User wants to find business contacts
        if any(word in goal_lower for word in ["find", "search", "look for", "get me"]) and \
           any(word in goal_lower for word in ["lead", "company", "companies", "business", "contact"]):
            # Check if they also want to send emails to those leads
            if any(word in goal_lower for word in ["send", "email", "pitch", "contact them"]):
                return ["Search for leads", "Create pitch", "Send outreach emails"]
            return ["Search for leads", "Send results summary"]
        
        # SIMPLE EMAIL: User wants to send an email (test, notification, custom message)
        if any(word in goal_lower for word in ["send", "email", "test", "notify", "message", "reminder"]):
            return ["Send email"]
        
        # REPORT: User wants a summary or report
        if any(word in goal_lower for word in ["report", "summary", "update", "status"]):
            return ["Send report email"]
        
        # DEFAULT: Treat as email request
        return ["Send email"]

    def plan_next_action(self) -> Optional[ToolCall]:
        """Decide which tool to call based on current task."""
        active_task = self.state.get_active_task()
        
        if not active_task:
            for task in self.state.tasks.values():
                if task.status == TaskStatus.PENDING:
                    self.state.set_current_task(task.task_id)
                    active_task = task
                    break
        
        if not active_task:
            return None
        
        goal_lower = active_task.goal.lower()
        original_goal = self.state.planner_context.get("original_goal", "")
        recipient = self.state.planner_context.get("recipient_email", "")
        user_email = self.state.planner_context.get("user_email", "AI Sales Agent")
        user_id = self.state.planner_context.get("user_id")
        
        # ========================================
        # TASK: Search for leads
        # ========================================
        if "search" in goal_lower and "lead" in goal_lower:
            tool = self.tool_registry.get("search_leads")
            if tool:
                # Extract niche and location from original goal
                niche = self._extract_niche(original_goal)
                location = self._extract_location(original_goal)
                user_tier = (self.state.planner_context.get("user_tier") or "").lower()
                unlock = user_tier in ["pro", "business"]
                
                return ToolCall(spec=tool.spec, arguments={
                    "niche": niche,
                    "location": location,
                    "user_id": user_id,
                    "unlock": unlock
                })
        
        # ========================================
        # TASK: Create pitch for leads
        # ========================================
        if "create" in goal_lower and "pitch" in goal_lower:
            tool = self.tool_registry.get("personalize_pitch")
            if tool:
                lead_name = "Business Owner"
                niche = self._extract_niche(original_goal)
                
                # Get lead name from previous search
                for obs in self.state.observations:
                    if obs.output_payload and "leads_list" in obs.output_payload:
                        leads = obs.output_payload["leads_list"]
                        if leads:
                            lead_name = leads[0]["name"]
                        break
                
                return ToolCall(spec=tool.spec, arguments={
                    "lead_name": lead_name,
                    "niche": niche
                })
        
        # ========================================
        # TASK: Send outreach emails to leads
        # ========================================
        if "outreach" in goal_lower or ("send" in goal_lower and "pitch" in goal_lower):
            tool = self.tool_registry.get("send_email")
            if tool:
                # Get pitch and lead from previous steps
                pitch_body = ""
                lead_email = ""
                
                for obs in self.state.observations:
                    if obs.output_payload:
                        if "personalized_pitch" in obs.output_payload:
                            pitch_body = obs.output_payload["personalized_pitch"]
                        if "leads_list" in obs.output_payload:
                            leads = obs.output_payload["leads_list"]
                            if leads:
                                lead_email = leads[0]["email"]
                
                if pitch_body and lead_email:
                    return ToolCall(spec=tool.spec, arguments={
                        "to": lead_email,
                        "subject": "Partnership Opportunity - Let's Connect",
                        "body": pitch_body,
                        "sender_name": user_email,
                        "reply_to": user_email
                    })
        
        # ========================================
        # TASK: Send results summary (after lead search)
        # ========================================
        if "send" in goal_lower and ("result" in goal_lower or "summary" in goal_lower):
            tool = self.tool_registry.get("send_email")
            if tool:
                # Get leads found from previous step
                leads_found = []
                for obs in self.state.observations:
                    if obs.output_payload and "leads_list" in obs.output_payload:
                        leads_found = obs.output_payload["leads_list"]
                        break
                
                current_time = datetime.now().strftime('%H:%M on %A, %B %d, %Y')
                
                if leads_found:
                    leads_text = "\n".join([f"  • {l['name']} - {l['email']}" for l in leads_found])
                    body = f"""Hello,

Your AI Sales Agent has completed your request!

══════════════════════════════════════════════════
LEADS FOUND ({len(leads_found)} contacts)
══════════════════════════════════════════════════

{leads_text}

══════════════════════════════════════════════════
NEXT STEPS
══════════════════════════════════════════════════

1. Review the leads above
2. Visit your dashboard to manage contacts
3. Set up automated outreach campaigns

Request: {original_goal}
Completed: {current_time}

Best regards,
AI Sales Agent
"""
                else:
                    body = f"""Hello,

Your request has been processed.

Request: {original_goal}
Completed: {current_time}

No leads were found matching your criteria. Try broadening your search.

Best regards,
AI Sales Agent
"""
                
                return ToolCall(spec=tool.spec, arguments={
                    "to": recipient,
                    "subject": f"AI Sales Agent - Results Ready",
                    "body": body,
                    "sender_name": user_email,
                    "reply_to": user_email
                })
        
        # ========================================
        # TASK: Send email (simple/test/custom)
        # ========================================
        if "send" in goal_lower and ("email" in goal_lower or "report" in goal_lower):
            tool = self.tool_registry.get("send_email")
            if tool:
                current_time = datetime.now().strftime('%H:%M on %A, %B %d, %Y')
                
                # Create professional email based on user's request
                body = f"""Hello,

This email was sent by your AI Sales Agent automation.

══════════════════════════════════════════════════
YOUR REQUEST
══════════════════════════════════════════════════

{original_goal}

══════════════════════════════════════════════════
STATUS
══════════════════════════════════════════════════

✓ Automation executed successfully
✓ Email delivered at {current_time}
✓ Sender: {user_email}

══════════════════════════════════════════════════
WHAT'S NEXT?
══════════════════════════════════════════════════

Your AI Sales Agent can help you:
• Find business leads in any industry
• Send personalized outreach campaigns  
• Schedule recurring email automations

Visit your dashboard to explore more features.

Best regards,
AI Sales Agent
Automated Email System
"""
                
                # Determine subject based on goal
                if "test" in original_goal.lower():
                    subject = "Test Email - AI Sales Agent Working!"
                elif "report" in original_goal.lower():
                    subject = f"Daily Report - {datetime.now().strftime('%B %d, %Y')}"
                elif "reminder" in original_goal.lower():
                    subject = "Reminder from AI Sales Agent"
                else:
                    subject = "Message from AI Sales Agent"
                
                return ToolCall(spec=tool.spec, arguments={
                    "to": recipient,
                    "subject": subject,
                    "body": body,
                    "sender_name": user_email,
                    "reply_to": user_email
                })
        
        # Mark unmatched tasks as completed and try next
        active_task.status = TaskStatus.COMPLETED
        self.state.set_current_task(None)
        return self.plan_next_action()
    
    def _extract_niche(self, goal: str) -> str:
        """Extract business niche from user goal."""
        selected = self.state.planner_context.get("selected_niche")
        if selected:
            return selected

        if "[niche:" in goal.lower():
            start = goal.lower().find("[niche:")
            end = goal.find("]", start)
            if end != -1:
                return goal[start + 7:end].strip()

        goal_lower = goal.lower()
        
        if "security" in goal_lower or "guard" in goal_lower:
            return "Security Services"
        elif "solar" in goal_lower or "energy" in goal_lower:
            return "Solar & Renewable Energy"
        elif "logistics" in goal_lower or "transport" in goal_lower or "truck" in goal_lower:
            return "Logistics & Transport"
        elif "cleaning" in goal_lower:
            return "Commercial Cleaning"
        elif "it" in goal_lower or "tech" in goal_lower or "software" in goal_lower:
            return "IT & Technology"
        elif "finance" in goal_lower or "financial" in goal_lower:
            return "Financial Services"
        elif "software" in goal_lower or "saas" in goal_lower or "b2b" in goal_lower:
            return "B2B Software"
        elif "restaurant" in goal_lower or "food" in goal_lower:
            return "Restaurants & Hospitality"
        elif "property" in goal_lower or "real estate" in goal_lower:
            return "Real Estate"
        else:
            return "General Business"
    
    def _extract_location(self, goal: str) -> str:
        """Extract location from user goal."""
        goal_lower = goal.lower()
        
        locations = {
            "johannesburg": "Johannesburg",
            "joburg": "Johannesburg", 
            "jhb": "Johannesburg",
            "cape town": "Cape Town",
            "durban": "Durban",
            "pretoria": "Pretoria",
            "sandton": "Sandton",
            "soweto": "Soweto",
            "port elizabeth": "Port Elizabeth",
            "bloemfontein": "Bloemfontein",
            "gauteng": "Gauteng",
            "western cape": "Western Cape",
        }
        
        for key, value in locations.items():
            if key in goal_lower:
                return value
        
        return "South Africa"
