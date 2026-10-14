"""
Module:      src/tools/investments.py
Description: Child and education savings calculation tool for the Sovereign
             Advisor MCP server. One tool is exposed here:

             calculate_jisa_projection — projects the value of a Junior
             Stocks and Shares ISA at the child's 18th birthday, assuming
             regular monthly contributions compounded at the adviser's
             assumed annual equity growth rate.

             The KB006 adviser note illustrates this projection at £150/month
             from birth at 7% average annual return reaching approximately
             £58,000 at age 18. This tool runs that exact calculation with
             the client's actual figures so Foundry can include a personalised
             illustration in its suitability recommendation.

             The FCA Consumer Investment Strategy requires that growth
             projections use a consistent set of assumptions. 7% is used
             as the central estimate for a global equity tracker, consistent
             with Vanguard's long-run average return data and the projection
             rates used by major UK platforms for Stocks and Shares ISA
             illustrations.

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from src.models.schemas import (
    JISAProjectionInput,
    JISAProjectionOutput,
)

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
JISA_ANNUAL_ALLOWANCE_GBP: float = 9000.0   # 2026/27 tax year limit
CHILD_LOCK_IN_AGE:         int   = 18        # JISA funds locked until this age


# ============================================================
# TOOL - CALCULATE JISA PROJECTION
# ============================================================

def calculate_jisa_projection(inp: JISAProjectionInput) -> JISAProjectionOutput:
    """
    Project the balance of a Junior Stocks and Shares ISA at
    the child's 18th birthday.

    Growth model: month-by-month compounding.
        balance = (balance + monthly_contribution) x (1 + monthly_rate)
    where monthly_rate = (1 + annual_rate)^(1/12) - 1

    This matches how a drip-fed investment into an equity tracker
    actually accumulates — each monthly contribution benefits from
    the remaining compounding period.

    Outputs include total contributions and total growth separately
    so the Foundry agent can present both numbers to the adviser,
    making the power of compounding tangible for the client
    conversation (total growth typically exceeds total contributions
    for holding periods over 10 years at 7%+).

    Note: the tool does not enforce the £9,000 annual JISA limit
    so Foundry can model any contribution level and then flag a
    limit breach if the input exceeds it. The kb_rule_applied field
    in the child agent's JSON output will already reference KB006
    Rule 1 and note the allowance.
    """
    logger.debug("calculate_jisa_projection: child_age=%d, monthly=%.2f, balance=%.2f, growth=%.2f%%",
                 inp.child_age_years, inp.monthly_contribution_gbp,
                 inp.current_balance_gbp, inp.assumed_annual_growth)

    # --------------------------------------------------------
    # Years remaining until the child's 18th birthday
    # --------------------------------------------------------
    years_to_18: int = max(0, CHILD_LOCK_IN_AGE - inp.child_age_years)

    if years_to_18 == 0:
        # Child is already 18 — the JISA has converted to an adult ISA.
        # Return the current balance with zero projected growth.
        logger.info("Child is already 18 - JISA has converted to adult ISA.")
        return JISAProjectionOutput(
            years_to_18                 = 0,
            projected_balance_gbp       = round(inp.current_balance_gbp, 2),
            total_contributions_gbp     = 0.0,
            total_growth_gbp            = 0.0,
            effective_annual_return_pct = inp.assumed_annual_growth,
        )

    # --------------------------------------------------------
    # Monthly compounding rate
    # --------------------------------------------------------
    monthly_rate: float = (1 + inp.assumed_annual_growth / 100) ** (1 / 12) - 1
    n_months:     int   = years_to_18 * 12

    # --------------------------------------------------------
    # Month-by-month accumulation.
    # Contribution is made at the start of each month, then
    # the full balance compounds for that month — matches the
    # illustration convention used by Vanguard and HL.
    # --------------------------------------------------------
    balance:             float = inp.current_balance_gbp
    total_contributions: float = 0.0

    for _ in range(n_months):
        balance             += inp.monthly_contribution_gbp
        total_contributions += inp.monthly_contribution_gbp
        balance             += balance * monthly_rate

    # --------------------------------------------------------
    # Total growth = final balance minus starting balance
    # minus all contributions made during the period
    # --------------------------------------------------------
    total_growth: float = balance - inp.current_balance_gbp - total_contributions

    return JISAProjectionOutput(
        years_to_18                 = years_to_18,
        projected_balance_gbp       = round(balance, 2),
        total_contributions_gbp     = round(total_contributions, 2),
        total_growth_gbp            = round(total_growth, 2),
        effective_annual_return_pct = inp.assumed_annual_growth,
    )