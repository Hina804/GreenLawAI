
import asyncio
import json
from evaluation.evaluation_runner import EvaluationRunner
from loguru import logger

async def test_single():
    runner = EvaluationRunner()
    test_set = runner.load_test_set()
    
    # Just take the first question for verification
    subset = test_set[:1]
    
    logger.info("Running pilot inference on 1 question...")
    try:
        results = await runner.run_inference(subset)
        print("\n--- INFERENCE RESULT ---")
        print(json.dumps(results, indent=2))
        print("------------------------\n")
        
        # Save to raw_results for inspection
        runner.save_results(results, "data/evaluation/pilot_results.json")
        logger.info("Pilot results saved.")
    except Exception as e:
        logger.error(f"Pilot run failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_single())
