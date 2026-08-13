"""
7.0_PIPELINE_DAG.PY - Phase 7: Resilient DAG-Based Orchestration
Implements a Directed Acyclic Graph (DAG) for GreenLawAI pipeline execution.
Supports checkpointing, retries, and failure isolation.
"""

import os
import json
import logging
import asyncio
import time
import dataclasses
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

# Setup logging
logger = logging.getLogger(__name__)

PIPELINE_VERSION = "2.4"  # Bumped: invalidate checkpoints with empty Phase 1 OCR
SCHEMA_VERSION = "kpk_1.0"

@dataclass
class Task:
    """A single task in the pipeline DAG"""
    name: str
    phase: int
    func: Callable
    dependencies: Set[str] = field(default_factory=set)
    retry_count: int = 3
    timeout: int = 300
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0

class PipelineDAG:
    """Managed execution of pipeline tasks with dependency resolution"""
    
    def __init__(self, document_id: str, checkpoint_dir: Path):
        self.document_id = document_id
        self.checkpoint_dir = checkpoint_dir
        self.tasks: Dict[str, Task] = {}
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
    def add_task(self, name: str, phase: int, func: Callable, deps: List[str] = None):
        """Add task to DAG"""
        self.tasks[name] = Task(name=name, phase=phase, func=func, dependencies=set(deps or []))
        
    def get_execution_order(self) -> List[str]:
        """Resolve dependency order (Topological Sort)"""
        order = []
        visited = set()
        temp_stack = set()
        
        def visit(node_name):
            if node_name in temp_stack:
                raise ValueError(f"Cycle detected in DAG: {node_name}")
            if node_name not in visited:
                temp_stack.add(node_name)
                for dep in self.tasks[node_name].dependencies:
                    if dep not in self.tasks:
                        logger.warning(f"Dependency {dep} not found for task {node_name}")
                        continue
                    visit(dep)
                temp_stack.remove(node_name)
                visited.add(node_name)
                order.append(node_name)
                
        for name in self.tasks:
            if name not in visited:
                visit(name)
        return order

    @staticmethod
    def _checkpoint_result_is_valid(task_name: str, result: Any) -> bool:
        """Reject checkpoints that cached empty Phase 1 extraction."""
        if task_name != "ocr":
            return True
        data = {}
        if isinstance(result, dict):
            if "data" in result and isinstance(result["data"], dict):
                data = result["data"]
            else:
                data = result
        elif hasattr(result, "data") and isinstance(result.data, dict):
            data = result.data
        raw = data.get("raw_text", "") if isinstance(data, dict) else ""
        return len(str(raw).strip()) >= 100

    async def run(self, context: Any) -> Dict[str, Any]:
        """Run the DAG in dependency order with checkpointing"""
        order = self.get_execution_order()
        logger.info(f"Executing DAG for {self.document_id} in order: {order}")
        
        for task_name in order:
            task = self.tasks[task_name]
            
            # Check for checkpoint
            checkpoint_file = self.checkpoint_dir / f"{self.document_id}_{task.phase}_{task_name}.json"
            if checkpoint_file.exists():
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        
                        # Version Compatibility Check
                        check_p_ver = checkpoint_data.get('pipeline_version')
                        check_s_ver = checkpoint_data.get('schema_version')
                        
                        if check_p_ver == PIPELINE_VERSION and check_s_ver == SCHEMA_VERSION:
                            task.result = checkpoint_data.get('data')
                            if not self._checkpoint_result_is_valid(task_name, task.result):
                                logger.warning(
                                    f"Stale/invalid checkpoint for {task_name}; re-running task."
                                )
                            else:
                                logger.info(f"Loading compatible checkpoint for task {task_name} (v{check_p_ver})")

                                if context and hasattr(context, 'results'):
                                    from preprocessing_pipeline.phase_7_orchestration.__init__ import PhaseResult, ProcessingStatus

                                    if isinstance(task.result, dict) and 'status' in task.result:
                                        context.results[task.phase] = PhaseResult(
                                            status=ProcessingStatus(task.result.get('status', 'completed')),
                                            data=task.result.get('data', {}),
                                            metrics=task.result.get('metrics', {}),
                                            warnings=task.result.get('warnings', []),
                                            errors=task.result.get('errors', []),
                                            duration_seconds=task.result.get('duration_seconds', checkpoint_data.get('duration', 0)),
                                            timestamp=datetime.fromisoformat(task.result['timestamp']) if 'timestamp' in task.result else datetime.now()
                                        )
                                    elif isinstance(task.result, dict):
                                        context.results[task.phase] = PhaseResult(
                                            status=ProcessingStatus.COMPLETED,
                                            data=task.result,
                                            metrics={},
                                            warnings=[],
                                            errors=[],
                                            duration_seconds=checkpoint_data.get('duration', 0),
                                            timestamp=datetime.fromisoformat(checkpoint_data.get('timestamp')) if 'timestamp' in checkpoint_data else datetime.now()
                                        )
                                    else:
                                        context.results[task.phase] = task.result

                                task.status = "COMPLETED"
                                continue
                        else:
                            logger.warning(f"Incompatible checkpoint version for {task_name}: "
                                           f"Found {check_p_ver}/{check_s_ver}, "
                                           f"Expected {PIPELINE_VERSION}/{SCHEMA_VERSION}. Re-running.")
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint for {task_name}: {e}. Re-running.")

            # Run task
            task.status = "RUNNING"
            task.start_time = time.time()
            
            retries = 0
            while retries < task.retry_count:
                try:
                    logger.info(f"Running task {task_name} (Attempt {retries+1}/{task.retry_count})")
                    # Call the async function
                    if asyncio.iscoroutinefunction(task.func):
                        result = await task.func(context)
                    else:
                        result = task.func(context)
                        
                    task.result = result
                    task.status = "COMPLETED"
                    task.end_time = time.time()
                    
                    # Save checkpoint
                    self._save_checkpoint(task, checkpoint_file)
                    break
                    
                except Exception as e:
                    retries += 1
                    task.error = str(e)
                    logger.error(f"Task {task_name} failed: {e}")
                    if retries >= task.retry_count:
                        task.status = "FAILED"
                        raise e
                    await asyncio.sleep(2 ** retries)  # Exponential backoff

        return {name: t.status for name, t in self.tasks.items()}

    def _save_checkpoint(self, task: Task, path: Path):
        """Save task result to disk"""
        temp_path = str(path) + ".tmp"
        try:
            # Helper to make data JSON serializable
            def make_serializable(obj):
                if obj is None:
                    return None
                
                # Use to_dict if available
                if hasattr(obj, "to_dict") and callable(obj.to_dict):
                    return make_serializable(obj.to_dict())
                
                if dataclasses.is_dataclass(obj):
                    return make_serializable(dataclasses.asdict(obj))
                if isinstance(obj, dict):
                    return {str(k): make_serializable(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple, set)):
                    return [make_serializable(i) for i in obj]
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, Path):
                    return str(obj)
                
                # Fallback for other objects
                try:
                    json.dumps(obj)
                    return obj
                except (TypeError, OverflowError):
                    return str(obj)

            data = {
                "document_id": self.document_id,
                "task_name": task.name,
                "phase": task.phase,
                "pipeline_version": PIPELINE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "timestamp": datetime.now().isoformat(),
                "duration": task.end_time - task.start_time,
                "data": make_serializable(task.result)
            }
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            os.replace(temp_path, str(path))
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.warning(f"Failed to save checkpoint for {task.name}: {e}")

# Integration with Batch Processor Logic
class ResilientOrchestrator:
    """Uses DAG to process documents with full resilience"""
    
    def __init__(self, orchestrator_instance: Any):
        self.orch = orchestrator_instance
        self.checkpoint_root = Path("e:/GL_AI/data_preprocessed/checkpoints")
        
    async def process_with_dag(self, file_path: str, context: Optional[Any] = None):
        file_path_obj = Path(file_path)
        doc_id = file_path_obj.stem
        dag = PipelineDAG(doc_id, self.checkpoint_root / doc_id)
        
        # Define Pipeline DAG matching the 7-phase architecture
        # Phase 0: Foundation
        if hasattr(self.orch, '_execute_phase_0'):
            dag.add_task("profiling", 0, self.orch._execute_phase_0)
            p1_deps = ["profiling"]
        else:
            p1_deps = []

        # Phase 1: Extraction
        dag.add_task("ocr", 1, self.orch._execute_phase_1, p1_deps)
        
        # Phase 2: Restoration (Dependent on Phase 1)
        if hasattr(self.orch, '_execute_phase_2'):
            dag.add_task("sanitization", 2, self.orch._execute_phase_2, ["ocr"])
            
        # Phase 3: Linguistic Alignment
        if hasattr(self.orch, '_execute_phase_3'):
            dag.add_task("section_detection", 3, self.orch._execute_phase_3, ["sanitization"])
            
        # Phase 4: Legal Extraction
        if hasattr(self.orch, '_execute_phase_4'):
            dag.add_task("rule_extraction", 4, self.orch._execute_phase_4, ["section_detection"])
            
        # Phase 5: Authority Reasoning
        if hasattr(self.orch, '_execute_phase_5'):
            dag.add_task("authority_reasoning", 5, self.orch._execute_phase_5, ["rule_extraction"])
            
        # Phase 6: Graph Construction
        dag.add_task("graph_mapping", 6, self.orch._execute_phase_6, ["authority_reasoning" if hasattr(self.orch, '_execute_phase_5') else "rule_extraction"])
        
        # Run the DAG
        # Use provided context or create a mock one if needed
        return await dag.run(context)
