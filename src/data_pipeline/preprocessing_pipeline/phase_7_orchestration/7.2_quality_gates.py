"""
QUALITY GATES FOR FORESTRY LAW PREPROCESSING PIPELINE
Research-Grade Abstention Framework Implementation

Philosophy: "System Knows When It Doesn't Know"
Implements sequential quality checks with configurable thresholds.
Each gate can: PASS, WARN, or FAIL (triggering abstention).
"""

import json
import logging
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from datetime import datetime
from pathlib import Path

# Import from common
from preprocessing_pipeline.common.config import PipelineConfig, load_config
from preprocessing_pipeline.common.constants import (
    DocumentType, 
    ProcessingStatus, 
    QualityThresholds, 
    ABSTENTION_REASONS
)

from preprocessing_pipeline.common.llm_client import LLMClient


# Import from foundation phase for abstention logging using package exports
try:
    from preprocessing_pipeline.phase_0_foundation import DocProfiler, AbstentionLogger, AbstentionType
except ImportError:
    # Fallback if package path is not available
    try:
        from phase_0_foundation import DocProfiler, AbstentionLogger, AbstentionType
    except ImportError:
        DocProfiler = None
        AbstentionLogger = None


logger = logging.getLogger(__name__)


# Default quality thresholds for gates
QUALITY_THRESHOLDS = {
    'text_quality_threshold': 0.7,
    'legal_structure_threshold': 0.6,
    'entity_consistency_threshold': 0.5,
    'authority_validation_threshold': 0.7,
    'temporal_consistency_threshold': 0.8,
    'graph_integrity_threshold': 0.6,
    'multilingual_coherence_threshold': 0.5
}



class GateResult(Enum):
    """Results of quality gate evaluation"""
    PASS = "PASS"        # Meets quality standards
    WARN = "WARN"        # Below optimal but processable
    FAIL = "FAIL"        # Critical failure - trigger abstention
    MANUAL_REVIEW = "MANUAL_REVIEW"  # Requires human intervention


@dataclass
class GateMetric:
    """Metrics for a single quality gate"""
    gate_name: str
    result: GateResult
    score: float
    threshold: float
    details: Dict[str, Any]
    timestamp: str


@dataclass
class QualityReport:
    """Complete quality assessment report"""
    document_id: str
    document_type: str
    pipeline_stage: str
    overall_status: GateResult
    gates_passed: int
    gates_total: int
    confidence_score: float
    metrics: List[GateMetric]
    recommendations: List[str]
    abstention_reason: Optional[str] = None
    processing_time_ms: Optional[int] = None


class QualityGate:
    """Base class for all quality gates"""
    
    def __init__(self, name: str, threshold: float, weight: float = 1.0):
        self.name = name
        self.threshold = threshold
        self.weight = weight
        self.metrics = []
        
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        """Evaluate the gate - to be implemented by subclasses"""
        raise NotImplementedError
        
    def _create_metric(self, score: float, details: Dict[str, Any]) -> GateMetric:
        """Create a standardized metric object"""
        result = self._determine_result(score)
        return GateMetric(
            gate_name=self.name,
            result=result,
            score=score,
            threshold=self.threshold,
            details=details,
            timestamp=datetime.now().isoformat()
        )
    
    def _determine_result(self, score: float) -> GateResult:
        """Determine result based on score and threshold"""
        if score >= self.threshold:
            return GateResult.PASS
        elif score >= self.threshold * 0.7:  # 70% of threshold
            return GateResult.WARN
        else:
            return GateResult.FAIL


class TextQualityGate(QualityGate):
    """Gate 1: Text Extraction Quality"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check text quality metrics from Phase 1
        extracted_text = data.get('extracted_text', '')
        ocr_confidence = data.get('ocr_confidence', 0.0)
        char_error_rate = data.get('char_error_rate', 1.0)
        
        # Calculate quality score
        # OCR confidence (40%), text length (30%), error rate (30%)
        text_length_score = min(len(extracted_text) / 1000, 1.0)  # Normalize
        
        quality_score = (
            ocr_confidence * 0.4 +
            text_length_score * 0.3 +
            (1 - min(char_error_rate, 1.0)) * 0.3
        )
        
        details = {
            'ocr_confidence': ocr_confidence,
            'char_error_rate': char_error_rate,
            'text_length': len(extracted_text),
            'text_preview': extracted_text[:200] + '...' if len(extracted_text) > 200 else extracted_text
        }
        
        return self._create_metric(quality_score, details)


class LegalStructureGate(QualityGate):
    """Gate 2: Legal Document Structure"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check if document has proper legal structure
        document_type = context.get('document_type', 'UNKNOWN')
        sections = data.get('detected_sections', [])
        citations = data.get('citations', [])
        
        # Document type specific checks
        if document_type in ['STATUTE', 'ACT', 'ORDINANCE']:
            # Must have sections and citations
            section_score = min(len(sections) / 10, 1.0)  # At least 10 sections expected
            citation_score = min(len(citations) / 5, 1.0)  # At least 5 citations
            
            structure_score = (section_score * 0.6 + citation_score * 0.4)
            
        elif document_type in ['CIRCULAR', 'NOTIFICATION']:
            # Must have issuance authority and date
            has_authority = bool(data.get('issuing_authority'))
            has_date = bool(data.get('issuance_date'))
            
            structure_score = (has_authority * 0.5 + has_date * 0.5)
            
        elif document_type == 'WORKING_PLAN':
            # Must have temporal range and geographic info
            has_temporal = bool(data.get('validity_period'))
            has_geographic = bool(data.get('forest_division'))
            
            structure_score = (has_temporal * 0.5 + has_geographic * 0.5)
            
        else:
            # For reports and other documents, just check basic structure
            has_paragraphs = len(data.get('paragraphs', [])) > 3
            has_headings = len(data.get('headings', [])) > 1
            structure_score = (has_paragraphs * 0.5 + has_headings * 0.5)
        
        details = {
            'document_type': document_type,
            'sections_count': len(sections),
            'citations_count': len(citations),
            'has_legal_structure': structure_score > 0.5
        }
        
        return self._create_metric(structure_score, details)


class EntityConsistencyGate(QualityGate):
    """Gate 3: Entity Extraction Consistency"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check consistency of extracted entities
        entities = data.get('entities', {})
        entity_types = ['PERSON', 'ORGANIZATION', 'LOCATION', 'DATE', 'PENALTY', 'SPECIES']
        
        # Count entities by type
        entity_counts = {et: len(entities.get(et, [])) for et in entity_types}
        total_entities = sum(entity_counts.values())
        
        if total_entities == 0:
            consistency_score = 0.0
        else:
            # Check for entity type distribution (shouldn't be just one type)
            max_type_count = max(entity_counts.values())
            diversity_score = 1 - (max_type_count / total_entities)
            
            # Check for entity mention consistency (same entity mentioned multiple times)
            # This is simplified - in reality would need coreference resolution
            consistency_score = diversity_score * 0.7 + min(total_entities / 20, 1.0) * 0.3
        
        details = {
            'total_entities': total_entities,
            'entity_distribution': entity_counts,
            'entity_types_present': [et for et, count in entity_counts.items() if count > 0]
        }
        
        return self._create_metric(consistency_score, details)


class AuthorityValidationGate(QualityGate):
    """Gate 4: Authority Hierarchy Validation"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Validate authority hierarchy from Phase 5
        authority_hierarchy = data.get('authority_hierarchy', {})
        conflicts = data.get('authority_conflicts', [])
        
        # Check hierarchy completeness
        has_federal = bool(authority_hierarchy.get('federal_level'))
        has_provincial = bool(authority_hierarchy.get('provincial_level'))
        has_departmental = bool(authority_hierarchy.get('departmental_level'))
        
        completeness_score = (has_federal + has_provincial + has_departmental) / 3.0
        
        # Check for resolved conflicts
        conflict_resolution_score = 1.0 - min(len(conflicts) / 5, 1.0)
        
        authority_score = (completeness_score * 0.6 + conflict_resolution_score * 0.4)
        
        details = {
            'hierarchy_levels_present': [
                level for level, present in [
                    ('federal', has_federal),
                    ('provincial', has_provincial),
                    ('departmental', has_departmental)
                ] if present
            ],
            'conflicts_detected': len(conflicts),
            'conflicts': conflicts[:3]  # First 3 conflicts only
        }
        
        return self._create_metric(authority_score, details)


class TemporalConsistencyGate(QualityGate):
    """Gate 5: Temporal Consistency Check"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check temporal consistency from Phase 5
        temporal_data = data.get('temporal_data', {})
        
        # Check date validity
        issuance_date = temporal_data.get('issuance_date')
        effective_date = temporal_data.get('effective_date')
        amendment_dates = temporal_data.get('amendment_dates', [])
        
        date_consistency_score = 1.0
        
        # Check if dates are in valid order
        if issuance_date and effective_date:
            try:
                issuance = datetime.fromisoformat(issuance_date.replace('Z', '+00:00'))
                effective = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
                if effective < issuance:
                    date_consistency_score *= 0.5  # Penalize if effective before issuance
            except (ValueError, AttributeError):
                date_consistency_score *= 0.8
        
        # Check amendment chain consistency
        if amendment_dates:
            try:
                dates = [datetime.fromisoformat(d.replace('Z', '+00:00')) for d in amendment_dates]
                sorted_dates = sorted(dates)
                if dates != sorted_dates:
                    date_consistency_score *= 0.7  # Amendments not in chronological order
            except (ValueError, AttributeError):
                date_consistency_score *= 0.9
        
        # Check if document is still valid
        is_current = temporal_data.get('is_current', True)
        temporal_score = date_consistency_score * (1.0 if is_current else 0.3)
        
        details = {
            'issuance_date': issuance_date,
            'effective_date': effective_date,
            'amendment_count': len(amendment_dates),
            'is_current': is_current,
            'date_consistency_issues': date_consistency_score < 1.0
        }
        
        return self._create_metric(temporal_score, details)


class GraphIntegrityGate(QualityGate):
    """Gate 6: Graph Structure Integrity"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check graph structure from Phase 6
        graph_structure = data.get('graph_structure', {})
        
        # Count nodes and relationships (Handle both list and pre-calculated count)
        nodes = graph_structure.get('nodes', [])
        rels = graph_structure.get('relationships', [])
        
        if isinstance(nodes, list):
            node_count = len(nodes)
        else:
            node_count = int(nodes) if nodes is not None else 0
            
        if isinstance(rels, list):
            rel_count = len(rels)
        else:
            rel_count = int(rels) if rels is not None else 0
        
        # Calculate density (relationships per node)
        if node_count > 0:
            density = rel_count / node_count
            # Good graphs have density between 1.0 and 3.0
            if 1.0 <= density <= 3.0:
                density_score = 1.0
            elif density < 1.0:
                density_score = density  # Too sparse
            else:
                density_score = 3.0 / density  # Too dense
        else:
            density_score = 0.0
        
        # Check for isolated nodes (nodes with no relationships)
        isolated_nodes = graph_structure.get('isolated_nodes', 0)
        if node_count > 0:
            isolation_score = 1.0 - (isolated_nodes / node_count)
        else:
            isolation_score = 0.0
        
        # Check schema compliance
        schema_nodes = set(['Law', 'Section', 'Penalty', 'Species', 'Location'])
        if isinstance(nodes, list):
            actual_nodes = set([n.get('label', '') for n in nodes if isinstance(n, dict)])
        else:
            # If we only have counts, we might have schema stats in 'stats'
            stats = graph_structure.get('stats', {})
            actual_nodes = set(stats.get('node_labels', []))
            
        schema_compliance = len(schema_nodes.intersection(actual_nodes)) / len(schema_nodes) if schema_nodes else 1.0
        
        graph_score = (density_score * 0.4 + isolation_score * 0.3 + schema_compliance * 0.3)
        
        details = {
            'node_count': node_count,
            'relationship_count': rel_count,
            'graph_density': density_score if node_count > 0 else 0,
            'isolated_nodes': isolated_nodes,
            'schema_compliance': f"{schema_compliance:.1%}" if schema_nodes else "N/A"
        }
        
        return self._create_metric(graph_score, details)


class MultilingualCoherenceGate(QualityGate):
    """Gate 7: Multilingual Text Coherence"""
    
    def evaluate(self, data: Dict[str, Any], context: Dict[str, Any]) -> GateMetric:
        # Check multilingual coherence from Phase 3
        multilingual_data = data.get('multilingual_data', {})
        
        languages = multilingual_data.get('detected_languages', [])
        segments = multilingual_data.get('segments', [])
        code_switches = multilingual_data.get('code_switches', 0)
        
        # Language detection confidence
        lang_confidence = multilingual_data.get('language_confidence', {})
        avg_confidence = sum(lang_confidence.values()) / len(lang_confidence) if lang_confidence else 0.0
        
        # Segment consistency
        if segments:
            segment_lengths = [len(s.get('text', '')) for s in segments]
            length_variance = np.var(segment_lengths) if len(segment_lengths) > 1 else 0
            # Lower variance is better (more consistent segments)
            consistency_score = 1.0 / (1.0 + length_variance / 1000)
        else:
            consistency_score = 0.0
        
        # Code switching penalty (some code switching is expected in KPK docs)
        code_switch_score = 1.0 - min(code_switches / 20, 0.5)  # Max 50% penalty
        
        multilingual_score = (avg_confidence * 0.4 + consistency_score * 0.4 + code_switch_score * 0.2)
        
        details = {
            'detected_languages': languages,
            'segment_count': len(segments),
            'code_switches': code_switches,
            'avg_language_confidence': avg_confidence
        }
        
        return self._create_metric(multilingual_score, details)


class KPKQualityGateManager:
    """Manages all quality gates and generates final reports"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or QUALITY_THRESHOLDS
        self.gates = self._initialize_gates()
        self.abstention_log = None
        self.llm_client = LLMClient()
        
    def _initialize_gates(self) -> List[QualityGate]:
        """Initialize all quality gates with config thresholds"""
        gates = [
            TextQualityGate(
                name="text_quality",
                threshold=self.config.get('text_quality_threshold', 0.7)
            ),
            LegalStructureGate(
                name="legal_structure",
                threshold=self.config.get('legal_structure_threshold', 0.6)
            ),
            EntityConsistencyGate(
                name="entity_consistency",
                threshold=self.config.get('entity_consistency_threshold', 0.5)
            ),
            AuthorityValidationGate(
                name="authority_validation",
                threshold=self.config.get('authority_validation_threshold', 0.7)
            ),
            TemporalConsistencyGate(
                name="temporal_consistency",
                threshold=self.config.get('temporal_consistency_threshold', 0.8)
            ),
            GraphIntegrityGate(
                name="graph_integrity",
                threshold=self.config.get('graph_integrity_threshold', 0.6)
            ),
            MultilingualCoherenceGate(
                name="multilingual_coherence",
                threshold=self.config.get('multilingual_coherence_threshold', 0.5)
            )
        ]
        return gates
    
    def set_abstention_log(self, abstention_log: AbstentionLogger):
        """Set the abstention log for recording failures"""
        self.abstention_log = abstention_log
    
    def evaluate_all_gates(self, pipeline_data: Dict[str, Any], 
                          context: Dict[str, Any]) -> QualityReport:
        """Evaluate all quality gates and generate comprehensive report"""
        start_time = datetime.now()
        
        metrics = []
        failed_gates = []
        warning_gates = []
        
        # Evaluate each gate
        for gate in self.gates:
            try:
                metric = gate.evaluate(pipeline_data, context)
                metrics.append(metric)
                
                if metric.result == GateResult.FAIL:
                    failed_gates.append(gate.name)
                elif metric.result == GateResult.WARN:
                    warning_gates.append(gate.name)
                    
            except Exception as e:
                logger.error(f"Error evaluating gate {gate.name}: {str(e)}")
                # Create a failed metric for the errored gate
                failed_metric = GateMetric(
                    gate_name=gate.name,
                    result=GateResult.FAIL,
                    score=0.0,
                    threshold=gate.threshold,
                    details={'error': str(e)},
                    timestamp=datetime.now().isoformat()
                )
                metrics.append(failed_metric)
                failed_gates.append(gate.name)
        
        # Calculate overall scores
        gates_passed = len([m for m in metrics if m.result == GateResult.PASS])
        gates_total = len(metrics)
        
        # Weighted confidence score
        total_weight = sum(g.weight for g in self.gates)
        weighted_score = sum(
            m.score * g.weight 
            for m, g in zip(metrics, self.gates) 
            if m.score is not None
        ) / total_weight if total_weight > 0 else 0.0
        
        # Determine overall status
        if failed_gates:
            overall_status = GateResult.FAIL
            abstention_reason = self._determine_abstention_reason(failed_gates, metrics)
        elif warning_gates:
            overall_status = GateResult.WARN
            abstention_reason = None
        else:
            overall_status = GateResult.PASS
            abstention_reason = None
        
        # Generate LLM-powered recommendations
        recommendations = self._generate_recommendations(metrics, context)
        
        # Create final report
        report = QualityReport(
            document_id=context.get('document_id', 'unknown'),
            document_type=context.get('document_type', 'UNKNOWN'),
            pipeline_stage=context.get('pipeline_stage', 'FINAL'),
            overall_status=overall_status,
            gates_passed=gates_passed,
            gates_total=gates_total,
            confidence_score=weighted_score,
            metrics=metrics,
            recommendations=recommendations,
            abstention_reason=abstention_reason,
            processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
        )
        
        # Log abstention if needed
        if overall_status == GateResult.FAIL and self.abstention_log:
            self._log_abstention(report, pipeline_data, context)
        
        return report
    
    def _determine_abstention_reason(self, failed_gates: List[str], 
                                   metrics: List[GateMetric]) -> str:
        """Determine the primary reason for abstention"""
        # Map gate failures to abstention reasons
        gate_to_reason = {
            'text_quality': ABSTENTION_REASONS.POOR_OCR_QUALITY,
            'legal_structure': ABSTENTION_REASONS.INCOMPLETE_STRUCTURE,
            'authority_validation': ABSTENTION_REASONS.AUTHORITY_CONFLICT,
            'temporal_consistency': ABSTENTION_REASONS.TEMPORAL_CONFLICT,
            'graph_integrity': ABSTENTION_REASONS.GRAPH_INTEGRITY_ISSUE,
        }
        
        # Return the first matching reason, or default
        for gate in failed_gates:
            if gate in gate_to_reason:
                return gate_to_reason[gate]
        
        return ABSTENTION_REASONS.QUALITY_CHECK_FAILED
    
    def _generate_recommendations(self, metrics: List[GateMetric], 
                                context: Dict[str, Any]) -> List[str]:
        """Generate LLM-powered recommendations for improvement"""
        recommendations = []
        
        # First, add rule-based recommendations for failed gates
        for metric in metrics:
            if metric.result == GateResult.FAIL:
                if metric.gate_name == 'text_quality':
                    recommendations.append(
                        "Text quality low. Consider rescanning document or using "
                        "enhanced OCR with KPK-specific fonts."
                    )
                elif metric.gate_name == 'legal_structure':
                    recommendations.append(
                        "Legal structure incomplete. Document may be corrupted or "
                        "requires manual parsing of sections."
                    )
                elif metric.gate_name == 'authority_validation':
                    recommendations.append(
                        "Authority hierarchy conflicts detected. Requires manual "
                        "review of federal vs provincial jurisdiction."
                    )
        
        # If we have multiple warnings/failures, use LLM for holistic recommendations
        warning_count = len([m for m in metrics if m.result == GateResult.WARN])
        failure_count = len([m for m in metrics if m.result == GateResult.FAIL])
        
        if failure_count >= 2 or (failure_count + warning_count) >= 3:
            try:
                llm_recommendation = self._get_llm_recommendation(metrics, context)
                if llm_recommendation:
                    recommendations.append(f"LLM Analysis: {llm_recommendation}")
            except Exception as e:
                logger.warning(f"Could not get LLM recommendation: {str(e)}")
        
        # Default recommendation if none generated
        if not recommendations:
            recommendations.append("Document passed all quality checks. Ready for graph ingestion.")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _get_llm_recommendation(self, metrics: List[GateMetric], 
                              context: Dict[str, Any]) -> Optional[str]:
        """Get holistic recommendation from LLM"""
        # Prepare prompt for LLM
        metric_summary = "\n".join([
            f"- {m.gate_name}: Score={m.score:.2f}, Result={m.result.value}"
            for m in metrics
        ])
        
        prompt = f"""
        Analyze these quality gate results for a KPK forestry law document:
        
        Document Type: {context.get('document_type', 'UNKNOWN')}
        Document ID: {context.get('document_id', 'unknown')}
        
        Quality Gate Results:
        {metric_summary}
        
        Based on these results, provide ONE concise recommendation for improving 
        document processing. Focus on the most critical issue. Respond with only 
        the recommendation, no explanations.
        """
        
        response = self.llm_client.generate(prompt)
        return response.strip() if response else None
    
    def _log_abstention(self, report: QualityReport, 
                       pipeline_data: Dict[str, Any], 
                       context: Dict[str, Any]):
        """Log abstention decision with all relevant data"""
        if not self.abstention_log:
            return
        
        # Create comprehensive abstention record
        abstention_data = {
            'document_id': report.document_id,
            'document_type': report.document_type,
            'abstention_reason': report.abstention_reason,
            'failed_gates': [
                m.gate_name for m in report.metrics 
                if m.result == GateResult.FAIL
            ],
            'confidence_score': report.confidence_score,
            'quality_report': asdict(report),
            'pipeline_context': context,
            'extracted_data_summary': {
                'text_length': len(pipeline_data.get('extracted_text', '')),
                'entity_count': sum(len(v) for v in pipeline_data.get('entities', {}).values()),
                'graph_nodes': len(pipeline_data.get('graph_structure', {}).get('nodes', []))
            }
        }
        
        self.abstention_log.log_abstention(
            document_id=report.document_id,
            reason=report.abstention_reason,
            stage="QUALITY_GATES",
            details=abstention_data
        )
    
    def get_gate_statistics(self) -> Dict[str, Any]:
        """Get statistics about gate performance"""
        return {
            'total_gates': len(self.gates),
            'gate_names': [g.name for g in self.gates],
            'thresholds': {g.name: g.threshold for g in self.gates}
        }
    
    def export_report(self, report: QualityReport, 
                     output_dir: Path) -> Path:
        """Export quality report to JSON file"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"quality_report_{report.document_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = output_dir / filename
        
        # Convert report to serializable format
        report_dict = asdict(report)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, default=str)
        
        logger.info(f"Quality report exported to: {output_path}")
        return output_path


class AdaptiveThresholdOptimizer:
    """Adaptively adjusts quality thresholds based on historical performance"""
    
    def __init__(self, history_window: int = 100):
        self.history_window = history_window
        self.performance_history = []
        
    def update_thresholds(self, gate_results: List[GateMetric], 
                         manual_review_outcome: Optional[str] = None):
        """Update thresholds based on performance and manual review"""
        # Simple implementation - can be enhanced with ML
        for result in gate_results:
            # If gate failed but manual review said it was okay, lower threshold slightly
            if (result.result == GateResult.FAIL and 
                manual_review_outcome == 'APPROVED'):
                # This gate might be too strict
                self._adjust_threshold(result.gate_name, -0.05)
            
            # If gate passed but manual review found issues, increase threshold
            elif (result.result == GateResult.PASS and 
                  manual_review_outcome == 'REJECTED'):
                # This gate might be too lenient
                self._adjust_threshold(result.gate_name, 0.05)
    
    def _adjust_threshold(self, gate_name: str, adjustment: float):
        """Adjust threshold for a specific gate"""
        # In production, this would update the config
        logger.info(f"Adjusting threshold for {gate_name} by {adjustment:.3f}")


# Utility Functions
def create_quality_gate_manager(config: Optional[PipelineConfig] = None) -> KPKQualityGateManager:
    """Factory function to create quality gate manager"""
    if not config:
        config = load_config()
    
    # Use thresholds from config or defaults
    thresholds = {
        'text_quality': QualityThresholds.MIN_DOC_QUALITY,
        'legal_structure': QualityThresholds.MIN_STRUCTURE_QUALITY,
        'authority_validation': QualityThresholds.MIN_AUTHORITY_CONFIDENCE,
        'temporal_consistency': 0.5, # Default
        'graph_integrity': 0.6  # Default
    }
    
    return KPKQualityGateManager(thresholds)


def should_proceed_to_graph(report: QualityReport) -> Tuple[bool, str]:
    """Determine if document should proceed to graph construction"""
    if report.overall_status == GateResult.FAIL:
        return False, f"Abstaining due to: {report.abstention_reason}"
    
    elif report.overall_status == GateResult.WARN:
        # Can proceed with warnings
        warning_count = len([m for m in report.metrics if m.result == GateResult.WARN])
        return True, f"Proceeding with {warning_count} warnings"
    
    else:
        return True, "All quality gates passed"


def get_critical_failures(report: QualityReport) -> List[str]:
    """Get list of critical failures that require immediate attention"""
    critical_gates = ['text_quality', 'authority_validation', 'temporal_consistency']
    
    critical_failures = []
    for metric in report.metrics:
        if (metric.gate_name in critical_gates and 
            metric.result == GateResult.FAIL):
            critical_failures.append(
                f"{metric.gate_name}: score={metric.score:.2f} "
                f"(threshold={metric.threshold:.2f})"
            )
    
    return critical_failures


# Main execution for testing
if __name__ == "__main__":
    # Example usage
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create sample data for testing
    sample_data = {
        'extracted_text': 'This is a sample forestry law document from KPK...',
        'ocr_confidence': 0.85,
        'char_error_rate': 0.05,
        'detected_sections': ['Section 1', 'Section 2', 'Section 3'],
        'entities': {
            'PERSON': ['Forest Officer'],
            'LOCATION': ['KPK', 'Hazara Division'],
            'SPECIES': ['Chir Pine', 'Deodar']
        },
        'authority_hierarchy': {
            'federal_level': 'Ministry of Climate Change',
            'provincial_level': 'KPK Forest Department'
        },
        'temporal_data': {
            'issuance_date': '2023-01-15',
            'effective_date': '2023-02-01',
            'is_current': True
        }
    }
    
    sample_context = {
        'document_id': 'TEST_001',
        'document_type': 'STATUTE',
        'pipeline_stage': 'TEST'
    }
    
    # Create and run quality gates
    manager = create_quality_gate_manager()
    report = manager.evaluate_all_gates(sample_data, sample_context)
    
    # Print results
    print("\n" + "="*60)
    print("QUALITY GATE REPORT")
    print("="*60)
    print(f"Document: {report.document_id} ({report.document_type})")
    print(f"Overall Status: {report.overall_status.value}")
    print(f"Confidence Score: {report.confidence_score:.2%}")
    print(f"Gates Passed: {report.gates_passed}/{report.gates_total}")
    
    if report.abstention_reason:
        print(f"Abstention Reason: {report.abstention_reason}")
    
    print("\nGate Details:")
    for metric in report.metrics:
        print(f"  {metric.gate_name:25} {metric.result.value:10} "
              f"Score: {metric.score:.2f} (Threshold: {metric.threshold:.2f})")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"  • {rec}")
    
    # Check if should proceed
    should_proceed, reason = should_proceed_to_graph(report)
    print(f"\nDecision: {reason}")
    print("="*60)
