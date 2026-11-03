"""Catálogo e Regras Metrológicas de Balanças (Toledo Prix, Industriais e Analíticas).

Regra de Tolerância em Oficina (Inmetro / Toledo):
- Até 2 incrementos (divisões 'e') para mais ou para menos (±2e) -> DENTRO DA TOLERÂNCIA.
- 3 ou mais incrementos (> 2e) -> FORA DA TOLERÂNCIA (DIFERENÇA DE PESO - requer calibração).
"""

import json
import re
import unicodedata

DEFAULT_SCALE_MODELS = [
    # --- LINHA TOLEDO PRIX COMERCIAL ---
    {
        "brand": "Toledo",
        "model_name": "Prix 5 Plus",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 5 Plus (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 4 Uno",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 4 Uno (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 4 Due",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 4 Due (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 4 Steel",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 4 Steel (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 4 Flex",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 4 Flex (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 3 Plus",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Computadora Toledo Prix 3 Plus (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 3 Fit",
        "capacity_str": "15kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Computadora Toledo Prix 3 Fit 15kg (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 3 Fit",
        "capacity_str": "30kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Computadora Toledo Prix 3 Fit 30kg (0-6kg: 2g | 6-15kg: 5g | 15-30kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 6 Touch",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Touch Screen Toledo Prix 6 Touch (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 6 Flex",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Etiquetadora Toledo Prix 6 Flex (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "Prix 7 Touch",
        "capacity_str": "32kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança com Vídeo Toledo Prix 7 Touch (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2090 Baby",
        "capacity_str": "15kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Pediátrica Toledo 2090 Baby (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2090 PP",
        "capacity_str": "15kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Toledo 2090 PP 15kg (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2090 PP",
        "capacity_str": "30kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_30kg", "ranges": [[15.0, 0.005], [30.0, 0.010]]},
        "description": "Balança Toledo 2090 PP 30kg (0-15kg: 5g | 15-30kg: 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "3400",
        "capacity_str": "15kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Toledo 3400 / 3400 Jr (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Toledo",
        "model_name": "9094",
        "capacity_str": "15kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Toledo 9094 15kg (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Toledo",
        "model_name": "9094",
        "capacity_str": "30kg",
        "equipment_type": "Balança Toledo Prix",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_30kg", "ranges": [[15.0, 0.005], [30.0, 0.010]]},
        "description": "Balança Toledo 9094 30kg (0-15kg: 5g | 15-30kg: 10g)"
    },

    # --- LINHA TOLEDO INDUSTRIAL / PLATAFORMA ---
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "50kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.010},
        "description": "Balança Industrial Toledo 2180 Plataforma 50kg (div 10g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "100kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.020},
        "description": "Balança Industrial Toledo 2180 Plataforma 100kg (div 20g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "150kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.050},
        "description": "Balança Industrial Toledo 2180 Plataforma 150kg (div 50g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "300kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.100},
        "description": "Balança Industrial Toledo 2180 Plataforma 300kg (div 100g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "500kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.100},
        "description": "Balança Industrial Toledo 2180 Plataforma 500kg (div 100g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "1000kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.200},
        "description": "Balança Industrial Toledo 2180 Plataforma 1000kg (div 200g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "1500kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.500},
        "description": "Balança Industrial Toledo 2180 Plataforma 1500kg (div 500g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "2000kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 0.500},
        "description": "Balança Industrial Toledo 2180 Plataforma 2000kg (div 500g)"
    },
    {
        "brand": "Toledo",
        "model_name": "2180 Plataforma",
        "capacity_str": "3000kg",
        "equipment_type": "Balança Industrial / Plataforma",
        "unit": "kg",
        "division_rule": {"type": "fixa", "division": 1.000},
        "description": "Balança Industrial Toledo 2180 Plataforma 3000kg (div 1kg)"
    },

    # --- BALANÇAS ANALÍTICAS E DE PRECISÃO (EM GRAMAS) ---
    {
        "brand": "Marte",
        "model_name": "Marte 510g (AL500 / AD500)",
        "capacity_str": "510g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.01},
        "description": "Balança Semianalítica Marte 510g (divisão 0,01g / tolerância ±0,02g)"
    },
    {
        "brand": "Marte",
        "model_name": "Marte 510g Precisão (0,001g)",
        "capacity_str": "510g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.001},
        "description": "Balança Precisão Marte 510g (divisão 0,001g / 1mg / tolerância ±0,002g)"
    },
    {
        "brand": "Marte",
        "model_name": "Marte 210g Analítica",
        "capacity_str": "210g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.0001},
        "description": "Balança Analítica Marte 210g (divisão 0,0001g / 0,1mg - 4 casas)"
    },
    {
        "brand": "Marte",
        "model_name": "Marte 2100g",
        "capacity_str": "2100g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.01},
        "description": "Balança Marte 2100g (divisão 0,01g / tolerância ±0,02g)"
    },
    {
        "brand": "Marte",
        "model_name": "Marte 3100g",
        "capacity_str": "3100g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.01},
        "description": "Balança Marte 3100g (divisão 0,01g / tolerância ±0,02g)"
    },
    {
        "brand": "Marte",
        "model_name": "Marte 5100g",
        "capacity_str": "5100g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.1},
        "description": "Balança Marte 5100g (divisão 0,1g / tolerância ±0,2g)"
    },
    {
        "brand": "Shimadzu",
        "model_name": "Shimadzu ATY224 / AUY220",
        "capacity_str": "220g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.0001},
        "description": "Balança Analítica Shimadzu 220g (divisão 0,0001g / 0,1mg)"
    },
    {
        "brand": "Bel",
        "model_name": "Bel Engineering 220g",
        "capacity_str": "220g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.0001},
        "description": "Balança Analítica Bel 220g (divisão 0,0001g / 0,1mg)"
    },
    {
        "brand": "Ohaus",
        "model_name": "Ohaus Scout 600g",
        "capacity_str": "600g",
        "equipment_type": "Balança Analítica / Precisão",
        "unit": "g",
        "division_rule": {"type": "fixa", "division": 0.01},
        "description": "Balança Precisão Ohaus Scout 600g (divisão 0,01g)"
    },

    # --- OUTRAS MARCAS COMERCIAIS FREQUENTES (URANO / FILIZOLA / ELGIN) ---
    {
        "brand": "Urano",
        "model_name": "Urano Pop-S / Pop Light",
        "capacity_str": "32kg",
        "equipment_type": "Balança Comercial",
        "unit": "kg",
        "division_rule": {"type": "tripla_faixa_32kg", "ranges": [[6.0, 0.002], [15.0, 0.005], [32.0, 0.010]]},
        "description": "Balança Urano Pop-S 32kg (0-6kg: 2g | 6-15kg: 5g | 15-32kg: 10g)"
    },
    {
        "brand": "Urano",
        "model_name": "Urano Pop-S 15kg",
        "capacity_str": "15kg",
        "equipment_type": "Balança Comercial",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Urano Pop-S 15kg (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Filizola",
        "model_name": "Filizola Platina",
        "capacity_str": "15kg",
        "equipment_type": "Balança Comercial",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_15kg", "ranges": [[6.0, 0.002], [15.0, 0.005]]},
        "description": "Balança Filizola Platina 15kg (0-6kg: 2g | 6-15kg: 5g)"
    },
    {
        "brand": "Filizola",
        "model_name": "Filizola Platina / CS",
        "capacity_str": "30kg",
        "equipment_type": "Balança Comercial",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_30kg", "ranges": [[15.0, 0.005], [30.0, 0.010]]},
        "description": "Balança Filizola Platina 30kg (0-15kg: 5g | 15-30kg: 10g)"
    },
    {
        "brand": "Elgin",
        "model_name": "Elgin DP-30",
        "capacity_str": "30kg",
        "equipment_type": "Balança Comercial",
        "unit": "kg",
        "division_rule": {"type": "dupla_faixa_30kg", "ranges": [[15.0, 0.005], [30.0, 0.010]]},
        "description": "Balança Elgin DP-30 30kg (0-15kg: 5g | 15-30kg: 10g)"
    },
]


def _normalize(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def search_scale_models(query="", limit=20):
    """Retorna modelos de balanças correspondentes à busca da Priscila."""
    q = _normalize(query)
    results = []
    terms = [t for t in q.split() if t] if q else []

    for item in DEFAULT_SCALE_MODELS:
        haystack = _normalize(f"{item['brand']} {item['model_name']} {item['capacity_str']} {item['equipment_type']} {item['description']}")
        if not terms or all(t in haystack for t in terms):
            results.append({
                "brand": item["brand"],
                "model_name": item["model_name"],
                "capacity_str": item["capacity_str"],
                "display_name": f"{item['brand']} {item['model_name']} - {item['capacity_str']}",
                "equipment_type": item["equipment_type"],
                "unit": item["unit"],
                "description": item["description"],
                "division_rule": item["division_rule"],
            })
            if len(results) >= limit:
                break
    return results


def find_matching_scale_model(model_str):
    """Encontra o modelo de balança mais compatível com o texto digitado na O.S."""
    if not model_str:
        return None
    q = _normalize(model_str)
    for item in DEFAULT_SCALE_MODELS:
        model_norm = _normalize(item["model_name"])
        brand_norm = _normalize(item["brand"])
        if model_norm in q or (brand_norm in q and _normalize(item["capacity_str"]) in q):
            return item
    # Se mencionar prix 5 / prix 4 / prix 3
    if "prix 5" in q or "5 plus" in q:
        return DEFAULT_SCALE_MODELS[0]
    if "prix 4" in q or "uno" in q:
        return DEFAULT_SCALE_MODELS[1]
    if "prix 3" in q:
        return DEFAULT_SCALE_MODELS[5]
    if "prix 6" in q:
        return DEFAULT_SCALE_MODELS[8]
    if "marte" in q:
        if "210" in q:
            return DEFAULT_SCALE_MODELS[18]
        return DEFAULT_SCALE_MODELS[16]
    return None


def get_scale_division(nominal_weight, unit="kg", model_str=None):
    """
    Calcula a divisão 'e' (incremento) exata da balança na carga informada.
    """
    scale = find_matching_scale_model(model_str)
    u = (unit or (scale["unit"] if scale else "kg")).lower().strip()

    if u == "g":
        if scale and scale.get("division_rule"):
            rule = scale["division_rule"]
            if rule.get("type") == "fixa":
                return float(rule.get("division", 0.01)), "g"
        # Heurística para balança analítica/gramas
        if model_str and ("210" in model_str or "analit" in _normalize(model_str) or "0,0001" in model_str or "0.0001" in model_str):
            return 0.0001, "g"
        if model_str and ("0,001" in model_str or "0.001" in model_str or "1mg" in model_str):
            return 0.001, "g"
        return 0.01, "g"  # Padrão Marte 510g (divisão 0,01g)

    # u == "kg"
    load = float(nominal_weight)
    if scale and scale.get("division_rule"):
        rule = scale["division_rule"]
        if rule.get("type") == "fixa":
            return float(rule.get("division", 0.010)), "kg"
        ranges = rule.get("ranges", [])
        for max_load, div in ranges:
            if load <= max_load:
                return float(div), "kg"
        if ranges:
            return float(ranges[-1][1]), "kg"

    # Heurística padrão Toledo Prix Comercial (30kg/32kg Tripla Faixa):
    # 0 a 6kg: 2g (0.002kg)
    # 6 a 15kg: 5g (0.005kg)
    # 15 a 32kg: 10g (0.010kg)
    if load <= 6.0001:
        return 0.002, "kg"  # 2g
    elif load <= 15.0001:
        return 0.005, "kg"  # 5g
    elif load <= 32.0001:
        return 0.010, "kg"  # 10g
    elif load <= 100.0001:
        return 0.020, "kg"  # 20g
    elif load <= 300.0001:
        return 0.100, "kg"  # 100g
    else:
        return 0.200, "kg"  # 200g


def evaluate_weight_test(key_str, raw_measured, model_str=None, unit="kg"):
    """
    Avalia um teste de peso inicial ou final com a regra oficial dos 2 incrementos:
    - Até 2 incrementos (±2e): DENTRO DA TOLERÂNCIA
    - 3 ou mais incrementos (> 2e): FORA DA TOLERÂNCIA (DIFERENÇA DE PESO)
    """
    if raw_measured is None:
        return None
    str_val = str(raw_measured).strip()
    if not str_val:
        return None

    # Extrai o peso nominal da chave (ex: "1kg", "40kg", "1g", "500g")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(kg|g)$", str(key_str).strip(), re.IGNORECASE)
    if not m:
        return None
    nominal = float(m.group(1))
    key_unit = m.group(2).lower()

    # Limpa número medido
    clean_num = str_val.replace(",", ".").replace(" ", "")
    clean_num = re.sub(r"[^\d.-]", "", clean_num)
    try:
        measured = float(clean_num)
    except ValueError:
        return None

    active_unit = key_unit or unit or "kg"
    division, div_unit = get_scale_division(nominal, unit=active_unit, model_str=model_str)
    max_tolerance = 2 * division  # Exatamente 2 incrementos!

    diff = measured - nominal
    abs_diff = abs(diff)

    # Tolerância com pequena folga para arredondamento float (1e-6)
    is_outside_tolerance = (abs_diff - max_tolerance) > 1e-6

    # Formatações amigáveis
    if active_unit == "kg":
        # Converte para gramas para visualização clara do técnico e da Priscila
        diff_g = diff * 1000.0
        tol_g = max_tolerance * 1000.0
        div_g = division * 1000.0
        sign = "+" if diff > 0 else ""
        diff_str = f"{sign}{diff_g:.1f}g".replace(".0g", "g")
        tol_str = f"±{tol_g:.0f}g"
        div_str = f"e={div_g:.0f}g"
        display_measured = f"{str_val}kg" if not re.search(r"kg$", str_val, re.IGNORECASE) else str_val
    else:
        sign = "+" if diff > 0 else "-" if diff < 0 else ""
        diff_val_str = f"{abs(diff):.4f}".rstrip("0").rstrip(".") or "0"
        diff_str = f"{sign}{diff_val_str}g"
        tol_val_str = f"{max_tolerance:.4f}".rstrip("0").rstrip(".")
        tol_str = f"±{tol_val_str}g"
        div_val_str = f"{division:.4f}".rstrip("0").rstrip(".")
        div_str = f"e={div_val_str}g"
        display_measured = f"{str_val}g" if not re.search(r"g$", str_val, re.IGNORECASE) else str_val

    if is_outside_tolerance:
        status = "FORA_DA_ESPECIFICACAO"
        message = f"{key_str} - {display_measured} DIFERENÇA DE PESO (Erro {diff_str}, tolerância {tol_str} • {div_str})"
    else:
        status = "DENTRO_DA_TOLERANCIA"
        if abs_diff <= 1e-6:
            message = f"{key_str} - {display_measured} OK (Sem erro • {div_str})"
        else:
            message = f"{key_str} - {display_measured} OK (Dentro da tolerância: {diff_str} ≤ {tol_str} • {div_str})"

    return {
        "key": key_str,
        "nominal": nominal,
        "measured": measured,
        "diff": diff,
        "abs_diff": abs_diff,
        "division": division,
        "max_tolerance": max_tolerance,
        "is_outside_tolerance": is_outside_tolerance,
        "unit": active_unit,
        "diff_str": diff_str,
        "tol_str": tol_str,
        "div_str": div_str,
        "display_measured": display_measured,
        "status": status,
        "message": message,
    }
