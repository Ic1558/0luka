import json
import sys

def format_boq_row(item_data):
    """
    Formats a raw work item into a DDC-compliant BOQ row.
    """
    total_direct = (
        item_data.get('total_value_material', 0) +
        item_data.get('total_value_labor', 0) +
        item_data.get('total_value_machinery', 0)
    )
    
    return {
        "code": item_data.get('rate_code'),
        "description": item_data.get('rate_original_name'),
        "unit": item_data.get('rate_unit'),
        "material": item_data.get('total_value_material', 0),
        "labor": item_data.get('total_value_labor', 0),
        "total_direct": total_direct
    }

def apply_markups(direct_cost, contingency_pct=5, profit_pct=25):
    """
    Applies contingency and profit markups.
    """
    with_contingency = direct_cost * (1 + (contingency_pct / 100))
    total_submit = with_contingency * (1 + (profit_pct / 100))
    return {
        "direct": direct_cost,
        "with_contingency": with_contingency,
        "total_submit": total_submit,
        "margin": total_submit - direct_cost
    }

if __name__ == "__main__":
    # Simple CLI interface for the agent to use
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "calc":
            cost = float(sys.argv[2])
            print(json.dumps(apply_markups(cost)))
