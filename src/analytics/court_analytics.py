from typing import List, Dict, Any
import pandas as pd
import numpy as np
from src.data.court_schema import CourtCase

class CourtAnalytics:
    """
    Aggregation engine for calculating legal trends and statistics.
    """

    @staticmethod
    def aggregate_statistics(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates high-level metrics from a list of case dictionaries."""
        if not cases:
            return {
                "total_cases": 0,
                "conviction_rate": 0,
                "avg_penalty_rs": 0,
                "common_offenses": {}
            }
            
        df = pd.DataFrame(cases)
        
        total_cases = len(df)
        guilty_cases = len(df[df['verdict'].str.lower() == 'guilty'])
        conviction_rate = (guilty_cases / total_cases) * 100
        
        # Calculate penalty stats
        avg_penalty = df['penalty_amount_rs'].mean()
        max_penalty = df['penalty_amount_rs'].max()
        
        # Offense trends
        offense_counts = df['offense_category'].value_counts().to_dict()
        
        # Protected vs Unprotected
        protected_count = len(df[df['is_protected_forest'] == True])
        
        return {
            "total_cases": total_cases,
            "conviction_rate": round(conviction_rate, 2),
            "avg_penalty_rs": round(avg_penalty, 2),
            "max_penalty_rs": int(max_penalty),
            "offense_trends": offense_counts,
            "protected_forest_ratio": round(protected_count / total_cases, 2) if total_cases > 0 else 0
        }

    @staticmethod
    def get_penalty_forecast(offense_category: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Predicts likely penalty range for a category based on history."""
        relevant_cases = [c for c in cases if c['offense_category'] == offense_category]
        if not relevant_cases:
            return {"status": "insufficient_data"}
            
        amounts = [c['penalty_amount_rs'] for c in relevant_cases]
        return {
            "category": offense_category,
            "min_likely": int(np.percentile(amounts, 25)),
            "median": int(np.median(amounts)),
            "max_likely": int(np.percentile(amounts, 75)),
            "sample_size": len(relevant_cases)
        }
