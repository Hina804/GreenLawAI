import logging
import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Any, List
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class BlockchainRecorder(BaseTool):
    """
    Simulates recording evidence hashes to a tamper-evident blockchain ledger.
    """
    def __init__(self):
        super().__init__(
            name="blockchain_recorder",
            description="Records a digital fingerprint (hash) of evidence to a tamper-evident ledger."
        )
        self.ledger_path = "e:/GL_AI/data/memory/blockchain_ledger.json"
        if not os.path.exists(self.ledger_path):
            self._save_ledger([])

    def _save_ledger(self, ledger: List):
        with open(self.ledger_path, 'w') as f:
            json.dump(ledger, f, indent=2)

    def _load_ledger(self) -> List:
        with open(self.ledger_path, 'r') as f:
            return json.load(f)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - evidence_data: String or dict of the evidence to hash.
        - metadata: Additional context.
        """
        evidence = parameters.get("evidence_data", "")
        if isinstance(evidence, dict):
            evidence = json.dumps(evidence, sort_keys=True)
        
        # Create Hash
        evidence_hash = hashlib.sha256(evidence.encode()).hexdigest()
        
        # Prepare Block
        ledger = self._load_ledger()
        prev_hash = ledger[-1]['block_hash'] if ledger else "0" * 64
        
        block = {
            "index": len(ledger),
            "timestamp": datetime.now().isoformat(),
            "evidence_hash": evidence_hash,
            "previous_block_hash": prev_hash,
            "metadata": parameters.get("metadata", {})
        }
        
        # Mock "mining" / final hash
        block["block_hash"] = hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()
        
        ledger.append(block)
        self._save_ledger(ledger)
        
        logger.info(f"BlockchainRecorder: Evidence recorded. Hash: {evidence_hash}")
        
        return {
            "status": "recorded",
            "evidence_hash": evidence_hash,
            "block_index": block["index"],
            "block_hash": block["block_hash"]
        }
