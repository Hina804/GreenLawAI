
import os
import sys
import json
import logging
import asyncio
from pathlib import Path

# Add src to path
SRC_DIR = Path("E:/GL_AI/src")
sys.path.append(str(SRC_DIR))

# Import Orchestrator
from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import KPKPipelineOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Full list of 16 missing/deleted documents to restore
RAW_DOCS = {
    "Climate_Action_Board_2025": "climate/kpk/laws/The-Khyber-Pakhtunkhwa-Climate-Action-Board-Act-2025-GC.pdf",
    "Forest_Act_1927": "forestry/federal/laws/forest_act_1927.pdf",
    "Hazara_Ordinance_1980": "forestry/kpk/laws/(CONSERVATION_AND_EXPLOITATION_OF_CERTAIN_FORESTS_IN_HAZARA_DIVISION)_ORDINANCE,_1980.pdf",
    "Firewood_Charcoal_1964": "forestry/kpk/laws/1964_11_THE_WEST_PAKISTAN_FIREWOOD_AND_CHARCOAL_RESTRICTION_ACT_1964.pdf",
    "Forestry_Commission_1999": "forestry/kpk/laws/1999_15_THE_KHYBER_PAKHTUNKHWA_FORESTRY_COMMISSION_ACT_1999.pdf",
    "FDC_Ordinance_1980": "forestry/kpk/laws/FOREST_DEVELOPMENT_CORPORATION_ORDINANCE,_1980.pdf",
    "KPK_Forest_Ordinance_2002": "forestry/kpk/laws/kpk_forest_ordinance_2002.pdf",
    "Parks_Horticulture_2024": "forestry/kpk/laws/The-Khyber-Pakhtunkhwa-Parks-and-Horticulture-Act-2024.pdf",
    "NWF_Forest_Ord_2002_XIX": "forestry/kpk/laws/The-North-West-Frontier-Province-Forest-Ordinance-2002-Ord-No.-XIX-2002.pdf",
    "Wildlife_Act_2015": "forestry/kpk/laws/rules/2015_1_THE_KHYBER_PAKHTUNKHWA_WILDLIFE_AND_BIODIVERSITY_PROTECTION_PRESERVATION_CONSERVATION_AND_MANAGEMENT_ACT_2015.pdf",
    "Forest_Transport_Rules_2004": "forestry/kpk/laws/rules/Khyber_Pakhtunkhwa_Forest_Produce_Transport_Rules,_2004.pdf",
    "Guzara_Rules_2004": "forestry/kpk/laws/rules/Khyber_Pakhtunkhwa_Management_of_Guzara_Forest_Rules,_2004._.pdf",
    "Protected_Forest_Rules_2005": "forestry/kpk/laws/rules/Khyber_Pakhtunkhwa_Protected_Forest_Management_Rules,_2005.pdf",
    "Climate_Change_Policy_2022": "forestry/kpk/laws/rules/KPK_Climate_Change_Policy_2022.pdf",
    "Env_Protection_Act_2014": "forestry/kpk/laws/rules/KPK_Environmental_Protection_Act_2014.pdf",
    "Game_Reserve_Rules_1993": "forestry/kpk/laws/rules/KPK_Private_Game_Reserve_Rules_1993.pdf"
}

async def perfect_corpus():
    orchestrator = KPKPipelineOrchestrator()
    data_raw_root = Path("E:/GL_AI/data_raw")
    
    print(f"Starting restoration of {len(RAW_DOCS)} documents...")
    
    count = 0
    for doc_alias, rel_path in RAW_DOCS.items():
        pdf_path = data_raw_root / rel_path
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            continue
            
        count += 1
        logger.info(f"--- [{count}/{len(RAW_DOCS)}] RESTORING {doc_alias} ---")
        try:
            # force re-processing
            context = await orchestrator.process_document(str(pdf_path), use_dag=True)
            logger.info(f"Finished {doc_alias}: Status {context.status}")
        except Exception as e:
            logger.error(f"Failed to process {doc_alias}: {e}")

if __name__ == "__main__":
    asyncio.run(perfect_corpus())
