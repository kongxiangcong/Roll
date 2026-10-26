"""Model-internal conditions, distinct from market causal identification."""
from .calculator import perpetuity
from .valuation_reference.fundamental_valuation import number


def compare_perpetuity(old_cashflow, old_rate, new_cashflow, new_rate, old_price, new_price):
    old_value, new_value = perpetuity(old_cashflow, old_rate), perpetuity(new_cashflow, new_rate)
    def conditions(price):
        price = number(price, 'price', 0, True)
        return dict(fixed_old_rate_required_cashflow=price * old_rate,
                    fixed_old_cashflow_required_rate=old_cashflow / price)
    return dict(old_value=old_value, new_value=new_value,
                value_change_fraction=(new_value-old_value)/old_value,
                operating_change=old_cashflow != new_cashflow,
                old_price_conditions=conditions(old_price), new_price_conditions=conditions(new_price),
                market_cause_identified=False)
