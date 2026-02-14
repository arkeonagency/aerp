def calculate_metrics(l, w, h, pcs, gross_weight, rate_usd, ex_rate):
    """
    Standard Air Cargo Calculations
    Formula: (L * W * H * Pcs) / 6000
    """
    vol_weight = (l * w * h * pcs) / 6000
    chargeable_weight = max(gross_weight, vol_weight)
    
    total_usd = chargeable_weight * rate_usd
    total_etb = total_usd * ex_rate
    
    return {
        "vol_weight": round(vol_weight, 2),
        "chargeable_weight": round(chargeable_weight, 2),
        "total_usd": round(total_usd, 2),
        "total_etb": round(total_etb, 2)
    }