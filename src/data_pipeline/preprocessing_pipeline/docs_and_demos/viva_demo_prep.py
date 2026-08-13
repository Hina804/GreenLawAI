"""
viva_demo_prep.py - Viva Demonstration Preparation
===========================================================
Automates demonstration report generation focusing on:
1. LLM cleaning vs Rule-based extraction accuracy
2. Quality gate performance
3. Abstention transparency
4. KPK-specific feature demonstration

Generates:
1. Comparative analysis reports
2. Visualizations (requires matplotlib)
3. Sample outputs for demonstration
4. Viva presentation materials
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import statistics
from collections import defaultdict, Counter
import csv

# Try to import visualization libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("Warning: matplotlib not available. Visualization disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DemonstrationCase:
    """A case for viva demonstration."""
    name: str
    document_path: Path
    description: str
    focus_areas: List[str]  # ['llm_cleaning', 'multilingual', 'amendments', 'authority', 'penalty']
    expected_outcomes: Dict[str, Any]
    difficulty: str  # 'easy', 'medium', 'hard'
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComparisonResult:
    """Result of LLM vs Rule-based comparison."""
    case_name: str
    llm_score: float
    rule_score: float
    improvement: float
    llm_advantages: List[str]
    rule_advantages: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class VivaDemonstrationPreparator:
    """Prepares materials for viva demonstration."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Create subdirectories
        self.dirs = {
            'reports': self.output_dir / "reports",
            'visualizations': self.output_dir / "visualizations",
            'samples': self.output_dir / "sample_outputs",
            'presentation': self.output_dir / "presentation_materials",
        }
        
        for dir_path in self.dirs.values():
            dir_path.mkdir(exist_ok=True)
        
        # Define demonstration cases
        self.demo_cases = self._define_demo_cases()
        
        logger.info(f"Viva Demonstration Preparator initialized. Output: {self.output_dir}")
    
    def _define_demo_cases(self) -> List[DemonstrationCase]:
        """Define demonstration cases for viva."""
        return [
            DemonstrationCase(
                name="Clean Law PDF",
                document_path=Path("data/clean_law.pdf"),
                description="Well-formatted KPK Forest Ordinance PDF",
                focus_areas=["rule_extraction", "structure_detection"],
                expected_outcomes={
                    "ocr_confidence": 0.95,
                    "entity_extraction": 0.90,
                    "structure_accuracy": 0.85
                },
                difficulty="easy"
            ),
            DemonstrationCase(
                name="Messy Scanned Circular",
                document_path=Path("data/messy_circular.pdf"),
                description="Scanned circular with poor OCR, mixed languages",
                focus_areas=["llm_cleaning", "multilingual", "ambiguity_resolution"],
                expected_outcomes={
                    "llm_improvement": 0.4,
                    "multilingual_integrity": 0.8,
                    "ambiguity_resolution": 0.7
                },
                difficulty="medium"
            ),
            DemonstrationCase(
                name="Conflicting Amendments",
                document_path=Path("data/amended_law.pdf"),
                description="Law with multiple conflicting amendments",
                focus_areas=["amendment_tracking", "authority_resolution"],
                expected_outcomes={
                    "amendment_detection": 0.85,
                    "conflict_resolution": 0.75,
                    "temporal_accuracy": 0.8
                },
                difficulty="hard"
            ),
            DemonstrationCase(
                name="Mixed Language Document",
                document_path=Path("data/mixed_language.pdf"),
                description="Document with Urdu/English code-switching",
                focus_areas=["multilingual", "llm_cleaning"],
                expected_outcomes={
                    "language_preservation": 0.9,
                    "term_extraction": 0.85,
                    "structure_preservation": 0.8
                },
                difficulty="medium"
            ),
            DemonstrationCase(
                name="Complex Penalty Calculation",
                document_path=Path("data/penalty_provisions.pdf"),
                description="Document with complex penalty structures",
                focus_areas=["penalty_calculation", "rule_extraction"],
                expected_outcomes={
                    "penalty_accuracy": 0.9,
                    "calculation_confidence": 0.85,
                    "escalation_logic": 0.8
                },
                difficulty="hard"
            )
        ]
    
    def prepare_comparative_analysis(self, processing_results: List[Dict]) -> Dict:
        """
        Prepare comparative analysis of LLM vs Rule-based approaches.
        
        Args:
            processing_results: List of processing results from batch_processor
            
        Returns:
            Comparative analysis report
        """
        logger.info("Preparing comparative analysis...")
        
        # Extract metrics for comparison
        llm_metrics = []
        rule_metrics = []
        quality_scores = []
        abstention_rates = []
        
        for result in processing_results:
            phase_results = result.get('phase_results', {})
            
            # LLM cleaning metrics
            llm_cleaning = phase_results.get('llm_cleaning', {})
            if llm_cleaning.get('success'):
                llm_metrics.append(llm_cleaning.get('confidence_score', 0))
            
            # Rule extraction metrics
            rule_extraction = phase_results.get('rule_extraction', {})
            if rule_extraction.get('success'):
                rule_metrics.append(rule_extraction.get('confidence', 0))
            
            # Overall quality
            quality_scores.append(result.get('overall_score', 0))
            
            # Abstention rate
            if result.get('status') == 'abstained':
                abstention_rates.append(1)
            else:
                abstention_rates.append(0)
        
        # Calculate statistics
        comparison_results = []
        
        if llm_metrics and rule_metrics:
            for i, (llm_score, rule_score) in enumerate(zip(llm_metrics, rule_metrics)):
                improvement = llm_score - rule_score
                
                # Determine advantages
                llm_advantages = []
                rule_advantages = []
                
                if improvement > 0.1:
                    llm_advantages = ["Better OCR correction", "Context understanding"]
                    rule_advantages = ["Deterministic", "Faster"]
                elif improvement < -0.1:
                    llm_advantages = ["Handles ambiguity", "Multilingual"]
                    rule_advantages = ["More accurate for clean text", "Explainable"]
                else:
                    llm_advantages = ["Contextual", "Adaptive"]
                    rule_advantages = ["Reliable", "Transparent"]
                
                comparison_results.append(ComparisonResult(
                    case_name=f"Document_{i+1}",
                    llm_score=llm_score,
                    rule_score=rule_score,
                    improvement=improvement,
                    llm_advantages=llm_advantages,
                    rule_advantages=rule_advantages,
                    recommendations=self._generate_recommendations(llm_score, rule_score)
                ))
        
        # Generate report
        report = {
            'summary_statistics': {
                'average_llm_score': statistics.mean(llm_metrics) if llm_metrics else 0,
                'average_rule_score': statistics.mean(rule_metrics) if rule_metrics else 0,
                'average_improvement': statistics.mean([c.improvement for c in comparison_results]) 
                                      if comparison_results else 0,
                'average_quality': statistics.mean(quality_scores) if quality_scores else 0,
                'abstention_rate': statistics.mean(abstention_rates) if abstention_rates else 0,
                'total_documents_analyzed': len(processing_results)
            },
            'comparison_results': [c.to_dict() for c in comparison_results],
            'key_insights': self._generate_key_insights(comparison_results, processing_results),
            'recommendations_for_viva': self._generate_viva_recommendations(comparison_results)
        }
        
        # Save report
        report_file = self.dirs['reports'] / "comparative_analysis.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Comparative analysis saved to: {report_file}")
        
        # Generate visualization if available
        if VISUALIZATION_AVAILABLE and comparison_results:
            self._generate_comparison_visualization(comparison_results)
        
        return report
    
    def _generate_recommendations(self, llm_score: float, rule_score: float) -> List[str]:
        """Generate recommendations based on scores."""
        recommendations = []
        
        if llm_score > rule_score + 0.2:
            recommendations.append("Use LLM-based approach for similar documents")
            recommendations.append("LLM excels at context understanding and OCR correction")
        elif rule_score > llm_score + 0.2:
            recommendations.append("Rule-based approach is more reliable for this document")
            recommendations.append("Consider hybrid approach for edge cases")
        else:
            recommendations.append("Both approaches perform similarly")
            recommendations.append("Consider cost/performance trade-off")
        
        if llm_score < 0.6:
            recommendations.append("LLM confidence is low, consider manual review")
        
        if rule_score < 0.6:
            recommendations.append("Rule extraction confidence is low, check patterns")
        
        return recommendations
    
    def _generate_key_insights(self, comparison_results: List[ComparisonResult], 
                              processing_results: List[Dict]) -> List[str]:
        """Generate key insights from analysis."""
        insights = []
        
        if not comparison_results:
            return ["Insufficient data for insights"]
        
        # Calculate averages
        avg_improvement = statistics.mean([c.improvement for c in comparison_results])
        llm_wins = sum(1 for c in comparison_results if c.improvement > 0)
        rule_wins = sum(1 for c in comparison_results if c.improvement < 0)
        ties = sum(1 for c in comparison_results if -0.1 <= c.improvement <= 0.1)
        
        insights.append(f"LLM shows average improvement of {avg_improvement:.2f} over rule-based approach")
        insights.append(f"LLM performs better in {llm_wins} cases, Rule-based in {rule_wins} cases, {ties} ties")
        
        # Analyze abstention patterns
        abstentions = [r for r in processing_results if r.get('status') == 'abstained']
        if abstentions:
            reasons = []
            for a in abstentions:
                reasons.extend(a.get('abstention_reasons', []))
            
            reason_counts = Counter(reasons)
            top_reason = reason_counts.most_common(1)[0] if reason_counts else ("No reasons", 0)
            
            insights.append(f"System abstained in {len(abstentions)} cases")
            insights.append(f"Most common abstention reason: {top_reason[0]} ({top_reason[1]} cases)")
        
        # Quality gate analysis
        failed_gates = defaultdict(int)
        for result in processing_results:
            for gate in result.get('quality_gates', []):
                if not gate.get('passed', True):
                    failed_gates[gate.get('gate')] += 1
        
        if failed_gates:
            most_failed = max(failed_gates.items(), key=lambda x: x[1])
            insights.append(f"Most frequently failed quality gate: {most_failed[0]} ({most_failed[1]} failures)")
        
        # KPK-specific insights
        kpk_docs = [r for r in processing_results 
                   if any(kw in str(r) for kw in ['KPK', 'khyber', 'forest', 'ordinance'])]
        insights.append(f"Processed {len(kpk_docs)} KPK-specific forestry documents")
        
        return insights
    
    def _generate_viva_recommendations(self, comparison_results: List[ComparisonResult]) -> List[str]:
        """Generate recommendations for viva presentation."""
        recommendations = [
            "Start with clean PDF to demonstrate rule-based extraction accuracy",
            "Show messy scanned document to highlight LLM cleaning capabilities",
            "Demonstrate abstention cases to show system transparency",
            "Compare multilingual handling with and without LLM",
            "Show amendment tracking for temporal reasoning demonstration",
            "Present authority conflict resolution for complex legal hierarchy",
            "Include penalty calculation examples for practical utility",
            "Show quality gate dashboard for system reliability demonstration"
        ]
        
        if comparison_results:
            avg_improvement = statistics.mean([c.improvement for c in comparison_results])
            if avg_improvement > 0:
                recommendations.append(f"Emphasize LLM's {avg_improvement:.1%} average improvement")
            else:
                recommendations.append("Highlight rule-based reliability for clean documents")
        
        return recommendations
    
    def _generate_comparison_visualization(self, comparison_results: List[ComparisonResult]):
        """Generate visualization of comparison results."""
        try:
            # Prepare data
            case_names = [c.case_name for c in comparison_results]
            llm_scores = [c.llm_score for c in comparison_results]
            rule_scores = [c.rule_score for c in comparison_results]
            improvements = [c.improvement for c in comparison_results]
            
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('LLM vs Rule-Based Performance Comparison', fontsize=16, fontweight='bold')
            
            # Plot 1: Side-by-side comparison
            x = range(len(case_names))
            width = 0.35
            
            axes[0, 0].bar([i - width/2 for i in x], llm_scores, width, label='LLM', color='skyblue')
            axes[0, 0].bar([i + width/2 for i in x], rule_scores, width, label='Rule-Based', color='lightcoral')
            axes[0, 0].set_xlabel('Document Cases')
            axes[0, 0].set_ylabel('Confidence Score')
            axes[0, 0].set_title('Confidence Scores by Approach')
            axes[0, 0].set_xticks(x)
            axes[0, 0].set_xticklabels(case_names, rotation=45, ha='right')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            # Plot 2: Improvement chart
            colors = ['green' if imp > 0 else 'red' for imp in improvements]
            axes[0, 1].bar(case_names, improvements, color=colors)
            axes[0, 1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
            axes[0, 1].set_xlabel('Document Cases')
            axes[0, 1].set_ylabel('Improvement (LLM - Rule)')
            axes[0, 1].set_title('LLM Improvement over Rule-Based')
            axes[0, 1].set_xticklabels(case_names, rotation=45, ha='right')
            axes[0, 1].grid(True, alpha=0.3)
            
            # Plot 3: Scatter plot
            axes[1, 0].scatter(rule_scores, llm_scores, alpha=0.6, s=100)
            axes[1, 0].plot([0, 1], [0, 1], 'r--', alpha=0.5)  # y=x line
            axes[1, 0].set_xlabel('Rule-Based Score')
            axes[1, 0].set_ylabel('LLM Score')
            axes[1, 0].set_title('Correlation between Approaches')
            axes[1, 0].grid(True, alpha=0.3)
            
            # Plot 4: Summary statistics
            summary_data = [
                statistics.mean(llm_scores) if llm_scores else 0,
                statistics.mean(rule_scores) if rule_scores else 0,
                statistics.mean(improvements) if improvements else 0,
                sum(1 for imp in improvements if imp > 0.1),
                sum(1 for imp in improvements if imp < -0.1)
            ]
            summary_labels = ['Avg LLM', 'Avg Rule', 'Avg Improvement', 'LLM Wins', 'Rule Wins']
            colors_summary = ['skyblue', 'lightcoral', 'lightgreen', 'blue', 'red']
            
            axes[1, 1].bar(summary_labels, summary_data, color=colors_summary)
            axes[1, 1].set_ylabel('Score/Count')
            axes[1, 1].set_title('Summary Statistics')
            axes[1, 1].grid(True, alpha=0.3)
            
            # Adjust layout
            plt.tight_layout()
            
            # Save figure
            viz_file = self.dirs['visualizations'] / "llm_vs_rule_comparison.png"
            plt.savefig(viz_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Visualization saved to: {viz_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate visualization: {e}")
    
    def prepare_sample_outputs(self, processing_results: List[Dict]) -> Dict:
        """
        Prepare sample outputs for demonstration.
        
        Args:
            processing_results: List of processing results
            
        Returns:
            Dictionary of sample outputs
        """
        logger.info("Preparing sample outputs...")
        
        samples = {
            'best_case': None,
            'worst_case': None,
            'llm_success': None,
            'rule_success': None,
            'abstention_example': None,
            'multilingual_example': None
        }
        
        if not processing_results:
            return samples
        
        # Find best and worst by quality score
        sorted_results = sorted(processing_results, key=lambda x: x.get('overall_score', 0))
        if sorted_results:
            samples['worst_case'] = self._create_sample_summary(sorted_results[0])
            samples['best_case'] = self._create_sample_summary(sorted_results[-1])
        
        # Find good LLM example
        llm_results = [r for r in processing_results 
                      if r.get('phase_results', {}).get('llm_cleaning', {}).get('confidence_score', 0) > 0.8]
        if llm_results:
            samples['llm_success'] = self._create_sample_summary(llm_results[0])
        
        # Find good rule-based example
        rule_results = [r for r in processing_results 
                       if r.get('phase_results', {}).get('rule_extraction', {}).get('confidence', 0) > 0.8]
        if rule_results:
            samples['rule_success'] = self._create_sample_summary(rule_results[0])
        
        # Find abstention example
        abstention_results = [r for r in processing_results if r.get('status') == 'abstained']
        if abstention_results:
            samples['abstention_example'] = self._create_sample_summary(abstention_results[0])
        
        # Find multilingual example
        multilingual_results = [r for r in processing_results 
                              if r.get('phase_results', {}).get('multilingual_processing', {}).get('integrity_score', 0) > 0.7]
        if multilingual_results:
            samples['multilingual_example'] = self._create_sample_summary(multilingual_results[0])
        
        # Save samples
        samples_file = self.dirs['samples'] / "demonstration_samples.json"
        with open(samples_file, 'w', encoding='utf-8') as f:
            json.dump(samples, f, indent=2, ensure_ascii=False)
        
        # Also create CSV for easy viewing
        self._create_sample_csv(samples)
        
        logger.info(f"Sample outputs saved to: {samples_file}")
        
        return samples
    
    def _create_sample_summary(self, result: Dict) -> Dict:
        """Create a summary of a processing result for demonstration."""
        return {
            'document_id': result.get('document_id', 'unknown'),
            'overall_score': result.get('overall_score', 0),
            'status': result.get('status', 'unknown'),
            'processing_time': result.get('processing_time', 0),
            'phase_summary': {
                'ocr_extraction': result.get('phase_results', {}).get('ocr_extraction', {}).get('confidence', 0),
                'llm_cleaning': result.get('phase_results', {}).get('llm_cleaning', {}).get('confidence_score', 0),
                'multilingual': result.get('phase_results', {}).get('multilingual_processing', {}).get('integrity_score', 0),
                'rule_extraction': result.get('phase_results', {}).get('rule_extraction', {}).get('confidence', 0),
                'amendment_tracking': result.get('phase_results', {}).get('amendment_tracking', {}).get('confidence_score', 0),
            },
            'quality_gates_passed': sum(1 for g in result.get('quality_gates', []) if g.get('passed', False)),
            'quality_gates_total': len(result.get('quality_gates', [])),
            'abstention_reasons': result.get('abstention_reasons', []),
            'warnings': result.get('warnings', [])
        }
    
    def _create_sample_csv(self, samples: Dict):
        """Create CSV file of samples."""
        csv_file = self.dirs['samples'] / "demonstration_samples.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Sample Type', 'Document ID', 'Overall Score', 'Status', 
                           'OCR Score', 'LLM Score', 'Multilingual Score', 
                           'Rule Score', 'Amendment Score', 'Gates Passed', 'Processing Time'])
            
            # Write data
            for sample_type, sample in samples.items():
                if sample:
                    writer.writerow([
                        sample_type,
                        sample.get('document_id', ''),
                        sample.get('overall_score', 0),
                        sample.get('status', ''),
                        sample.get('phase_summary', {}).get('ocr_extraction', 0),
                        sample.get('phase_summary', {}).get('llm_cleaning', 0),
                        sample.get('phase_summary', {}).get('multilingual', 0),
                        sample.get('phase_summary', {}).get('rule_extraction', 0),
                        sample.get('phase_summary', {}).get('amendment_tracking', 0),
                        f"{sample.get('quality_gates_passed', 0)}/{sample.get('quality_gates_total', 0)}",
                        sample.get('processing_time', 0)
                    ])
    
    def prepare_presentation_materials(self, analysis_report: Dict, 
                                      sample_outputs: Dict) -> Dict:
        """
        Prepare presentation materials for viva.
        
        Args:
            analysis_report: Comparative analysis report
            sample_outputs: Sample outputs dictionary
            
        Returns:
            Presentation materials
        """
        logger.info("Preparing presentation materials...")
        
        presentation = {
            'title': 'GreenLawAI: KPK Forestry System - Viva Demonstration',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'sections': [
                {
                    'title': 'Project Overview',
                    'content': [
                        'Specialized system for KPK forestry laws',
                        'Hybrid approach: LLM cleaning + Rule-based reasoning',
                        'Temporal and authority-aware processing',
                        'Quality gates and abstention mechanisms'
                    ]
                },
                {
                    'title': 'Key Innovations',
                    'content': [
                        'LLM as document restorer (not interpreter)',
                        'KPK-specific legal hierarchy resolution',
                        'Multilingual Urdu/English handling',
                        'Amendment tracking with temporal reasoning',
                        'Deterministic penalty calculation engine'
                    ]
                },
                {
                    'title': 'Performance Summary',
                    'content': self._create_performance_summary(analysis_report)
                },
                {
                    'title': 'Demonstration Cases',
                    'content': [
                        f"Best case: {sample_outputs.get('best_case', {}).get('document_id', 'N/A')} "
                        f"(Score: {sample_outputs.get('best_case', {}).get('overall_score', 0):.2f})",
                        f"Worst case: {sample_outputs.get('worst_case', {}).get('document_id', 'N/A')} "
                        f"(Score: {sample_outputs.get('worst_case', {}).get('overall_score', 0):.2f})",
                        f"LLM success: {sample_outputs.get('llm_success', {}).get('document_id', 'N/A')}",
                        f"Rule-based success: {sample_outputs.get('rule_success', {}).get('document_id', 'N/A')}",
                        f"Abstention example: {sample_outputs.get('abstention_example', {}).get('document_id', 'N/A')}",
                        f"Multilingual example: {sample_outputs.get('multilingual_example', {}).get('document_id', 'N/A')}"
                    ]
                },
                {
                    'title': 'System Transparency',
                    'content': [
                        'Quality gates provide measurable confidence',
                        'Abstention logging shows system limitations',
                        'Human review queue for uncertain cases',
                        'All decisions are explainable'
                    ]
                },
                {
                    'title': 'Research Contributions',
                    'content': [
                        'KPK-specific legal authority hierarchy',
                        'Temporal amendment tracking model',
                        'Hybrid LLM+Rules architecture',
                        'Abstention-aware system design'
                    ]
                }
            ],
            'statistics': analysis_report.get('summary_statistics', {}),
            'recommendations': analysis_report.get('recommendations_for_viva', [])
        }
        
        # Save presentation
        pres_file = self.dirs['presentation'] / "viva_presentation_materials.json"
        with open(pres_file, 'w', encoding='utf-8') as f:
            json.dump(presentation, f, indent=2, ensure_ascii=False)
        
        # Create markdown version
        self._create_markdown_presentation(presentation)
        
        logger.info(f"Presentation materials saved to: {pres_file}")
        
        return presentation
    
    def _create_performance_summary(self, analysis_report: Dict) -> List[str]:
        """Create performance summary for presentation."""
        stats = analysis_report.get('summary_statistics', {})
        
        return [
            f"Documents analyzed: {stats.get('total_documents_analyzed', 0)}",
            f"Average LLM score: {stats.get('average_llm_score', 0):.2f}",
            f"Average rule-based score: {stats.get('average_rule_score', 0):.2f}",
            f"Average improvement with LLM: {stats.get('average_improvement', 0):.2f}",
            f"Overall quality score: {stats.get('average_quality', 0):.2f}",
            f"Abstention rate: {stats.get('abstention_rate', 0):.1%}",
            f"Success rate: {1 - stats.get('abstention_rate', 0):.1%}"
        ]
    
    def _create_markdown_presentation(self, presentation: Dict):
        """Create markdown version of presentation."""
        md_file = self.dirs['presentation'] / "viva_presentation.md"
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# {presentation['title']}\n\n")
            f.write(f"**Date:** {presentation['date']}\n\n")
            
            for section in presentation['sections']:
                f.write(f"## {section['title']}\n\n")
                for item in section['content']:
                    f.write(f"- {item}\n")
                f.write("\n")
            
            # Add statistics
            f.write("## Key Statistics\n\n")
            stats = presentation['statistics']
            for key, value in stats.items():
                if isinstance(value, float):
                    f.write(f"- {key.replace('_', ' ').title()}: {value:.2f}\n")
                else:
                    f.write(f"- {key.replace('_', ' ').title()}: {value}\n")
            
            f.write("\n")
            
            # Add recommendations
            f.write("## Viva Recommendations\n\n")
            for rec in presentation['recommendations']:
                f.write(f"- {rec}\n")
    
    def generate_full_demonstration_package(self, processing_results: List[Dict]) -> Dict:
        """
        Generate complete demonstration package.
        
        Args:
            processing_results: List of processing results
            
        Returns:
            Complete demonstration package
        """
        logger.info("Generating complete demonstration package...")
        
        # Step 1: Comparative analysis
        analysis_report = self.prepare_comparative_analysis(processing_results)
        
        # Step 2: Sample outputs
        sample_outputs = self.prepare_sample_outputs(processing_results)
        
        # Step 3: Presentation materials
        presentation = self.prepare_presentation_materials(analysis_report, sample_outputs)
        
        # Create package summary
        package = {
            'generated_at': datetime.now().isoformat(),
            'total_documents': len(processing_results),
            'analysis_report': analysis_report,
            'sample_outputs': sample_outputs,
            'presentation_materials': presentation,
            'files_generated': self._list_generated_files()
        }
        
        # Save complete package
        package_file = self.output_dir / "complete_demonstration_package.json"
        with open(package_file, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Complete demonstration package saved to: {package_file}")
        
        # Print summary
        self._print_demonstration_summary(package)
        
        return package
    
    def _list_generated_files(self) -> List[str]:
        """List all generated files."""
        files = []
        
        for dir_name, dir_path in self.dirs.items():
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    files.append(str(file_path.relative_to(self.output_dir)))
        
        return files
    
    def _print_demonstration_summary(self, package: Dict):
        """Print demonstration summary to console."""
        print("\n" + "="*70)
        print("VIVA DEMONSTRATION PACKAGE - SUMMARY")
        print("="*70)
        
        stats = package.get('analysis_report', {}).get('summary_statistics', {})
        
        print(f"\n📊 PERFORMANCE STATISTICS:")
        print(f"   Documents analyzed: {stats.get('total_documents_analyzed', 0)}")
        print(f"   Average LLM score: {stats.get('average_llm_score', 0):.2f}")
        print(f"   Average rule-based score: {stats.get('average_rule_score', 0):.2f}")
        print(f"   LLM improvement: {stats.get('average_improvement', 0):+.2f}")
        print(f"   Overall quality: {stats.get('average_quality', 0):.2f}")
        print(f"   Abstention rate: {stats.get('abstention_rate', 0):.1%}")
        
        print(f"\n📁 GENERATED FILES:")
        files = package.get('files_generated', [])
        for file in files[:10]:  # Show first 10 files
            print(f"   • {file}")
        if len(files) > 10:
            print(f"   • ... and {len(files) - 10} more")
        
        print(f"\n🎯 KEY INSIGHTS:")
        insights = package.get('analysis_report', {}).get('key_insights', [])
        for insight in insights[:5]:
            print(f"   • {insight}")
        
        print(f"\n💡 VIVA RECOMMENDATIONS:")
        recommendations = package.get('presentation_materials', {}).get('recommendations', [])
        for rec in recommendations[:5]:
            print(f"   • {rec}")
        
        print(f"\n📂 OUTPUT DIRECTORY: {self.output_dir}")
        print("="*70)


def main():
    """Main entry point for demonstration preparation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Viva Demonstration Preparation')
    parser.add_argument('--input', required=True, help='Input JSON file with processing results')
    parser.add_argument('--output', help='Output directory for demonstration materials')
    parser.add_argument('--generate-all', action='store_true', help='Generate complete package')
    parser.add_argument('--analysis-only', action='store_true', help='Generate only analysis')
    parser.add_argument('--samples-only', action='store_true', help='Generate only samples')
    
    args = parser.parse_args()
    
    # Load processing results
    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            processing_results = json.load(f)
        
        # Check if it's a list or has results key
        if isinstance(processing_results, dict) and 'document_statistics' in processing_results:
            # Assume it's from batch_processor report
            processing_results = processing_results['document_statistics']
        
        logger.info(f"Loaded {len(processing_results)} processing results")
        
    except Exception as e:
        logger.error(f"Failed to load processing results: {e}")
        return
    
    # Initialize preparator
    output_dir = Path(args.output) if args.output else Path("viva_demonstration")
    preparator = VivaDemonstrationPreparator(output_dir)
    
    # Generate requested materials
    if args.generate_all or (not args.analysis_only and not args.samples_only):
        preparator.generate_full_demonstration_package(processing_results)
    elif args.analysis_only:
        preparator.prepare_comparative_analysis(processing_results)
    elif args.samples_only:
        preparator.prepare_sample_outputs(processing_results)


if __name__ == "__main__":
    main()
