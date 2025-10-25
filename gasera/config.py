# gasera_config.py

CAS_DETAILS = {
    "74-82-8": ("Methane", "CH₄"),
    "124-38-9": ("Carbon Dioxide", "CO₂"),
    "7732-18-5": ("Water Vapor", "H₂O"),
    "630-08-0": ("Carbon Monoxide", "CO"),
    "10024-97-2": ("Nitrous Oxide", "N₂O"),
    "7664-41-7": ("Ammonia", "NH₃"),
    "7446-09-5": ("Sulfur Dioxide", "SO₂"),
    "7782-44-7": ("Oxygen", "O₂"),
    "75-07-0": ("Acetaldehyde", "C₂H₄O"),
    "64-17-5": ("Ethanol", "C₂H₆O"),
    "67-56-1": ("Methanol", "CH₄O"),
}

# Consistent color mapping for charting (Chart.js, Bootstrap-safe)
CAS_COLORS = {
    "74-82-8": "#1f77b4",     # Methane, CH₄
    "124-38-9": "#ff7f0e",    # Carbon Dioxide, CO₂
    "7732-18-5": "#2ca02c",   # Water Vapor, H₂O
    "630-08-0": "#d62728",    # Carbon Monoxide, CO
    "10024-97-2": "#9467bd",  # Nitrous Oxide, N₂O
    "7664-41-7": "#8c564b",   # Ammonia, NH₃
    "7446-09-5": "#e377c2",   # Sulfur Dioxide, SO₂
    "7782-44-7": "#7f7f7f",   # Oxygen, O₂
    "75-07-0": "#bcbd22",     # Acetaldehyde, C₂H₄O
    "64-17-5": "#17becf",     # Ethanol, C₂H₆O
    "67-56-1": "#a05d56",     # Methanol, CH₄O
}

def get_gas_info(cas):
    return CAS_DETAILS.get(cas, None)  # returns (name, formula) or None

def get_gas_name(cas):
    name, _ = CAS_DETAILS.get(cas, (None, None))
    return name if name else "Unknown Gas"

def get_gas_formula(cas):
    _, formula = CAS_DETAILS.get(cas, (None, None))
    return formula if formula else "Unknown Formula"

def get_color_for_cas(cas):
    return CAS_COLORS.get(cas, "#999")

def get_cas_details(cas: str) -> dict:
    name, formula = CAS_DETAILS.get(cas, ("", ""))
    label = f"{name} ({formula}, {cas})" if name and formula else cas
    color = get_color_for_cas(cas)
    return {
        "cas": cas,
        "name": name,
        "formula": formula,
        "label": label,
        "color": color
    }