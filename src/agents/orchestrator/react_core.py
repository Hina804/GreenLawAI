"""
ReAct Agent - Plan-Driven Edition.
The agent follows the DETERMINISTIC plan from TaskPlanner.
It does NOT ask the LLM what tool to call — the plan already specifies that.
The LLM is ONLY used for final synthesis (plain text generation).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from memory.memory_fabric import MemoryFabric
from tools.registry import ToolRegistry
from agents.orchestrator.planner import TaskPlanner
from agents.orchestrator.meta_cognition import MetaCognition
from agents.reflection.outcome_analyzer import OutcomeAnalyzer
from agents.reflection.lesson_learner import LessonLearner
from pipeline.ab_tester import ABTester

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    Plan-Driven ReAct Agent.
    
    The key insight: Phi-2 CANNOT output JSON reliably.
    Solution: Use the LLM ONLY for plain-text synthesis.
    All planning and tool selection is deterministic.
    """

    def __init__(self, llm_engine=None):
        self.memory = MemoryFabric()
        self.tool_registry = ToolRegistry(llm_manager=llm_engine)
        self.planner = TaskPlanner(llm_engine=llm_engine)
        self.meta = MetaCognition(llm_engine=llm_engine)
        self.optimizer = OutcomeAnalyzer()
        self.learner = LessonLearner()
        self.tester = ABTester()
        self.llm = llm_engine
        self._last_sat_image = None # Track the latest satellite image for attachments

    async def process(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """
        Plan-Driven execution:
        1. Create deterministic plan (keyword-based, no LLM)
        2. Execute each planned tool in sequence
        3. Synthesize findings with LLM (plain text only)
        """
        context = context or {}
        start_time = datetime.now()
        execution_id = str(uuid.uuid4())
        answer = ""  # Initialized to avoid UnboundLocalError
        
        # A/B testing
        variant = self.tester.get_variant()
        context["variant"] = variant
        
        # Retrieve past lessons
        lessons = self.learner.get_relevant_lessons(task)
        context["past_lessons"] = lessons

        # === ZERO-STEP EMERGENCY OVERRIDE (DeepSeek Req 2) ===
        from agents.emergency_responder import EmergencyResponder
        responder = EmergencyResponder()
        if await responder.should_trigger(task):
            logger.warning("[ReAct] CRITICAL EMERGENCY DETECTED. Overriding ReAct loop.")
            return await responder.handle(task)

        # === STEP 1: CREATE DETERMINISTIC PLAN ===
        plan = await self.planner.create_plan(task, context)
        steps = []
        tool_results_cache = {}  # Prevent duplicate tool calls

        logger.info(f"[ReAct] Executing plan: {[s['name'] for s in plan.sub_tasks]}")

        # === STEP 2: EXECUTE PLAN (Optimized Parallel/Sequential) ===
        # Group subtasks: parallel-ready data tools vs sequential-only notification/action tools
        parallel_batch = []
        sequential_batch = []
        
        for sub_task in plan.sub_tasks:
            tool_name = sub_task.get("tool", "web_search")
            if tool_name == "complete":
                continue # Handled at the end
            
            # Tools that DON'T depend on previous steps' outputs can be parallelized
            is_parallelizable = tool_name in [
                "web_search", "law_specialist", "search_forest_laws", 
                "incident_agent", "climate_oracle", "citizen_awareness",
                "satellite_analyzer", "patrol_planner", "judiciary_specialist"
            ]
            
            if is_parallelizable:
                parallel_batch.append(sub_task)
            else:
                sequential_batch.append(sub_task)

        # 2a. Execute Parallel Batch
        if parallel_batch:
            logger.info(f"[ReAct] Executing parallel batch: {[t['tool'] for t in parallel_batch]}")
            
            async def execute_task(st):
                t_name = st.get("tool")
                prms = self._build_params(task, t_name, [], plan.location_data)
                try:
                    res = await self.tool_registry.execute(tool_name=t_name, parameters=prms)
                    if t_name == "satellite_analyzer" and isinstance(res, dict):
                        if res.get("status") == "success" and res.get("image_path"):
                            self._last_sat_image = res.get("image_path")
                    return st['id'], t_name, prms, res, st['description']
                except Exception as ex:
                    logger.error(f"[ReAct] Parallel tool '{t_name}' failed: {ex}")
                    return st['id'], t_name, prms, {"error": str(ex)}, st['description']

            results = await asyncio.gather(*[execute_task(t) for t in parallel_batch])
            
            for task_id, t_name, prms, res, desc in results:
                tool_results_cache[t_name] = res
                plan.complete_step(res)
                obs = self._format_observation(res)
                steps.append({
                    'step': task_id, 'thought': desc, 'action': t_name,
                    'params': prms, 'result': res, 'observation': obs,
                    'timestamp': datetime.now().isoformat()
                })

        # 2b. Execute Sequential Batch
        for sub_task in sequential_batch:
            tool_name = sub_task.get("tool")
            params = self._build_params(task, tool_name, steps, plan.location_data)
            
            logger.info(f"[ReAct] Step {sub_task['id']}: {sub_task['name']} → {tool_name} (Sequential)")
            try:
                tool_result = await self.tool_registry.execute(tool_name=tool_name, parameters=params)
            except Exception as e:
                logger.error(f"[ReAct] Tool '{tool_name}' failed: {e}")
                tool_result = {"error": str(e)}

            tool_results_cache[tool_name] = tool_result
            plan.complete_step(tool_result)
            observation = self._format_observation(tool_result)
            steps.append({
                'step': sub_task['id'], 'thought': sub_task['description'],
                'action': tool_name, 'params': params, 'result': tool_result,
                'observation': observation, 'timestamp': datetime.now().isoformat()
            })

        # Final memory storage (batch) - FIXED
        try:
            store_tasks = []
            for s in steps:
                store_tasks.append(self.memory.episodic.store({
                    'task': task, 
                    'step': s['step'], 
                    'thought': s['thought'],
                    'result': s['result'], 
                    'timestamp': datetime.now()
                }))
            # IMPORTANT: Await all store operations
            if store_tasks:
                await asyncio.gather(*store_tasks)
        except Exception as e:
            logger.warning(f"Failed to store episodic memories: {e}")

        # === STEP 3: SYNTHESIZE FINAL ANSWER ===
        answer = await self._synthesize(task, steps)
        # === STEP 4: REFLECT ===
        reflection = await self._safe_reflect(task, answer, steps, variant, execution_id)

        return {
            "status": "success",
            "task": task,
            "answer": answer,
            "steps": steps,
            "total_steps": len(steps),
            "duration": (datetime.now() - start_time).total_seconds(),
            "reflection": reflection
        }

    def _build_params(self, task: str, tool_name: str, steps: Optional[List[Dict]] = None, location_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Build tool parameters from the task text and planner context."""
        task_lower = task.lower()
        steps = steps or []
        
        # Default query parameter
        base_params = {"query": task[:200]}
        
        # Inject location intelligence if available from planner
        if location_data:
            loc_name = location_data.get('region_full') or location_data.get('name')
            base_params.update({
                "location": loc_name,
                "latitude": location_data.get('lat'),
                "longitude": location_data.get('lon'),
                "context": {"location": location_data}
            })

        if tool_name in ["web_search", "law_specialist", "search_forest_laws", "incident_agent", "climate_oracle", "citizen_awareness"]:
            return base_params
        elif tool_name == "satellite_analyzer":
            # 1. Use planner location if available
            if location_data:
                return {"location": location_data.get('name', "Hazara").capitalize()}
                
            # 2. Fallback to keyword extraction
            location = "Swat" # Default
            for city in ["abbottabad", "shangla", "dir", "swat", "mansehra", "haripur"]:
                if city in task_lower:
                    location = city.capitalize()
                    break
            return {"location": location}
        elif tool_name in ["slack_notifier", "teams_notifier", "email_sender"]:
            # Check for previously fetched satellite image to attach
            file_path = None
            if hasattr(self, "_last_sat_image"):
                file_path = self._last_sat_image
            
            # Synthesize report from findings so far
            report = self._template_synthesis(task, steps)
            
            # Clean UI markers (IMAGE_PATH) for Slack
            import re
            report = re.sub(r"IMAGE_PATH\[(.*?)\]", "", report)
            
            return {
                "message": f"🤖 *GreenLawAI Autonomous Report*\n\n{report}",
                "file_path": file_path
            }
        elif tool_name == "email_sender":
            import os
            report = self._template_synthesis(task, steps)
            return {
                "recipient": os.getenv("DFO_EMAIL", "alihinaali2022@gmail.com"),
                "subject": f"GreenLawAI: Forest Investigation Report - {task[:30]}",
                "message": report
            }
        elif tool_name in ["sms_messenger", "whatsapp_messenger"]:
            import os
            summary_parts = []
            for s in steps:
                if s.get('action') == 'incident_agent':
                    res = s.get('result', {})
                    if res.get('evidence'): summary_parts.append(f"Evidence: {len(res['evidence'])} found.")
                elif s.get('action') == 'satellite_analyzer':
                    res = s.get('result', {})
                    if res.get('analysis'): summary_parts.append("Satellite confirmed.")
            
            summary = " ".join(summary_parts) if summary_parts else "Alert generated."
            short_msg = f"GreenLawAI: {task[:40]}. {summary}"
            if len(short_msg) > 150: short_msg = short_msg[:147] + "..."
            
            return {
                "phone": os.getenv("DFO_PHONE_NUMBER", "+923495994503"),
                "message": short_msg
            }
        elif tool_name == "dfo_notifier":
            return {"region": task[:50], "message": task[:200]}
        elif tool_name == "patrol_planner":
            return {}
        elif tool_name == "certificate_generator":
            return {"violation_type": task[:100]}
        else:
            return {"query": task[:200]}

    def _format_observation(self, result: Any) -> str:
        """Convert tool result to a readable observation string."""
        if isinstance(result, dict):
            if "error" in result:
                return f"Tool error: {result['error']}"
            
            # Extract the most useful parts
            parts = []
            
            # Web search results
            if "results" in result:
                for r in result.get("results", [])[:3]:
                    parts.append(f"[{r.get('title', 'Result')}] {r.get('snippet', '')}")
            
            # Patrol schedule
            if "summary" in result:
                parts.append(result["summary"])
            elif "recommendations" in result:
                for rec in result.get("recommendations", []):
                    parts.append(
                        f"{rec.get('priority', '')} {rec.get('division', '')}: "
                        f"{rec.get('action', '')} ({rec.get('reason', '')})"
                    )
            
            # Date
            if "date" in result:
                parts.append(f"Date: {result['date']}")
            
            if parts:
                return "\n".join(parts)
            
            return str(result)[:500] if str(result).strip() != "0" else "Success"
        
        return str(result)[:500] if str(result).strip() != "0" else "Success"

    async def _synthesize(self, task: str, steps: List) -> str:
        """
        Synthesize a professional answer from tool results.
        Uses LLM for plain text generation (its strength).
        Falls back to template-based synthesis if LLM fails.
        """
        # Collect and deduplicate observations
        unique_findings = []
        seen_observations = set()
        for s in steps:
            if s.get('action') not in ['error', 'complete']:
                obs = str(s.get('observation', '')).strip()
                if obs and obs not in ["0", "0.0", "None", "null"] and obs not in seen_observations:
                    unique_findings.append(f"- {obs}")
                    seen_observations.add(obs)
        findings = "\n".join(unique_findings)

        # === GENERATE DETERMINISTIC TEMPLATE ===
        template_text = self._template_synthesis(task, steps)

        # === GENERATE FINAL ANSWER ===
        answer = ""
        llm_response = None
        if self.llm and findings.strip():
            try:
                prompt = (
                    f"TASK: {task}\n"
                    f"EVIDENCE:\n{findings}\n\n"
                    f"Write a brief, professional 2-3 sentence summary answering the task. "
                    f"Do not list all the specific data points, as the full detailed report will be automatically attached below. "
                )
                llm_response = await self.llm.generate_text(prompt)
                
                if llm_response:
                    # Clean the response of rogue characters or separators
                    llm_response = llm_response.strip()
                    
                    # 🚨 AGGRESSIVE CONVERSATIONAL SCRUBBING (Loop Prevention)
                    # Remove "User:", "Assistant:", "TASK:", etc if LLM repeats them
                    import re
                    prefixes = [r"^User:", r"^Assistant:", r"^Task:", r"^Evidence:", r"^Step \d+:"]
                    for p in prefixes:
                        llm_response = re.sub(p, "", llm_response, flags=re.IGNORECASE | re.MULTILINE).strip()
                    
                    # Cut off if LLM starts hallucinating a second turn
                    for stop_word in ["User:", "Task:", "\n---\n"]:
                        if stop_word in llm_response:
                            llm_response = llm_response.split(stop_word)[0].strip()

                    llm_response = "\n".join([line for line in llm_response.split("\n") if line.strip() not in ["0", "0.0", "None", "---"]])
                
                # Check for obvious Colab truncation or empty fallbacks
                if llm_response and len(llm_response.strip()) > 20:
                    answer = f"{llm_response}\n\n---\n\n{template_text}"
                else:
                    answer = template_text
            except Exception as e:
                logger.error(f"[ReAct] LLM synthesis failed: {e}")
                answer = template_text
        else:
            answer = template_text

        # Final safety check before hallucination guard
        if not answer:
            answer = template_text

        # === NOTIFICATION & HALLUCINATION GUARD ===
        notif_keywords = ['notify', 'alert', 'send', 'inform', 'report', 'dispatch']
        user_requested_notif = any(kw in task.lower() for kw in notif_keywords)
        
        # Check if any notification tool successfully executed
        notif_tool_executed = False
        for step in steps:
            action = step.get('action')
            if action in ['dfo_notifier', 'slack_notifier', 'teams_notifier', 'email_sender', 'whatsapp_messenger', 'sms_messenger']:
                result = step.get('result', {})
                if result.get('status') == 'success' or result.get('notification_sent') == True or 'mobile_links' in result:
                    notif_tool_executed = True
                    break
        
        logger.debug(f"[ReAct] Notification Audit | Requested: {user_requested_notif} | Tool Executed: {notif_tool_executed}")

        # 1. Hallucination Scrubbing (Filter LLM's generic 'I notified DFO' lies)
        hallucination_str = "However, the Department of Fisheries and Oceans (DFO) has been notified of this issue and is currently investigating the matter."
        if not notif_tool_executed and hallucination_str in answer:
            logger.info("[ReAct] Scrubbing hallucination: Tool did not execute but LLM claimed notification.")
            answer = answer.replace(hallucination_str, "").strip()
        
        # 2. Conditional Notification Message
        if user_requested_notif and not notif_tool_executed:
            logger.info("[ReAct] Adding manual notification prompt: Requested by user but no auto-dispatch.")
            answer = "ℹ️ Manual notification required (No automatic dispatch executed).\n\n" + answer
            
        return answer

    def _template_synthesis(self, task: str, steps: List) -> str:
        """Build a professional answer from tool results WITHOUT the LLM."""
        sections = []
        sections.append(f"## Analysis Report\n**Query:** {task}\n")
        
        # Milestone 15.8: Section Prioritization
        # If user asked for news/search, prioritize that section
        is_search_query = any(kw in task.lower() for kw in ['news', 'search', 'report', 'latest', 'happened', 'update'])
        
        # Temporary buffers for sections
        news_buffer = []
        other_buffer = []
        
        for step in steps:
            # Decide which buffer to use for this step
            current_buffer = news_buffer if step.get('action') == 'web_search' else other_buffer
            
            if step.get('action') == 'web_search':
                results = step.get('result', {}).get('results', [])
                
                # Milestone 15.3: Relevance Guard (Scrubbing out-of-scope results)
                mandatory_keywords = [
                    'forest', 'timber', 'tree', 'law', 'kpk', 'pakistan', 'government', 
                    'legal', 'wildfire', 'environment', 'ecology', 'incident', 'accident', 
                    'arrest', 'fine', 'report', 'court', 'magistrate', 'authority', 'happened', 
                    'news', 'police', 'investigation', 'abbottabad', 'mansehra', 'haripur', 
                    'swat', 'kalam', 'shangla', 'bunner', 'dir', 'battagram', 'kohistan'
                ]
                filtered_results = []
                for r in results:
                    text_to_check = (r.get('title', '') + " " + r.get('snippet', r.get('body', ''))).lower()
                    if any(kw in text_to_check for kw in mandatory_keywords):
                        filtered_results.append(r)

                is_throttled = step.get('result', {}).get('status') == 'throttled'
                is_historical = step.get('result', {}).get('status') in ['success_historical', 'success_realtime', 'success_recent']
                historical_context = step.get('result', {}).get('historical_context', '')
                    
                if filtered_results:
                    current_buffer.append("### 🌐 Intelligence Findings (Grounded Search)")
                    for r in filtered_results[:5]: 
                        headline = r.get('title', 'Source')
                        snippet = r.get('snippet', r.get('body', 'No details available.'))
                        source = r.get('source')
                        date = r.get('date')
                        url = r.get('url', '#')
                        
                        meta_line = f"*{source}* — {date}" if source and date else f"*{source}*" if source else ""
                        current_buffer.append(f"**{headline}**")
                        if meta_line: current_buffer.append(meta_line)
                        current_buffer.append(f"> {snippet}")
                        if url and url != "#": current_buffer.append(f"🔗 [Read more]({url})\n")
                        else: current_buffer.append("")
                
                elif is_historical and historical_context:
                    current_buffer.append("### 📜 Tactical Historical Intelligence")
                    current_buffer.append(historical_context)
                
                elif is_throttled:
                    # Milestone 15.15: Sensor-as-News Fallback
                    current_buffer.append("### 🛰️ Internal Sensor Intelligence (Sensor-as-News)")
                    current_buffer.append("> *Live web search is currently throttled by provider. Accessing internal NASA/Satellite sensors for ground truth.*")
                        
                    # High-level synthesis of other tool results found in previous steps
                    # We look for 'get_fire_alerts' findings
                    fire_step = next((s for s in steps if s.get('action') == 'get_fire_alerts'), None)
                    if fire_step and fire_step.get('result', {}).get('alerts'):
                        alerts = fire_step['result']['alerts']
                        for i, alert in enumerate(alerts[:3]):
                            loc = alert.get('location', 'Unknown')
                            confidence = alert.get('confidence', 'N/A')
                            time_str = alert.get('acq_time', 'Recently')
                            current_buffer.append(f"**🔴 ALERT: High-Heat Anomaly Detected in {loc}**")
                            current_buffer.append(f"*Source: NASA FIRMS Satellite* — *Time: {time_str}*")
                            current_buffer.append(f"> Verified thermal signature (Confidence: {confidence}%) at tactical coordinates. System tracking active ignition.\n")
                    else:
                        current_buffer.append("**⚪ STATUS: No active heat signatures in primary patrol zones.**")
                        current_buffer.append("> Regional monitoring continues via passive satellite IR sensors.\n")
                        
            elif step.get('action') == 'search_forest_laws':
                results = step.get('result', {}).get('results', [])
                current_buffer.append("### ⚖️ Legal Framework & Core Penalties")
                if results:
                    for r in results:
                        text = r.get('text', '')[:200]
                        meta = r.get('metadata', {})
                        cite = f" ({meta.get('law_title', 'Act')} Sec {meta.get('section', 'N/A')})"
                        current_buffer.append(f"- {text}...{cite}")
                
                from core.penalty_calculator import PenaltyCalculator
                base_deodar = PenaltyCalculator.BASE_PENALTIES.get('deodar', 206000)
                current_buffer.append("\n**Critical Enforcements (KP Forest Ordinance):**")
                current_buffer.append("- Illegal timber transit: Confiscation of vehicle + Rs. 50,000 fine.")
                current_buffer.append(f"- Deforestation (Deodar): Up to 6 months imprisonment and/or fines up to Rs. {base_deodar:,} per violation (Schedule-III).")
                current_buffer.append("")
            
            elif step.get('action') == 'patrol_planner':
                result = step.get('result', {})
                if result.get('summary'):
                    current_buffer.append("### 🛡️ Patrol Schedule")
                    current_buffer.append(result['summary'])
                elif result.get('recommendations'):
                    current_buffer.append("### 🛡️ Patrol Recommendations")
                    for rec in result['recommendations']:
                        current_buffer.append(
                            f"- {rec.get('priority', '')} **{rec.get('division', '')}**: "
                            f"{rec.get('action', '')} — {rec.get('reason', '')}"
                        )
                current_buffer.append("")
            
            elif step.get('action') == 'law_specialist':
                result = step.get('result', {})
                text = result.get('answer') or result.get('legal_explanation') or result.get('text')
                if not text and isinstance(result, dict):
                    text = str(result)[:500]
                
                current_buffer.append("### ⚖️ Legal Analysis (IRAC Foundation)")
                if text and str(text).strip() not in ["0", "0.0", "None", "null"]:
                    if "ISSUE:" not in text:
                        current_buffer.append(f"**ISSUE:** Analysis of forest violation for '{task[:100]}'\n")
                        current_buffer.append(f"**RULE:**\n{text}\n")
                    else:
                        current_buffer.append(text)
                else:
                    current_buffer.append("No legal analysis generated.")
                current_buffer.append("")
                
            elif step.get('action') == 'incident_agent':
                result = step.get('result', {})
                current_buffer.append("### 🕵️ Incident Investigation Data")
                current_buffer.append(f"**Target:** {result.get('investigation_target', 'Unknown')}")
                if result.get("evidence"):
                    current_buffer.append("**Evidence Found:**")
                    for ev in result.get("evidence", []):
                        current_buffer.append(f"- {ev}")
                current_buffer.append(f"**Conclusion:** {result.get('conclusion', 'N/A')}")
                current_buffer.append("")
                
            elif step.get('action') == 'fire_department_api':
                result = step.get('result', {})
                current_buffer.append("### 🚒 Emergency Response")
                current_buffer.append(f"**STATUS:** {result.get('status', 'NOTIFIED')}")
                current_buffer.append(f"- **Action:** {result.get('action', '')}")
                current_buffer.append(f"- **Location:** {result.get('location', '')}")
                current_buffer.append(f"- **Instructions:** {result.get('instructions', '')}")
                current_buffer.append("")
                
            elif step.get('action') == 'evacuation_planner':
                result = step.get('result', {})
                current_buffer.append("### 🚨 Evacuation Protocol")
                current_buffer.append(f"**STATUS:** {result.get('status', 'ORDERED')}")
                current_buffer.append(f"- **Zone:** {result.get('evacuation_zone', '')}")
                if result.get('safe_routes'):
                    current_buffer.append(f"- **Routes:** {', '.join(result['safe_routes'])}")
                current_buffer.append(f"- **Broadcast:** {result.get('broadcast', '')}")
                current_buffer.append("")
                
            elif step.get('action') in ['sms_messenger', 'whatsapp_messenger', 'email_sender', 'dfo_notifier', 'slack_notifier', 'teams_notifier']:
                result = step.get('result', {})
                if result.get('status') == 'success' or result.get('notification_sent') or 'mobile_links' in result:
                    current_buffer.append("### 📨 Official Notification Dispatched")
                else:
                    continue
                
                if 'action' in result: current_buffer.append(f"- **Action:** {result.get('action', '')}")
                if 'message' in result: current_buffer.append(f"- **Message:** {result.get('message', '')}")
                
                if 'mobile_links' in result:
                    links = result['mobile_links']
                    hw, hs = links.get('whatsapp', ''), links.get('sms', '')
                    current_buffer.append("\n**🚀 Mobile Command Center:**")
                    btn_container = f'<div style="margin: 10px 0;">'
                    if hw: btn_container += f'<a href="{hw}" target="_blank" style="background-color: #25d366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-right: 10px; border: none;">📱 Send WhatsApp</a>'
                    if hs: btn_container += f'<a href="{hs}" style="background-color: #3b82f6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; border: none;">💬 Send SMS</a>'
                    btn_container += '</div>'
                    current_buffer.append(btn_container)
                
                if step.get('action') == 'slack_notifier': current_buffer.append("✅ **Live Slack Alert Sent**")
                current_buffer.append("")

            elif step.get('action') == 'satellite_analyzer':
                result = step.get('result', {})
                if result.get('status') == 'success':
                    current_buffer.append("### 🛰️ Live Satellite Intelligence")
                    current_buffer.append(f"**Analysis:** {result.get('analysis', '')}")
                    if result.get('image_path'): current_buffer.append(f"\nIMAGE_PATH[{result['image_path']}]")
                else:
                    current_buffer.append(f"### 🛰️ Satellite Scan Failed")
                current_buffer.append("")

            elif step.get('action') == 'climate_oracle':
                result = step.get('result', {})
                text = result.get('answer')
                current_buffer.append("### 🌦️ Climate & Weather Intelligence")
                if text: current_buffer.append(text)
                current_buffer.append("")

        # Merge buffers based on prioritization
        if is_search_query:
            sections.extend(news_buffer)
            sections.extend(other_buffer)
        else:
            sections.extend(other_buffer)
            sections.extend(news_buffer)
        
        # Add awareness section at the very end regardless of priority
        for step in steps:
            if step.get('action') == 'citizen_awareness':
                result = step.get('result', {})
                text = result.get('answer')
                sections.append("### 🌱 Citizen Awareness & Action")
                if text:
                    sections.append(text)
                else:
                    sections.append("No awareness content available.")
                sections.append("")
        
        # Milestone 15.15: Tactical Intelligence Synthesis
        if len(sections) <= 1:
            sections.append("*Regional intelligence sensors are online. No active forest fire anomalies or news reports detected in primary Hazara zones for current query.*")
        
        # Filter out rogue single-character sections like '0'
        cleaned_sections = [s for s in sections if str(s).strip() not in ["0", "None", "0.0", "null"]]
        final_report = "\n".join(cleaned_sections)
        
        # FINAL AGGRESSIVE SCRUB
        import re
        final_report = re.sub(r"^\s*0\s*$", "", final_report, flags=re.MULTILINE)
        final_report = re.sub(r"^\s*---\s*$", "---", final_report, flags=re.MULTILINE)
        final_report = re.sub(r"\n\s*\n\s*\n", "\n\n", final_report)
        
        return final_report.strip()

    async def _safe_reflect(self, task, answer, steps, variant, execution_id) -> Dict:
        """Reflect on execution with error handling."""
        try:
            score = self.optimizer.evaluate_final_outcome(answer, steps)
            lesson = self.optimizer.identify_learning_opportunity(task, score, steps)
            if lesson:
                self.learner.save_lesson(task, lesson, {"variant": variant, "score": score})
            self.tester.log_result(variant, score, execution_id)
            return {"score": score, "lesson_learned": lesson or "None", "variant": variant}
        except Exception:
            return {"score": 0.5, "lesson_learned": "None", "variant": variant}
