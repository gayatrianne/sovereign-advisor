"""
Module:      src/tools/savings.py
Description: Savings calculation tools for the Sovereign Advisor MCP server.
             Two tools are exposed here:

             1. calculate_savings_gap — projects how many months it takes
                to reach a savings goal at the client's monthly contribution
                rate, accounting for compounding interest on the growing
                balance. Foundry uses this to confirm product suitability
                and to identify whether the client needs to increase
                contributions.

             2. calculate_emergency_fund_target — quantifies the emergency
                reserve shortfall relative to the FCA Consumer Duty standard
                of 3 to 6 months of essential expenses. This check MUST be
                run before any long-term savings or investment recommendation
                per the debt priority framework in all KB files.

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from src.models.schemas import (
    SavingsGapInput,
    SavingsGapOutput,
    EmergencyFundInput,
    EmergencyFundOutput,
)

logger = logging.getLogger(__name__)


# ============================================================
# TOOL 1 - CALCULATE SAVINGS GAP
# ============================================================

def calculate_savings_gap(inp: SavingsGapInput) -> SavingsGapOutput:
    """
    Project how many months it takes to reach a savings goal
    given a starting balance, monthly contributions, and a
    compound interest rate (AER).

    The interest is applied monthly using the true monthly
    rate derived from the AER:
        monthly_rate = (1 + AER/100)^(1/12) - 1

    This matches how UK savings providers compound interest
    on instant-access and regular saver accounts.

    Cap: 600 months (50 years). If the goal cannot be reached
    within this window, months_to_goal is returned as 9999.
    """
    logger.debug("calculate_savings_gap: goal=%.2f, balance=%.2f, monthly=%.2f, AER=%.2f%%",
                 inp.goal_gbp, inp.current_balance_gbp,
                 inp.monthly_contribution_gbp, inp.annual_interest_rate)

    # --------------------------------------------------------
    # Derive the true monthly compounding rate from the AER
    # --------------------------------------------------------
    monthly_rate: float = (1 + inp.annual_interest_rate / 100) ** (1 / 12) - 1

    balance:        float = inp.current_balance_gbp
    total_interest: float = 0.0
    months:         int   = 0
    MAX_MONTHS:     int   = 600

    # --------------------------------------------------------
    # Month-by-month simulation:
    # 1. Add the month's contribution
    # 2. Apply interest on the new balance
    # --------------------------------------------------------
    while balance < inp.goal_gbp and months < MAX_MONTHS:
        balance         += inp.monthly_contribution_gbp
        interest_earned  = balance * monthly_rate
        balance         += interest_earned
        total_interest  += interest_earned
        months          += 1

    if months >= MAX_MONTHS and balance < inp.goal_gbp:
        logger.warning("Goal of £%.2f not reached within %d months", inp.goal_gbp, MAX_MONTHS)
        return SavingsGapOutput(
            months_to_goal            = 9999,
            total_interest_earned_gbp = round(total_interest, 2),
            projected_balance_gbp     = round(balance, 2),
        )

    return SavingsGapOutput(
        months_to_goal            = months,
        total_interest_earned_gbp = round(total_interest, 2),
        projected_balance_gbp     = round(balance, 2),
    )


# ============================================================
# TOOL 2 - CALCULATE EMERGENCY FUND TARGET
# ============================================================

def calculate_emergency_fund_target(inp: EmergencyFundInput) -> EmergencyFundOutput:
    """
    Calculate the emergency fund target and shortfall for a client.

    FCA Consumer Duty (PS22/9) and the debt priority framework
    applied across all Sovereign Advisor knowledge base files
    require that an adequate liquid emergency reserve is in
    place before recommending any investment or long-term
    savings product. Typically 3 months for dual-income
    households and 6 months for single earners.

    The shortfall_gbp output tells Foundry exactly how much
    the client needs to accumulate in easy-access savings
    before it should recommend ISAs, JISAs, or pension top-ups.
    A shortfall_gbp of 0.0 means the check is passed and
    longer-term products can be considered.
    """
    logger.debug("calculate_emergency_fund_target: expenses=%.2f, months=%d, current=%.2f",
                 inp.monthly_essential_expenses_gbp, inp.months_cover,
                 inp.current_easy_access_gbp)

    # --------------------------------------------------------
    # Target = months_cover x monthly essential expenses
    # --------------------------------------------------------
    target_gbp: float = inp.monthly_essential_expenses_gbp * inp.months_cover

    # --------------------------------------------------------
    # Shortfall: how much more the client needs to save.
    # Clamped to 0 — no negative shortfall if already over target.
    # --------------------------------------------------------
    shortfall_gbp: float = max(0.0, target_gbp - inp.current_easy_access_gbp)

    # --------------------------------------------------------
    # Express current holdings as months of cover so Foundry
    # can surface this number directly to the adviser.
    # --------------------------------------------------------
    if inp.monthly_essential_expenses_gbp > 0:
        months_of_cover_held: float = round(
            inp.current_easy_access_gbp / inp.monthly_essential_expenses_gbp, 2
        )
    else:
        months_of_cover_held = 0.0

    return EmergencyFundOutput(
        target_gbp           = round(target_gbp, 2),
        shortfall_gbp        = round(shortfall_gbp, 2),
        months_of_cover_held = months_of_cover_held,
    )