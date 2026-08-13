import smtplib
import socket
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection(server, port, use_ssl=False):
    print(f"Testing {server}:{port} (SSL={use_ssl})...", end=" ", flush=True)
    try:
        if use_ssl:
            s = smtplib.SMTP_SSL(server, port, timeout=10)
        else:
            s = smtplib.SMTP(server, port, timeout=10)
        s.noop()
        s.quit()
        print("✅ SUCCESS")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def main():
    print("--- GreenLawAI Email Diagnostic ---")
    targets = [
        ("smtp.gmail.com", 465, True),
        ("smtp.gmail.com", 587, False),
        ("smtp.gmail.com", 25, False),
        ("alt1.smtp.gmail.com", 465, True),
        ("alt1.smtp.gmail.com", 587, False),
    ]
    
    results = []
    for server, port, ssl in targets:
        results.append(test_connection(server, port, ssl))
    
    print("\n--- Summary ---")
    if any(results):
        print("Great! At least one connection worked. Update your .env with a working Server/Port.")
    else:
        print("CRITICAL: All SMTP connections timed out.")
        print("This means your current Network (ISP or Firewall) is blocking standard Email ports.")
        print("Recommendation: Try a different internet connection (Mobile Hotspot) or check Windows Firewall.")

if __name__ == "__main__":
    main()
