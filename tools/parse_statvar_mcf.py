"""Parse Data Commons StatVar MCF files into structured dicts."""
from pathlib import Path
from typing import Dict, List

_SKIP_PROPERTIES = {"typeOf", "name", "nameWithLanguage", "alternateName",
                     "description", "descriptionUrl"}

_POP_TYPE_CATEGORIES = {
    "Person": "Demographics",
    "Household": "Demographics",
    "Student": "Education",
    "EconomicActivity": "Economy",
    "Establishment": "Economy",
    "BLSEstablishment": "Economy",
    "BLSWorker": "Economy",
    "USCEstablishment": "Economy",
    "FarmInventory": "Economy",
    "MedicalConditionIncident": "Health",
    "MedicalEvent": "Health",
    "Place": "Energy",
}

_PERSON_HEALTH_PROPS = {"medicalCondition", "healthBehavior", "healthOutcome",
                         "causeOfDeath", "diseaseSeverity"}
_PERSON_EMPLOYMENT_PROPS = {"workStatus", "workerClassification", "occupation",
                             "naics", "employerType"}
_PERSON_EDUCATION_PROPS = {"educationalAttainment", "schoolEnrollment",
                            "schoolGradeLevel", "schoolSubject"}


def parse_mcf_statvars(mcf_text: str) -> List[Dict[str, str]]:
    """Parse MCF text into list of StatVar dicts.
    Each dict has 'dcid' plus property keys with dcs:-prefixed values.
    """
    statvars = []
    current_node = None

    for line in mcf_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("Node:"):
            if current_node and "populationType" in current_node:
                statvars.append(current_node)
            dcid_raw = line.split(":", 1)[1].strip()
            dcid = dcid_raw.replace("dcid:", "").strip()
            current_node = {"dcid": dcid}
            continue
        if ":" in line and current_node is not None:
            prop, _, val = line.partition(":")
            prop = prop.strip()
            val = val.strip()
            if prop in _SKIP_PROPERTIES:
                continue
            if val.startswith("dcid:"):
                val = "dcs:" + val[5:]
            current_node[prop] = val

    if current_node and "populationType" in current_node:
        statvars.append(current_node)
    return statvars


def classify_statvar_category(sv: Dict[str, str]) -> str:
    """Classify a StatVar dict into a schema category."""
    pop_type_raw = sv.get("populationType", "")
    pop_type = pop_type_raw.replace("dcs:", "")
    if pop_type in _POP_TYPE_CATEGORIES:
        category = _POP_TYPE_CATEGORIES[pop_type]
        if pop_type == "Person":
            sv_props = set(sv.keys())
            if sv_props & _PERSON_HEALTH_PROPS:
                return "Health"
            if sv_props & _PERSON_EMPLOYMENT_PROPS:
                return "Employment"
            if sv_props & _PERSON_EDUCATION_PROPS:
                return "Education"
        return category
    return "Economy"


def parse_mcf_file(mcf_path: Path) -> List[Dict[str, str]]:
    """Parse an MCF file from disk."""
    text = mcf_path.read_text(encoding="utf-8")
    return parse_mcf_statvars(text)


def group_by_category(statvars: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """Group StatVars by category."""
    groups: Dict[str, List[Dict[str, str]]] = {}
    for sv in statvars:
        cat = classify_statvar_category(sv)
        groups.setdefault(cat, []).append(sv)
    return groups
