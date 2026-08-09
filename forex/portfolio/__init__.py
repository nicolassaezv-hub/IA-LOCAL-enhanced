"""forex/portfolio — Portfolio y Opportunity Score Roadmap VI."""
try:
    from forex.portfolio.opportunity_score import (
        OpportunityRanker, OpportunityResult, SignalInput,
        calculate_op_score, get_ranker
    )
except ImportError:
    pass
