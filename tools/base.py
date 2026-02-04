"""Base tool interface and registry for automation tools like email, file operations."""

from typing import Callable, Dict, Any, Optional, List # type hints for tool functions and registries
from models import ToolSpec, ToolCall, Observation, ToolStatus # data models for tool calls and observations

class Tool:
    def __init__(self, spec: ToolSpec, execute_func: Callable[[Dict[str, Any]], Dict[str, Any]]):  # stores tool metadata and actual function that runs it
        self.spec = spec  # keep the tool specification for validation
        self.execute_func = execute_func # the actual function that does the work 
    

    def execute(self, arguments: Dict[str,Any]) -> Observation: # controller calls this to the tool like "send email to sarah'
        

        try:  # wrap in try/except so that errors dont crash the agent
            result = self.execute_func(arguments)  # run the actual function (like sending email)
            if not isinstance(result, dict):  # check if result is a dictionary
                raise ValueError(f"Tool function must return a dictionary, got {type(result)}")
            output_text = result.get('output_text', 'Tool execution successful')  # get the message like "email sent"
            return Observation(call_id="", output_text=output_text, output_payload=result, status=ToolStatus.SUCCEDED)  # package the result so controller can use it (SUCCEDED with one E, not SUCCEEDED)
        except Exception as e:  # if something goes wrong (like network error)
            import traceback
            error_details = traceback.format_exc()  # get full error details
            print(f"[DEBUG ERROR] Tool execution failed: {error_details}")  # debug: show full error
            return Observation(call_id="", output_text=f"Error: {str(e)}", status=ToolStatus.ERRORED, error=str(e))  # tell the controller the tool failed


class ToolRegistry:
    def __init__(self): # creates empty regisrty to store tools 
        self.tools: Dict[str, Tool] = {} # dictionery to store the tools by name like {"send_email":Tool(...),"read_file":Tool(...)}
    
    def register(self, tool: Tool) -> None:  # adds a tool to the registry so agent can find it
        self.tools[tool.spec.name] = tool  # store tool using its name as the key, so agent can find it by name


    def get(self, name: str) -> Optional[Tool]: # controller uses this to find a tool by name like "send email"
        return self.tools.get(name) # hand back the tool object or None if not found 

    def list_tools(self) -> List[str]:  # returns list of all tool names so planner knows what tools are available
        return list(self.tools.keys()) # gets all tool names from the dictionert and return them as a list

