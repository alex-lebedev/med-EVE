"""
Agent Manager - Unified interface for all agentic MedGemma calls
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from .model_manager import model_manager
from .events import EventType, Step

class AgentManager:
    def __init__(self):
        self.prompt_cache = {}
        self.decision_thresholds = {
            'context_complexity': 3,  # markers
            'ambiguity_threshold': 0.15,  # confidence difference
            'min_confidence_for_refinement': 0.7,
            'rare_combination_threshold': 0.1  # probability of seeing this combination
        }
    
    def _env_enabled(self, env_key: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled via environment variable."""
        raw = os.getenv(env_key)
        if raw is None:
            return default
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    
    def _load_prompt_template(self, agent_type: str) -> str:
        """Load prompt template from file"""
        if agent_type in self.prompt_cache:
            return self.prompt_cache[agent_type]
        
        prompt_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'prompts',
            f'{agent_type}.txt'
        )
        
        try:
            with open(prompt_file, 'r') as f:
                template = f.read()
            self.prompt_cache[agent_type] = template
            return template
        except FileNotFoundError:
            raise Exception(f"Prompt template not found: {prompt_file}")
    
    def _build_prompt(self, agent_type: str, context: Dict[str, Any], data: Dict[str, Any]) -> tuple[str, str]:
        """Build system and user prompts from template and data"""
        template = self._load_prompt_template(agent_type)
        
        # Split template into system and user parts (if marked)
        if "===SYSTEM===" in template and "===USER===" in template:
            parts = template.split("===USER===")
            system_prompt = parts[0].replace("===SYSTEM===", "").strip()
            user_template = parts[1].strip()
        else:
            # Default: entire template is system, data is user
            system_prompt = template
            user_template = json.dumps(data, indent=2)
        
        # Format user prompt with merged kwargs (data overrides context) so no duplicate keyword
        format_kwargs = {**context, **data}
        try:
            user_prompt = user_template.format(**format_kwargs)
        except (KeyError, TypeError):
            # If formatting fails (missing key or duplicate keyword), fall back to JSON
            user_prompt = json.dumps(format_kwargs, indent=2)
        
        return system_prompt, user_prompt
    
    def should_use_agent(self, agent_type: str, context: Dict[str, Any]) -> bool:
        """
        Decision logic for when to use model vs. rule-based fallback
        """
        if model_manager.lite_mode or not model_manager.model_loaded:
            return False
        
        if agent_type == "context_selection":
            if not self._env_enabled("USE_CONTEXT_SELECTION_MODEL", default=False):
                return False
            abnormal_markers = context.get('abnormal_markers', [])
            patient_context = context.get('patient_context', {})
            
            # Use model if complex case
            if len(abnormal_markers) > self.decision_thresholds['context_complexity']:
                return True
            
            # Use model if unusual combinations
            if self._has_unusual_combinations(abnormal_markers):
                return True
            
            # Use model if comorbidities present
            if self._has_comorbidities(patient_context):
                return True
            
            return False
        
        elif agent_type == "evidence_weighting":
            if not self._env_enabled("USE_EVIDENCE_WEIGHTING_MODEL", default=False):
                return False
            marker = context.get('marker')
            status = context.get('status')
            evidence_bundle = context.get('evidence_bundle', {})
            
            # Use model for rare combinations
            if self._is_rare_combination(marker, status):
                return True
            
            # Use model if conflicting evidence
            if self._has_conflicts(evidence_bundle):
                return True
            
            return False
        
        elif agent_type == "hypothesis_generation":
            # Only use model for full JSON hypothesis generation if explicitly enabled (hybrid uses lite + ranking/reasoning by default)
            if not self._env_enabled("USE_HYPOTHESIS_GENERATION_MODEL", default=False):
                return False
            return True
        
        elif agent_type == "test_recommendation":
            if not self._env_enabled("USE_TEST_RECOMMENDATION_MODEL", default=False):
                return False
            hypotheses = context.get('hypotheses', [])
            
            # Use model if ambiguity exists
            if self._has_ambiguity(hypotheses):
                return True
            
            # Use model if no tests recommended
            if not any(h.get('next_tests') for h in hypotheses):
                return True
            
            return False
        
        elif agent_type == "action_generation":
            if not self._env_enabled("USE_ACTION_GENERATION_MODEL", default=False):
                return False
            return True
        
        elif agent_type == "guardrail_explanation":
            if not self._env_enabled("USE_GUARDRAIL_EXPLANATION_MODEL", default=False):
                return False
            # Use model when guardrail fails
            return context.get('guardrail_failed', False)
        
        elif agent_type == "novel_insight":
            if not self._env_enabled("USE_NOVEL_INSIGHT_MODEL", default=False):
                return False
            if context.get("force_novelty"):
                return True
            # Trigger on low confidence, ambiguity, or contradictions
            top_conf = float(context.get("top_confidence", 0))
            margin = float(context.get("confidence_margin", 1))
            contradictions = int(context.get("contradiction_count", 0))
            supports = int(context.get("support_count", 0))
            if top_conf < 0.55:
                return True
            if margin < self.decision_thresholds['ambiguity_threshold']:
                return True
            if contradictions > 0 and contradictions >= supports:
                return True
            return False
        
        return False
    
    def _has_unusual_combinations(self, abnormal_markers: List[str]) -> bool:
        """Check if marker combination is unusual"""
        # Simple heuristic: combinations not in common patterns
        common_patterns = [
            {'Ferritin', 'Iron', 'TSAT'},  # Iron studies
            {'TSH', 'FT4', 'FT3'},  # Thyroid panel
            {'hsCRP', 'Ferritin'}  # Inflammation + iron
        ]
        
        marker_set = set(abnormal_markers)
        for pattern in common_patterns:
            if marker_set.issubset(pattern) or pattern.issubset(marker_set):
                return False
        
        return True
    
    def _has_comorbidities(self, patient_context: Dict[str, Any]) -> bool:
        """Check if patient has comorbidities"""
        # Check for common comorbidity indicators
        comorbidities = patient_context.get('comorbidities', [])
        if comorbidities:
            return True
        
        # Check age for age-related conditions
        age = patient_context.get('age')
        if age and age > 65:
            return True
        
        return False
    
    def _is_rare_combination(self, marker: str, status: str) -> bool:
        """Check if marker/status combination is rare"""
        # Simple heuristic: rare if not in common patterns
        common_combinations = [
            ('hsCRP', 'HIGH'),
            ('Ferritin', 'HIGH'),
            ('Ferritin', 'LOW'),
            ('Iron', 'LOW'),
            ('TSAT', 'LOW'),
            ('Hb', 'LOW'),
            ('TSH', 'HIGH'),
            ('FT4', 'LOW')
        ]
        
        return (marker, status) not in common_combinations
    
    def _has_conflicts(self, evidence_bundle: Dict[str, Any]) -> bool:
        """Check if evidence has conflicts"""
        supports = evidence_bundle.get('supports', [])
        contradictions = evidence_bundle.get('contradictions', [])
        
        # Conflict if both supports and contradictions for same pattern
        if supports and contradictions:
            support_patterns = {item.get('pattern_id') for item in supports}
            contradict_patterns = {item.get('pattern_id') for item in contradictions}
            return bool(support_patterns & contradict_patterns)
        
        return False
    
    def _has_ambiguity(self, hypotheses: List[Dict[str, Any]]) -> bool:
        """Check if hypotheses have ambiguity (top 2 within threshold)"""
        if len(hypotheses) < 2:
            return False
        
        sorted_hypo = sorted(hypotheses, key=lambda h: h.get('confidence', 0), reverse=True)
        if len(sorted_hypo) < 2:
            return False
        
        diff = sorted_hypo[0].get('confidence', 0) - sorted_hypo[1].get('confidence', 0)
        return diff < self.decision_thresholds['ambiguity_threshold']
    
    def call_agent(
        self,
        agent_type: str,
        context: Dict[str, Any],
        data: Dict[str, Any],
        events_list: Optional[List] = None,
        step: Optional[Step] = None
    ) -> Dict[str, Any]:
        """
        Unified interface for calling agents
        
        Args:
            agent_type: Type of agent (context_selection, hypothesis_generation, etc.)
            context: Context data for decision making
            data: Data to pass to the agent
            events_list: Optional list to emit events to
            step: Optional pipeline step for events
        
        Returns:
            Agent response (parsed JSON if available, else raw text)
        """
        import time
        start_time = time.time()
        
        # Check if we should use model
        should_use = self.should_use_agent(agent_type, context)
        
        # Emit decision event
        if events_list is not None and step is not None:
            from .events import emit_event
            emit_event(
                events_list,
                step,
                EventType.AGENT_DECISION,
                {
                    'agent_type': agent_type,
                    'decision': 'use_model' if should_use else 'use_rules',
                    'rationale': self._get_decision_rationale(agent_type, context, should_use)
                }
            )
        
        if not should_use:
            # Fallback to rule-based (will be handled by calling code)
            return {'use_model': False, 'fallback': True}
        
        # Build prompts
        try:
            system_prompt, user_prompt = self._build_prompt(agent_type, context, data)
            if agent_type == 'hypothesis_generation':
                user_prompt = user_prompt + "\n{"
        except Exception as e:
            # If prompt loading fails, fallback
            if events_list is not None and step is not None:
                from .events import emit_event
                emit_event(
                    events_list,
                    step,
                    EventType.MODEL_CALLED,
                    {
                        'agent_type': agent_type,
                        'prompt_type': agent_type,
                        'status': 'error',
                        'error': str(e),
                        'response_time_ms': 0
                    }
                )
            return {'use_model': False, 'fallback': True, 'error': str(e)}
        
        # Call model
        try:
            if agent_type == 'hypothesis_generation':
                logging.info("Starting hypothesis_generation model call")
            elif agent_type == 'action_generation':
                logging.info("Starting action_generation model call")
            max_tokens_raw = os.getenv("MEDGEMMA_MAX_TOKENS", "384").strip()
            try:
                max_tokens = max(128, min(1024, int(max_tokens_raw)))
            except ValueError:
                max_tokens = 384
            response = model_manager.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=0.3,
                top_p=0.9
            )
            if agent_type == 'hypothesis_generation':
                logging.info("Completed hypothesis_generation")
            elif agent_type == 'action_generation':
                logging.info("Completed action_generation")
            response_time = time.time() - start_time

            # Emit model called event
            if events_list is not None and step is not None:
                from .events import emit_event
                emit_event(
                    events_list,
                    step,
                    EventType.MODEL_CALLED,
                    {
                        'agent_type': agent_type,
                        'prompt_type': agent_type,
                        'status': 'success',
                        'response_time_ms': response_time * 1000,
                        'cached': response.get('cached', False)
                    }
                )
            
            # Return parsed JSON if available, else raw text; validate critical keys by agent_type
            parsed = response.get('json')
            if parsed is None and agent_type == 'hypothesis_generation' and response.get('text'):
                parsed = model_manager._extract_json_from_text("{" + response["text"])
            if parsed is not None and isinstance(parsed, dict):
                parsed = self._validate_agent_result(agent_type, parsed)
            if parsed is not None:
                if agent_type == "hypothesis_generation" and parsed.get("hypotheses") == [] and response.get("text"):
                    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
                    try:
                        os.makedirs(out_dir, exist_ok=True)
                        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        path = os.path.join(out_dir, "raw_hypothesis_failed_%s.txt" % ts)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(response["text"])
                        logging.warning("hypothesis_generation raw output saved to %s", path)
                    except OSError:
                        pass
                raw_text = response['text']
                if agent_type == 'hypothesis_generation' and parsed is not None and not raw_text.strip().startswith('{'):
                    raw_text = "{" + raw_text
                return {
                    'use_model': True,
                    'result': parsed,
                    'raw_output': raw_text,
                    'response_time_ms': response_time * 1000
                }
            else:
                return {
                    'use_model': True,
                    'result': None,
                    'raw_output': response['text'],
                    'response_time_ms': response_time * 1000,
                    'warning': 'Could not extract or validate JSON from model output'
                }
        
        except Exception as e:
            if agent_type == 'hypothesis_generation':
                logging.info("hypothesis_generation failed: %s", e)
            elif agent_type == 'action_generation':
                logging.info("action_generation failed: %s", e)
            response_time = time.time() - start_time

            # Emit error event
            if events_list is not None and step is not None:
                from .events import emit_event
                emit_event(
                    events_list,
                    step,
                    EventType.MODEL_CALLED,
                    {
                        'agent_type': agent_type,
                        'status': 'error',
                        'error': str(e),
                        'response_time_ms': response_time * 1000
                    }
                )
            
            # Fallback to rule-based
            return {
                'use_model': False,
                'fallback': True,
                'error': str(e)
            }
    
    def _validate_agent_result(self, agent_type: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate parsed JSON has critical keys and types; return None or safe fallback if invalid."""
        if not isinstance(result, dict):
            return None
        if agent_type == "hypothesis_generation":
            if "hypotheses" not in result or not isinstance(result.get("hypotheses"), list):
                logging.warning("hypothesis_generation: missing or invalid 'hypotheses' list in model output")
                return {"hypotheses": [], "patient_actions": result.get("patient_actions") or [], "red_flags": result.get("red_flags") or []}
            return result
        if agent_type == "action_generation":
            if "patient_actions" not in result or not isinstance(result.get("patient_actions"), list):
                logging.warning("action_generation: missing or invalid 'patient_actions' list in model output")
                return {"patient_actions": []}
            return result
        if agent_type == "test_recommendation":
            if "recommended_tests" not in result or not isinstance(result.get("recommended_tests"), list):
                logging.warning("test_recommendation: missing or invalid 'recommended_tests' list in model output")
                return {"recommended_tests": []}
            return result
        if agent_type == "novel_insight":
            if "novel_insights" not in result:
                result["novel_insights"] = result.get("novel_insights") or []
            if "novel_actions" not in result:
                result["novel_actions"] = result.get("novel_actions") or []
            if not isinstance(result["novel_insights"], list):
                result["novel_insights"] = []
            if not isinstance(result["novel_actions"], list):
                result["novel_actions"] = []
            return result
        return result

    def _get_decision_rationale(self, agent_type: str, context: Dict[str, Any], decision: bool) -> str:
        """Generate rationale for agent decision"""
        if not decision:
            return f"Using rule-based fallback for {agent_type}"
        
        if agent_type == "context_selection":
            markers = context.get('abnormal_markers', [])
            return f"Complex case with {len(markers)} abnormal markers - using model"
        elif agent_type == "evidence_weighting":
            return "Rare or conflicting evidence - using model for dynamic weighting"
        elif agent_type == "hypothesis_generation":
            return "Always using model for hypothesis generation"
        elif agent_type == "test_recommendation":
            return "Ambiguity detected or no tests recommended - using model"
        elif agent_type == "action_generation":
            return "Always using model for context-aware action generation"
        elif agent_type == "guardrail_explanation":
            return "Guardrail failed - using model for explanation"
        
        return f"Using model for {agent_type}"

agent_manager = AgentManager()
