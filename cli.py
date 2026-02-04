""" CLI command line interface for users to run the agent . """
from models import AgentState, ToolCall, ControllerConfig
from controller import Controller
from planner import Planner # import planner to decide what to do
from tools.base import ToolRegistry
from tools.implementation import register_tools



def setup_agent() -> Controller:  # creates and returns a Controller with all components set up
    import os  # import os to set environment variables (os is Python standard library)
    os.environ["EMAIL_PASSWORD"] = "mdrf gyhb wfci szqj"  # Gmail app password (16 characters, spaces can be included or removed)
    os.environ["EMAIL_SENDER"] = "sandtonstreets@gmail.com"  # set sender email here
    state = AgentState()  # create agent state to track tasks and progress (AgentState is in models.py)
    tool_registry = ToolRegistry()  # create tool registry to store available tools (ToolRegistry class is in tools/base.py, creates empty registry)
    register_tools(tool_registry)  # register all tools in the registry (register_tools function is in tools/implementation.py, takes ToolRegistry object as parameter)
    controller_config = ControllerConfig()
    planner = Planner(state, tool_registry)  # create planner to decide what to do (Planner.__init__ method is in planner.py, takes state and tool_registry as parameters)
    controller = Controller(state, planner, tool_registry, controller_config)  # create controller to manage everything (Controller.__init__ method is in controller.py, takes state, planner, tool_registry, and config as parameters)
    return controller # return the controller so it can be used to run the agent

def main(): # main function that runs user executes the CLI
   controller = setup_agent() # create controller with all components (setup_agent function is in this file returns Controller object )
   user_goal = input("Enter your goal: ") # ask user what they want the agent to do (input() is a python standard library function)
   result = controller.run(user_goal) # run the agent with user's goal (Controller.run method is in the controller.py takes user string and return completion messege)
   print(result) # display the completion message to the user (print()) is python standard library function)




if __name__ == "__main__": # only run main() if this file is executed directly (not imported)
   main() # run the main function


