
import time
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.security import RateLimiter

def test_unit_rate_limiter():
    print("Unit Testing RateLimiter...")
    
    # 1. 5 requests per minute limit
    limiter = RateLimiter(requests_per_minute=5)
    client = "user_1"
    
    # 2. Allow first 5
    for i in range(5):
        allowed = limiter.is_allowed(client)
        print(f"Request {i+1}: {'Allowed' if allowed else 'Denied'}")
        if not allowed:
            print("❌ Error: Should have been allowed.")
            return

    # 3. Deny 6th
    denied = limiter.is_allowed(client)
    print(f"Request 6: {'Allowed' if denied else 'Denied'}")
    if denied:
        print("❌ Error: Should have been denied.")
        return
    else:
        print("✅ Correctly denied.")

    print("\n✅ RateLimiter Unit Test Passed!")

if __name__ == "__main__":
    test_unit_rate_limiter()
