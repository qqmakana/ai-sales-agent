""" Controller module that manages the agent and coordinates planner, tools and state. """
from ntpath import exists
from models import AgentState, ToolCall, ControllerConfig, Observation, ToolStatus, TaskStatus  # import data models we need
from planner import Planner # import planner so controller can ask what to do next
from tools.base import ToolRegistry  # import tool registry so controller can call tools 
import time # for tracking execution time 

class Controller: # main loop that manages the robot and manages automation sytem or  allcomponents
    def __init__(self, state: AgentState, planner: Planner, tool_registry: ToolRegistry, controller_config: ControllerConfig):
        self.state = state  # save agent state so the controller can track tasks and progress
        self.planner = planner  # save planner so controller can ask what to do next
        self.tool_registry = tool_registry  # save tool registry so the controller can run tools
        self.controller_config = controller_config  # save config so controller can check max_steps and other settings

    def run(self, user_goal: str) -> str:  # main method that starts the agent with a user goal like "Email Sarah the daily summary"
        # Step 1: Break user goal into tasks and register them
        task_steps = self.planner.break_goal_into_tasks(user_goal)  # ask planner to break user goal into steps (break_goal_into_tasks method is in planner.py)
        for task_goal in task_steps:  # register each step as a task
            self.state.register_task(task_goal)  # create and store each task in the state (register_task method is in models.py AgentState class)
        
        # Step 2: Main loop - keep asking planner what to do and executing tools until done
        while self.state.step_count < self.controller_config.max_steps:  # keep looping until we hit max steps limit (step_count is in models.py AgentState, max_steps is in models.py ControllerConfig)
            self.state.step_count += 1  # increment step counter to track how many loops we've done
            tool_call = self.planner.plan_next_action()  # ask planner what tool to call next (plan_next_action method is in planner.py, returns Optional[ToolCall] from models.py)
            if not tool_call:  # if planner returns None, no more actions to take
                print("[DEBUG] No more tool calls, exiting loop")  # debug: show when planner returns None
                break  # exit loop, we're done with all tasks
            print(f"[DEBUG] Planner returned tool: {tool_call.spec.name}")  # debug: show which tool planner chose
            
            # Execute the tool call (ToolCall class is in models.py, Tool.execute method is in tools/base.py)
            tool = self.tool_registry.get(tool_call.spec.name)  # get tool from registry: tool_call.spec.name gives us the tool name (tool_call is ToolCall from models.py, spec is ToolSpec from models.py, then ToolRegistry.get in tools/base.py)
            if not tool:  # if tool not found in registry, skip this tool call
                continue  # skip this iteration, tool doesn't exist
            tool_call.status = ToolStatus.RUNNING  # mark tool as running (ToolStatus enum is in models.py)
            tool_call.started_at = time.time()  # record when tool call started (time.time() is Python standard library)
            observation = tool.execute(tool_call.arguments)  # execute the tool with arguments and get result (Tool.execute method is in tools/base.py, returns Observation from models.py)
            print(f"[DEBUG] Tool: {tool_call.spec.name}, Status: {observation.status}, Output: {observation.output_text}")  # debug: show what tool executed and result
            tool_call.finished_at = time.time()  # record when tool execution finished (time.time() is Python standard library)
            tool_call.status = observation.status  # update tool_call status based on observation (observation.status is ToolStatus from models.py)
            self.state.append_tool_call(tool_call)  # store tool call in the state history (append_tool_call method is in models.py AgentState class)
            self.state.append_observation(observation)  # store observation in the state history (append_observation method is in models.py AgentState class)
            
            # Mark current task as completed if tool succeeded (TaskStatus enum is in models.py)
            active_task = self.state.get_active_task()  # get the current active task (get_active_task method is in models.py AgentState)
            if active_task and observation.status == ToolStatus.SUCCEDED:  # if task exists and tool succeeded
                active_task.status = TaskStatus.COMPLETED  # mark task as completed (TaskStatus.COMPLETED is in models.py)
                self.state.set_current_task(None)  # clear current task so planner can find next one (set_current_task method is in models.py AgentState)
                print(f"[DEBUG] Task '{active_task.goal}' marked as completed")  # debug: show task completion
        
        return "Agent execution completed"  # return completion message






