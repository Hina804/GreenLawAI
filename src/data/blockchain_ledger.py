import hashlib
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class BlockchainLedger:
    """
    Simulated Immutable Ledger for Permit Auditing.
    Uses SHA-256 hash chaining to ensure permit integrity.
    """
    def __init__(self, ledger_path: str = "data/permit_chain.json"):
        self.ledger_path = os.path.join(os.getcwd(), ledger_path)
        self._ensure_storage()
        self.chain = self._load()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        if not os.path.exists(self.ledger_path):
            # Genesis Block
            genesis = self._create_block(data="GENESIS_BLOCK", prev_hash="0"*64)
            with open(self.ledger_path, "w") as f:
                json.dump([genesis], f)

    def _load(self) -> List[Dict]:
        try:
            with open(self.ledger_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load ledger: {e}")
            return []

    def _calculate_hash(self, block: Dict) -> str:
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def _create_block(self, data: Any, prev_hash: str) -> Dict:
        block = {
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "prev_hash": prev_hash,
            "nonce": 0 # For future Proof-of-Work if needed
        }
        block["hash"] = self._calculate_hash(block)
        return block

    def record_permit(self, permit_id: str, applicant_cnic: str, decision_score: float) -> str:
        """Records a permit on the ledger and returns the block hash."""
        prev_hash = self.chain[-1]["hash"] if self.chain else "0"*64
        
        # We record a compact summary of the permit and its integrity hash
        permit_summary = {
            "permit_id": permit_id,
            "applicant_hash": hashlib.sha256(applicant_cnic.encode()).hexdigest(),
            "decision_score": decision_score,
            "verification_status": "AUTHENTICATED"
        }
        
        new_block = self._create_block(data=permit_summary, prev_hash=prev_hash)
        self.chain.append(new_block)
        
        try:
            with open(self.ledger_path, "w") as f:
                json.dump(self.chain, f, indent=4)
            return new_block["hash"]
        except Exception as e:
            logger.error(f"Failed to write to ledger: {e}")
            return "ERROR_RECORDING_BLOCK"

    def verify_chain(self) -> bool:
        """Verifies the integrity of the entire chain."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            
            # Re-calculate hash
            temp_block = {k: v for k, v in current.items() if k != "hash"}
            if current["hash"] != self._calculate_hash(temp_block):
                return False
                
            if current["prev_hash"] != previous["hash"]:
                return False
        return True

# Global singleton
blockchain_ledger = BlockchainLedger()
