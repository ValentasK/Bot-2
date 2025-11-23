import os
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Sequence
import operator

import aiohttp
import asyncpg
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
POSTGRES_CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")


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
    
@tool
async def get_all_users() -> str:
    """Get a list of all users from the PostgreSQL database."""
    if not POSTGRES_CONNECTION_STRING:
        return "ToolError: Database connection string not configured. Set POSTGRES_CONNECTION_STRING in .env"
    
    try:
        conn = await asyncpg.connect(POSTGRES_CONNECTION_STRING)
        try:
            # Query to get all users
            query = """
                SELECT username as name
                FROM public."User"
                ORDER BY user_id
            """
            rows = await conn.fetch(query)
            
            if not rows:
                return "No users found in the database."
            
            result = f"Total users: {len(rows)}\n\n"
            for row in rows:
                result += f"- {row['name']}\n"
            
            return result
            
        finally:
            await conn.close()
            
    except Exception as e:
        log.exception("Failed to query database")
        return f"ToolError: Database query failed: {e}"


@tool
async def get_user_tasks(username: str) -> str:
    """Get all tasks assigned to a specific user from the PostgreSQL database. Provide the username as a string."""
    if not POSTGRES_CONNECTION_STRING:
        return "ToolError: Database connection string not configured. Set POSTGRES_CONNECTION_STRING in .env"
    
    try:
        conn = await asyncpg.connect(POSTGRES_CONNECTION_STRING)
        try:
            # Query to get user info and their tasks based on username
            query = """
                SELECT u.user_id, u.username, t.task_id, t.title, t.description, t.is_done, t.created_at
                FROM public."User" u
                LEFT JOIN public."Task" t ON u.user_id = t.user_id
                WHERE u.username = $1
                ORDER BY t.task_id
            """
            rows = await conn.fetch(query, username)
            
            if not rows:
                return f"User '{username}' not found in the database."
            
            # Format the results
            user_id = rows[0]['user_id']
            tasks = []
            
            for row in rows:
                if row['task_id']:  # Only if task exists
                    tasks.append({
                        'id': row['task_id'],
                        'title': row['title'],
                        'description': row['description'],
                        'is_done': row['is_done'],
                        'created_at': row['created_at']
                    })
            
            if not tasks:
                return f"User '{username}' (ID: {user_id}) has no tasks assigned."
            
            result = f"Tasks for user '{username}' (ID: {user_id}):\n"
            for task in tasks:
                status = "✅ Done" if task['is_done'] else "⏳ Pending"
                result += f"\n- Task #{task['id']}: {task['title']}\n"
                result += f"  Description: {task['description']}\n"
                result += f"  Status: {status}\n"
                result += f"  Created: {task['created_at']}\n"
            
            return result
            
        finally:
            await conn.close()
            
    except Exception as e:
        log.exception("Failed to query database")
        return f"ToolError: Database query failed: {e}"


@tool
async def add_task_for_user(username: str, title: str, description: str) -> str:
    """Add a new task for a specific user in the PostgreSQL database. Provide username, task title, and description."""
    if not POSTGRES_CONNECTION_STRING:
        return "ToolError: Database connection string not configured. Set POSTGRES_CONNECTION_STRING in .env"
    
    try:
        conn = await asyncpg.connect(POSTGRES_CONNECTION_STRING)
        try:
            # First, get the user_id for the username
            user_query = """
                SELECT user_id FROM public."User"
                WHERE username = $1
            """
            user_row = await conn.fetchrow(user_query, username)
            
            if not user_row:
                return f"User '{username}' not found in the database."
            
            user_id = user_row['user_id']
            
            # Insert the new task
            insert_query = """
                INSERT INTO public."Task" (user_id, title, description, is_done, created_at)
                VALUES ($1, $2, $3, FALSE, NOW())
                RETURNING task_id, title, description, is_done, created_at
            """
            new_task = await conn.fetchrow(insert_query, user_id, title, description)
            
            result = f"✅ Task created successfully for user '{username}':\n"
            result += f"\n- Task ID: {new_task['task_id']}\n"
            result += f"- Title: {new_task['title']}\n"
            result += f"- Description: {new_task['description']}\n"
            result += f"- Status: ⏳ Pending\n"
            result += f"- Created: {new_task['created_at']}\n"
            
            return result
            
        finally:
            await conn.close()
            
    except Exception as e:
        log.exception("Failed to add task to database")
        return f"ToolError: Failed to add task: {e}"


tools = [get_time, http_get, get_all_users, get_user_tasks, add_task_for_user]


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
