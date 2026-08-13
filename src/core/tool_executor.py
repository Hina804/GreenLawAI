from typing import Dict, Any, List
from loguru import logger
from dataclasses import dataclass

@dataclass
class ToolOutput:
    status: str
    data: Any
    message: str = ""
    meta: Dict[str, Any] = None

class ToolExecutor:
    """
    STRICT TOOL EXECUTION LAYER
    
    Purpose:
    - Centralize tool execution
    - Enforce tool output schema
    - Prevent agents from calling tools directly
    - Provide audit logs for tool usage
    """
    
    @staticmethod
    async def execute(tool: Any, **kwargs) -> ToolOutput:
        tool_name = getattr(tool, "name", "unknown_tool")
        logger.info(f"[ToolExecutor] Executing {tool_name} with args: {kwargs}")
        
        try:
            # Check if execute is async
            if hasattr(tool, "execute"):
                if hasattr(tool.execute, "__call__"):
                    import inspect
                    if inspect.iscoroutinefunction(tool.execute):
                        raw_result = await tool.execute(**kwargs)
                    else:
                        raw_result = tool.execute(**kwargs)
                else:
                    raise ValueError(f"Tool {tool_name} has no callable execute method")
            else:
                raise ValueError(f"Tool {tool_name} has no execute method")

            # Standardize output
            if isinstance(raw_result, dict):
                return ToolOutput(
                    status="success" if raw_result.get("status") == "success" else "error",
                    data=raw_result.get("results") or raw_result.get("data") or {},
                    message=raw_result.get("error", ""),
                    meta=raw_result.get("metadata", {})
                )
            else:
                # Raw output bypasses contract - wrap it
                logger.warning(f"[ToolExecutor] RAW OUTPUT DETECTED from {tool_name}. Wrapping.")
                return ToolOutput(
                    status="success",
                    data=raw_result,
                    meta={"wrapped": True}
                )

        except Exception as e:
            logger.error(f"[ToolExecutor] CRITICAL FAILURE in {tool_name}: {e}")
            return ToolOutput(
                status="error",
                data={},
                message=str(e)
            )
