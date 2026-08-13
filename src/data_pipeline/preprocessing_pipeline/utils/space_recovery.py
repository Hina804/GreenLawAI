"""
Space Recovery Engine - Fixes concatenated OCR text via Viterbi word segmentation.
"""
import re, math, logging
logger = logging.getLogger(__name__)

# Top common English words + KPK domain terms
_COMMON = """a an the of in to for and is it by on at or as be was are with that this from but not
all were can had has have been its may per will than one two no so do if up he she we my our us
his her who did how out any own also each such more some very when only into over much most them
then what well made just about after before between under through during both few many other being
same where would could should shall must need upon which there their these those here now its"""

_DOMAIN = """forest forests forestry division divisional tree trees timber fuelwood firewood wood
plantation plantations afforestation reforestation deforestation planting species deodar chir pine
kail walnut oak poplar eucalyptus acacia dalbergia sissoo phulai kao sanatha ber conifer conifers
broadleaved scrub degraded watershed catchment erosion soil soils geology alluvial drainage basin
river stream climate rainfall monsoon temperature humidity elevation slope terrain grazing rangeland
pasture fodder wildlife habitat biodiversity conservation protection preservation regeneration
silvicultural silviculture thinning pruning felling selection improvement rotation enrichment
stocking canopy crown density volume increment growth mature immature nursery seedling sapling
logging harvest harvesting encroachment patrolling checkpost fire damage pest infestation
section act ordinance rule rules regulation regulations penalty fine fines compensation
imprisonment punishable liable offence offences violation amendment amended substituted inserted
deleted omitted notification gazette government provincial federal state authority officer officers
appointment transfer promotion civil servant servants administration administrative department
ministry commissioner conservator inspector guard ranger deputy court judgment verdict appeal
petition petitioner respondent appellant prosecution accused convicted acquitted sentenced dismissed
haripur abbottabad mansehra battagram kohistan shangla buner swat chitral dir malakand peshawar
kohat bannu lakki marwat karak hangu orakzai kurram waziristan hazara tarbela khanpur ghazi
sirikot siran kaghan naran balakot agror tanawal galis kunhar unhar daur torghar indus kabul
pakistan punjab sindh balochistan islamabad pakhtunkhwa khyber nwfp northern southern eastern
western chapter part annex appendix table figure page preface overview working plan prepared
approved report annual quarterly monthly progress performance status updated revised summary
description profile inventory survey assessment evaluation monitoring control financial expenditure
revenue cost budget forecast projection estimate target achievement result objective strategy
proposal prescription guideline methodology standard procedure framework component programme
project scheme initiative intervention activity operation resource management development planning
implementation organization committee community participation consultation stakeholder village
district region province area unit range beat block circle zone headquarters staff position vacancy
sanctioned filled required additional needed existing proposed current future total average maximum
minimum percentage rate ratio value amount number count hectares meters kilometers square cubic tons
million billion semi following standardized methodology resource center centre approved developed
comprises main strategic level operational covering period ten five primary ensures wise use upland
non concert local communities satisfy needs marketable products enhance environmental promote
economic growth map located covering portion coordinates latitude longitude bounded north south east
west comprises divided administratively ranges city central formation sandstone clay conglomerate
deposits pre cambrian rocks phyllites schists marbles plains terraces types type characteristics
cover loam moderate fertility good retention mixed sandy drained gravelly shallow depth profile
agricultural land subtropical distinct seasonal variations parameter value arid summer winter
december january september march humidity percent snowfall nil rare frost higher major body length
affected perennial boundary reservoir lake southwestern dam nullahs streams distributed throughout
composition condition crop distribution percentage roxburghii leaved blanks reserved growing stock
commercial constitute dominant covering approximately primarily meters pure stands occasional age
class young middle aged height diameter breast regeneration status fair occurring drier lower
modesta olea ferruginea dodonaea viscosa zizyphus mauritiana various established schemes year
survival camaldulensis nilotica conifers comprise categorized category pressure intensively grazed
moderately lightly protected enclosed excellent injury severity trend stable illegal increasing
decreasing valleys irrigated rain fed livestock alpine pastures significant exist due tenure
ownership pattern secondary private cultivation collection communal settlement residential problems
opportunities managing overgrazing leading conversion lack alternative energy sources demand weak
enforcement potential agroforestry interventions involvement introduction improved measures socio
history managed structure villages mouzas population rural urban ethnic groups hindko speaking
pashto clans khels tanolis gujars syeds awans tenures state owned guzara cultural patterns
predominantly agrarian society rearing occupation joint family system prevalent jirga active
conflict resolution strong bonds traditional sharing mechanisms conditions livelihood source
dependent activities labor employment business trade remittances conflicts customs sanction systems
minor disputes between rights dispute imposed trends demands resources product consumption
projected deficit surplus timber cubic public issues concerns concern scarcity loss ngo situation
currently vacancy sub clerical governmental organizations world fund wwf iucn drives availability
skilled adequate operations daily wage unskilled process statistics followed stage prescribed
development satellite imagery systematic sampling surveys mouza detailed committee abc formation
participatory utilization produce change previous cum cycle girth limit dbh annual allowable
guidelines identify units suitable specific functions roles deliver determine strategies sustainable
principles priority frame exceed participation involved values multiple provide services adaptive
prescriptions reviewed adjusted based results method treatment removal diseased trees suppressed
clear rotational replanting rehabilitation circles production meeting force january steep slopes
only fireline maintenance works cut single near enhanced access quota allocation dead line
shelterbelts committees abcs covered member households adjoining town surrounding nearby opened
roads metalled tracks mix ratios reorganization creation implemented increased regulated indicator
frequency maintain increase greater fewer satisfaction expenditures royalties net"""

class SpaceRecoveryEngine:
    def __init__(self):
        self.word_cost = {}
        self.max_word_len = 0
        self._build()

    def _build(self):
        wc = {}
        for w in _COMMON.split():
            wc[w.strip()] = 10_000_000
        for w in _DOMAIN.split():
            w = w.strip()
            if w:
                wc[w] = 5_000_000
        for ch in "abcdefghijklmnopqrstuvwxyz":
            if ch not in wc:
                wc[ch] = 200
        total = sum(wc.values())
        for w, c in wc.items():
            self.word_cost[w] = math.log(total / c)
            self.max_word_len = max(self.max_word_len, len(w))

    def _viterbi(self, s_orig):
        s = s_orig.lower()
        n = len(s)
        INF = float('inf')
        dp = [(0, -1)] + [(INF, -1)] * n
        for i in range(1, n + 1):
            best_c, best_j = INF, i - 1
            for j in range(max(0, i - self.max_word_len), i):
                w = s[j:i]
                wc = self.word_cost.get(w)
                if wc is None:
                    wc = 30.0 + len(w) * 2.0 if len(w) > 2 else 80.0
                cand = dp[j][0] + wc
                if cand < best_c:
                    best_c, best_j = cand, j
            dp[i] = (best_c, best_j)
        if dp[-1][0] >= 1e8:
            return s_orig
        words, curr = [], n
        while curr > 0:
            prev = dp[curr][1]
            words.append(s_orig[prev:curr])
            curr = prev
        words.reverse()
        return " ".join(words)

    def _process(self, token):
        if not token.isalpha():
            return token
        if token.lower() in self.word_cost:
            return token
        if len(token) < 5:
            return token
        pieces = re.split(r'(?<=[a-z])(?=[A-Z])', token)
        out = []
        for p in pieces:
            if len(p) >= 5 and p.lower() not in self.word_cost:
                out.append(self._viterbi(p))
            else:
                out.append(p)
        return " ".join(out)

    def recover_spaces(self, text):
        if not text:
            return text
        parts = re.split(r'(\s+|[^\w]+)', text)
        for i, p in enumerate(parts):
            if p.isalpha():
                parts[i] = self._process(p)
        return "".join(parts)

def apply_space_recovery_to_file(json_path):
    import json
    from pathlib import Path
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    engine = SpaceRecoveryEngine()
    raw = data.get("data", {}).get("raw_text", "")
    if raw:
        data["data"]["raw_text"] = engine.recover_spaces(raw)
        data["data"]["space_recovery_applied"] = True
    return data

if __name__ == "__main__":
    engine = SpaceRecoveryEngine()
    tests = [
        "ThisWorkingPlanforHaripurForestDivisionhasbeen",
        "preparedfollowingthestandardized",
        "methodologyforResourceInventoryandPlanningas",
        "DivisionalForestOfficer",
        "ChiefConservatorofForests",
        "GovernmentofKhyberPakhtunkhwa",
        "HWORKINGPLANFORHARIPURFORESTDIVISION",
    ]
    for t in tests:
        print(f"  IN: {t}")
        print(f" OUT: {engine.recover_spaces(t)}")
        print()
