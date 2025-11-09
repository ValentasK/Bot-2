import os
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Sequence
import operator

import aiohttp
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

import config

# Load environment variables
load_dotenv()

log = logging.getLogger(config.LOG_NAME)

OPENAI_API_KEY = os.getenv(config.ENV_OPENAI_API_KEY)


# ------------- DEFINE TOOLS -------------
@tool
async def get_time() -> str:
    """Return current UTC time in ISO-8601 format."""
    now = datetime.now(timezone.utc).isoformat()
    return now


@tool
async def http_get(url: str) -> str:
    """HTTP GET a URL and return text (first 10k chars). Use for public pages only."""
    if not (url.startswith("http://") or url.startswith("https://")):
        return "ToolError: invalid URL"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                text = await response.text()
                return text[:10000]
    except Exception as e:
        return f"ToolError: {e}"


tools = [get_time, http_get]


# ------------- DEFINE STATE -------------
class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # Can add more fields like iteration count, user context, etc.


# ------------- DEFINE NODES -------------
def should_continue(state: AgentState) -> str:
    """Decide whether to continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If there are tool calls, route to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    # Otherwise, end
    return "end"


async def call_model(state: AgentState) -> dict:
    """Call the LLM with current state."""
    messages = state["messages"]
    
    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        openai_api_key=OPENAI_API_KEY,
        temperature=0
    )
    llm_with_tools = llm.bind_tools(tools)
    
    response = await llm_with_tools.ainvoke(messages)
    
    # Return dict to update state
    return {"messages": [response]}


# ------------- BUILD GRAPH -------------
def create_agent_graph():
    """Create and compile the LangGraph agent."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # After tools, always go back to agent
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


# ------------- PUBLIC INTERFACE -------------
# Cache the compiled graph
_agent_graph = None


async def langgraph_agent(user_message: str, max_iterations: int = 10) -> str:
    """
    Run the LangGraph agent with the given user message.
    
    Args:
        user_message: The user's input
        max_iterations: Maximum number of iterations (safety limit)
    
    Returns:
        The final response from the agent
    """
    global _agent_graph
    
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    
    try:
        # Initial state
        initial_state = {
            "messages": [HumanMessage(content=user_message)]
        }
        
        log.info("[LangGraph] Starting agent for message: %s", user_message)
        
        # Run the graph
        final_state = await _agent_graph.ainvoke(
            initial_state,
            config={"recursion_limit": max_iterations}
        )
        
        # Extract final response
        messages = final_state["messages"]
        final_message = messages[-1]
        
        if isinstance(final_message, AIMessage):
            return final_message.content or "(no content)"
        else:
            return str(final_message.content)
            
    except Exception as e:
        log.exception("[LangGraph] Agent failed")
        return f"⚠️ LangGraph agent error: {e}"
