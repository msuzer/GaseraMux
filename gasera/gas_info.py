from typing import Dict, Optional, Any

CAS_INFO: Dict[str, Dict[str, str]] = {
    "74-82-8": {
        "name": "Methane",
        "formula": "CH₄",
        "color": "#ff9f40",  # bright orange
    },
    "124-38-9": {
        "name": "Carbon Dioxide",
        "formula": "CO₂",
        "color": "#ff6384",  # bright pink/red
    },
    "7732-18-5": {
        "name": "Water Vapor",
        "formula": "H₂O",
        "color": "#2ca02c",  # vivid green/teal
    },
    "630-08-0": {
        "name": "Carbon Monoxide",
        "formula": "CO",
        "color": "#d62728",
    },
    "10024-97-2": {
        "name": "Nitrous Oxide",
        "formula": "N₂O",
        "color": "#ffcd56",  # bright yellow
    },
    "7664-41-7": {
        "name": "Ammonia",
        "formula": "NH₃",
        "color": "#1f77b4",  # vivid blue
    },
    "7446-09-5": {
        "name": "Sulfur Dioxide",
        "formula": "SO₂",
        "color": "#e377c2",
    },
    "7782-44-7": {
        "name": "Oxygen",
        "formula": "O₂",
        "color": "#7f7f7f",
    },
    "75-07-0": {
        "name": "Acetaldehyde",
        "formula": "CH₃CHO",
        "color": "#bcbd22",
    },
    "64-17-5": {
        "name": "Ethanol",
        "formula": "C₂H₅OH",
        "color": "#17becf",
    },
    "67-56-1": {
        "name": "Methanol",
        "formula": "CH₃OH",
        "color": "#a05d56",
    },
}

def get_gas_info(cas: str) -> Optional[Dict[str, str]]:
    """Return the gas information dict for a given CAS code, or None if not found."""
    return CAS_INFO.get(cas)


def get_gas_name(cas: str) -> str:
    """Return the gas name for a given CAS code."""
    return CAS_INFO.get(cas, {}).get("name", "Unknown Gas")


def get_gas_formula(cas: str) -> str:
    """Return the chemical formula for a given CAS code."""
    return CAS_INFO.get(cas, {}).get("formula", "Unknown Formula")


def get_color_for_cas(cas: str) -> str:
    """Return the associated display color for a given CAS code."""
    return CAS_INFO.get(cas, {}).get("color", "#999")


def get_cas_details(cas: str) -> Dict[str, Any]:
    """
    Return a detailed dictionary with all relevant info for charting/UI:
    {
        "cas": "124-38-9",
        "name": "Carbon Dioxide",
        "formula": "CO₂",
        "label": "Carbon Dioxide (CO₂, 124-38-9)",
        "color": "#ff7f0e"
    }
    """
    gas = CAS_INFO.get(cas, {})
    name = gas.get("name", "")
    formula = gas.get("formula", "")
    label = f"{name} ({formula}, {cas})" if name and formula else cas
    color = gas.get("color", "#999")

    return {
        "cas": cas,
        "name": name,
        "formula": formula,
        "label": label,
        "color": color,
    }

def build_label_to_color_map() -> Dict[str, str]:
    """Return mapping of "Name (Formula, CAS)" -> color used by frontend."""
    out: Dict[str, str] = {}
    for cas, info in CAS_INFO.items():
        name = info.get("name", "")
        formula = info.get("formula", "")
        label = f"{name} ({formula}, {cas})" if name and formula else cas
        out[label] = info.get("color", "#999")
    return out