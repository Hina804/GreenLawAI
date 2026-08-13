
import os
import requests
from pathlib import Path

# URLs identified by supervisor
DOCS = {
    "KPK_Forest_Produce_Transport_Rules_2004.pdf": "http://kpcode.kp.gov.pk/uploads/Khyber_Pakhtunkhwa_Forest_Produce_Transport_Rules,_2004.pdf",
    "KPK_Protected_Forest_Management_Rules_2005.pdf": "http://kpcode.kp.gov.pk/uploads/Khyber_Pakhtunkhwa_Protected_Forest_Management_Rules,_2005.pdf",
    "KPK_Wildlife_And_Biodiversity_Act_2015.pdf": "http://kpcode.kp.gov.pk/uploads/2015_1_THE_KHYBER_PAKHTUNKHWA_WILDLIFE_AND_BIODIVERSITY_PROTECTION_PRESERVATION_CONSERVATION_AND_MANAGEMENT_ACT_2015.pdf",
    "KPK_Private_Game_Reserve_Rules_1993.pdf": "https://kpcode.kp.gov.pk/uploads/Private_Game_Reserve_Rules_1993.pdf",
    "KPK_Environmental_Protection_Act_2014.pdf": "https://kpcode.kp.gov.pk/uploads/THE_KHYBER_PAKHTUNKHWA_ENVIRONMENTAL_PROTECTION_ACT_2014.pdf",
    "KPK_Climate_Change_Policy_2022.pdf": "https://epakp.gov.pk/wp-content/uploads/2022/09/Khyber-Pakhtunkhwa-Climate-Change-Policy-2022.pdf",
    "KPK_Management_of_Guzara_Forest_Rules_2004.pdf": "http://kpcode.kp.gov.pk/uploads/Khyber_Pakhtunkhwa_Management_of_Guzara_Forest_Rules,_2004.pdf",
    "KPK_Forest_Officers_Rules_2004.pdf": "http://kpcode.kp.gov.pk/uploads/Khyber_Pakhtunkhwa_Forest_Officers_Powers_Duties_and_Reward_Rules,_2004.pdf"
}

TARGET_DIR = Path("e:/GL_AI/data_raw/forestry/kpk/laws/rules")

def download_files():
    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"📥 Target Directory: {TARGET_DIR}")
    
    for filename, url in DOCS.items():
        filepath = TARGET_DIR / filename
        if filepath.exists():
            print(f"⏩ Skipping {filename} (Already exists)")
            continue
            
        print(f"📡 Downloading: {filename}...")
        try:
            # Increase timeout for government servers
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"✅ Saved: {filename}")
        except Exception as e:
            print(f"❌ Failed to download {filename}: {e}")

if __name__ == "__main__":
    download_files()
