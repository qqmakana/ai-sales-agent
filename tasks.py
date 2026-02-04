from datetime import datetime
from app import app
from cli import setup_agent
from database import db, Automation, User
from scheduler_utils import compute_next_run
from tools.implementation import send_email_function


def _strip_prefix(goal: str) -> str:
    if goal.startswith("[email] "):
        return goal[len("[email] "):]
    if goal.startswith("[leads] "):
        return goal[len("[leads] "):]
    return goal


def _extract_niche(goal: str) -> tuple[str, str]:
    selected_niche = ""
    if "[niche:" in goal:
        start = goal.lower().find("[niche:")
        end = goal.find("]", start)
        if end != -1:
            selected_niche = goal[start + 7:end].strip()
            goal = (goal[:start] + goal[end + 1:]).strip()
    return selected_niche, goal


def run_automation_task(automation_id: int) -> dict:
    """Execute an automation and update DB state."""
    with app.app_context():
        automation = Automation.query.get(automation_id)
        if not automation or not automation.is_active:
            return {"status": "skipped", "message": "Automation not active"}

        user = User.query.get(automation.user_id)
        if not user:
            return {"status": "skipped", "message": "User not found"}

        # Expire schedules
        if automation.end_date and datetime.utcnow() > automation.end_date:
            automation.is_active = False
            automation.status = "expired"
            automation.locked_at = None
            db.session.commit()
            return {"status": "expired", "message": "Automation expired"}

        # Special case: weekly lead delivery report
        if "weekly lead delivery report" in automation.goal.lower():
            from database import Lead
            leads = Lead.query.filter_by(user_id=user.id).order_by(Lead.created_at.desc()).limit(20).all()
            lead_lines = []
            for lead in leads:
                lead_lines.append(f"- {lead.name} | {lead.email} | {lead.website} | {lead.niche}")

            plain = "Weekly Lead Delivery Report\n\n"
            plain += f"Total leads in CRM: {len(leads)}\n\n"
            plain += "\n".join(lead_lines) if lead_lines else "No leads yet."

            html_rows = ""
            for lead in leads:
                html_rows += f"""
                <tr>
                  <td>{lead.name}</td>
                  <td>{lead.email}</td>
                  <td>{lead.website}</td>
                  <td>{lead.niche}</td>
                </tr>"""

            html = f"""
            <div style="font-family:Arial,sans-serif">
              <h2 style="margin:0;color:#111827">AI Sales Agent</h2>
              <p style="color:#6b7280">Weekly Lead Delivery Report</p>
              <p><strong>Total leads:</strong> {len(leads)}</p>
              <table style="width:100%;border-collapse:collapse" border="1" cellpadding="8">
                <thead style="background:#f3f4f6">
                  <tr>
                    <th align="left">Name</th>
                    <th align="left">Email</th>
                    <th align="left">Website</th>
                    <th align="left">Niche</th>
                  </tr>
                </thead>
                <tbody>
                  {html_rows if html_rows else '<tr><td colspan="4">No leads yet</td></tr>'}
                </tbody>
              </table>
            </div>
            """

            send_email_function({
                "to": automation.recipient_email,
                "subject": "Weekly Lead Delivery Report",
                "body": plain,
                "html_body": html,
                "sender_name": "AI Sales Agent",
                "reply_to": user.email
            })

            automation.last_run = datetime.utcnow()
            automation.run_count += 1
            automation.status = "scheduled"
            automation.result = "Weekly lead delivery report sent."
            automation.next_run_at = compute_next_run(
                automation.frequency,
                automation.scheduled_time,
                automation.scheduled_days,
                from_time=datetime.utcnow(),
            )
            db.session.commit()
            return {"status": "completed", "result": "Weekly report sent"}

        controller = setup_agent()
        controller.state.planner_context["recipient_email"] = automation.recipient_email
        controller.state.planner_context["user_email"] = user.email
        controller.state.planner_context["user_tier"] = user.subscription_tier
        controller.state.planner_context["user_id"] = user.id
        controller.state.planner_context["action_type"] = (
            "leads" if automation.goal.startswith("[leads]") else "email"
        )
        selected_niche, cleaned = _extract_niche(automation.goal)
        controller.state.planner_context["selected_niche"] = selected_niche
        controller.state.planner_context["original_goal"] = _strip_prefix(cleaned)

        try:
            result = controller.run(automation.goal)

            email_sent = False
            email_error = None
            for tool_call in controller.state.tool_history:
                if tool_call.spec.name == "send_email":
                    for obs in controller.state.observations:
                        if "sent successfully" in obs.output_text.lower():
                            email_sent = True
                        elif "error" in obs.output_text.lower() or "simulated" in obs.output_text.lower():
                            email_error = obs.output_text

            automation.last_run = datetime.utcnow()
            automation.run_count += 1
            automation.locked_at = None

            if automation.frequency == "once":
                automation.status = "completed"
                automation.completed_at = datetime.utcnow()
            else:
                automation.status = "scheduled"
                automation.next_run_at = compute_next_run(
                    automation.frequency,
                    automation.scheduled_time,
                    automation.scheduled_days,
                    from_time=datetime.utcnow(),
                )

            if email_error:
                automation.result = f"{result}\n\n⚠️ Email Status: {email_error}"
            elif email_sent:
                automation.result = f"{result}\n\n✅ Email sent to: {automation.recipient_email}"
            else:
                automation.result = result

            user.automations_count += 1
            db.session.commit()

            return {
                "status": "completed",
                "result": result,
                "email_sent": email_sent,
                "email_error": email_error,
            }
        except Exception as e:
            automation.status = "failed"
            automation.result = f"Error: {str(e)}"
            automation.locked_at = None
            db.session.commit()
            return {"status": "failed", "error": str(e)}
