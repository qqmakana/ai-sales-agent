"""Data models shared across the agent system.""" 

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto # lightweight enums for statuses
from typing import Any, Dict, List, Optional # type hints for structured fields
import time #timestamp for tool calls and observations 
import uuid # unique IDs for for tasks and tool calls


class TaskStatus(Enum): #life cycle statuses for tasks
    PENDING =auto()
    IN_PROGRESS =auto()# task actively being worked on
    COMPLETED =auto()# task finished succesfully
    FAILED =auto()# task failed to complete

class ToolStatus(Enum):#lifecycle states for tool calls
    REQUESTED =auto()# planner queued the tool but not started yet
    RUNNING =auto()# tool execution currenty in progress
    SUCCEDED =auto()#tool finished without errors and retuned output
    ERRORED =auto()#tool ran but returnrd an error condition

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    automations = db.relationship('Automation', backref='owner', lazy=True)
    integrations = db.relationship('Integration', backref='owner', lazy=True)

class Integration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_name = db.Column(db.String(50), nullable=False) # e.g., 'trello', 'slack'
    credentials = db.Column(db.JSON, nullable=False) # Store API keys, tokens, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Automation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    goal = db.Column(db.String(200), nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@dataclass(frozen=True) # immutable spec so tools can share it safely
class ToolSpec: #static description of available tool or tool specification
    name:str # human readable tool identifier
    description:str # short description of what the tool does 
    input_schema:Dict[str,Any] # json schema for input data
    output_schema:Dict[str, Any] #json schema for expected output
    timeout_seconds:int = 60 # maximum time to wait for tool response
    max_retries:int = 1 # number of times to try if tool call fails 

@dataclass # runtime record, so we allow mutation
class ToolCall: #runtime record of a tool call or when the tool was called
    spec:ToolSpec #tool specification used
    arguments: Dict[str,Any] #arguments sent to the tool 
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))#unique tracking ID
    status: ToolStatus = ToolStatus.REQUESTED # lifecycle state for this call
    requested_at: float = field(default_factory=time.time) # timestamp when requested
    started_at: Optional[float] = None # timestamp when started  execution
    finished_at: Optional[float] = None # timestamp when finished execution or running
    error: Optional[str] = None # error message if the call fails 


@dataclass #cuptures output from the tool call or a tool response
class Observation: # single observation resulting from a tool call
    call_id: str # unique ID of the tool call that procuced this observation
    output_text: str # natural - language summery retuned by the tool 
    output_payload: Optional[Dict[str,Any]] = None # structured data returned
    status: ToolStatus = ToolStatus.SUCCEDED # final status of the call
    error: Optional[str] = None # error message if the call fails 
    created_at: float = field(default_factory=time.time) #timestamp when we stored this observation

@dataclass # planner-managed unit of work
class Task: # describes a single planner task with hierarchical metadata
    task_id: str #unique identifier for this task
    goal: str # the goal of the task
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0 # higher numbers mean the controller picks it sooner
    parent_id: Optional[str] = None # ID of the parent task if any 
    children: List[str] = field(default_factory=list) # child task IDs
    scratchpad: List[str] = field(default_factory=list) # planner notes for this task


    def add_child(self, child_id: str) -> None : # helper to register a child task
        self.children.append(child_id) # simple list append
    def add_note(self, note: str) -> None: #let planner attach reasoning notes 
        self.scratchpad.append(note) # notepad or scratchpad has notes for later reference


@dataclass # configeration knobs for the controller loop
class ControllerConfig: # settings for the main control loop
    max_steps: int = 100 # maximum number or total number of loop iterations
    max_reties_per_tool: int = 2 # controller rerty limit per tool call
    enable_telemerty: bool = True # to monitor metrics/ logs
    log_level: str = "INFO" # default log level for the controller

@dataclass # overall agent runtime state
class AgentState: # cumpture the agent current state 
    current_task_id: Optional[str] = None # ID of the active task, if any
    tasks: Dict[str,Task] = field(default_factory=dict) # registry of all tasks
    tool_history: List[ToolCall] = field(default_factory=list)#historty of the last tool call for each tool
    observations: List[Observation] = field(default_factory=list)#history of the last observation for the tool call
    planner_context: Dict[str, Any] = field(default_factory=dict)# plannner-specific metadata
    scratchpad: List[str] = field(default_factory = list)# global reasoning notes
    step_count: int = 0 # number of steps taken so far  


    def register_task(self, goal: str, priority: int =0, parent_id: Optional[str] = None) -> str: # create and store a task
        # the goal variable inside the def(register_task) is breaking down the user foal into small tasks
        task_id = str(uuid.uuid4())#
        task = Task(task_id = task_id, goal = goal, priority = priority, parent_id=parent_id) #instantiate the task object
        self.tasks[task_id] = task# store it in the AgentsState regisrty
        if parent_id and parent_id in self.tasks: # link it to the parent if any
            self.tasks[parent_id].add_child(task_id) # parent now tracks child
        return task_id # subtask "Email Sarah the daily to do summary" when the planner adds that task


    def get_active_task(self) -> Optional[Task]: # lets the loop grab a current job like "email Sarah
        if self.current_task_id: # only return the job we are doing now(eg."email Sarah the list") 
            return self.tasks.get(self.current_task_id) # hand back the "email Sarah" task object
        return None # if no job is active, say "nothing" to do right now"   
    
    def set_current_task(self, task_id: Optional[str]) -> None:
          # controller switches to a new job like "email Sarah"
        self.current_task_id = task_id # update which job we're working on

    def append_tool_call(self, tool_call: ToolCall) -> None: # controller adds each tool invocation for history
        self.tool_history.append(tool_call) # add this tool call to the history         

    def append_observation(self, observation: Observation) -> None: # controller adds each tool output like "email sent successfully"
        self.observations.append(observation) # add this result to the observation history






                     # parent now tracks child




















