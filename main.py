"""
Module:      main.py
Description: Entry point for the Sovereign Advisor MCP (Model Context Protocol)
             server. Registers all financial calculation tools so that Azure AI
             Foundry — or any other MCP-compliant client — can discover and
             call them via the standard JSON-RPC tool protocol.

             Transport: SSE (Server-Sent Events) for HTTP-based access.
             Expose locally via ngrok for Foundry to reach without deploying
             to Azure Functions.

             Running locally:
               python main.py
             Then in a second terminal:
               ngrok http 8000

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import logging
from typing import Optional

# Set host/port and allowed hosts BEFORE importing FastMCP
# FastMCP reads these env vars during initialisation.
# MCP_ALLOWED_HOSTS = "*" is required when ngrok rewrites the
# Host header — without it the SSE endpoint returns 400.
os.environ["FASTMCP_HOST"]      = "0.0.0.0"
os.environ["FASTMCP_PORT"]      = "8000"
os.environ["MCP_ALLOWED_HOSTS"] = "*"

from mcp.server.fastmcp import FastMCP

# Internal config — all env vars read once from .env
from src.config import MCP_SERVER_NAME, MCP_SERVER_VERSION, LOG_LEVEL

# Tool function imports — pure Python, no MCP dependency
from src.tools.debt        import calculate_debt_cost, calculate_transfer_fee_vs_interest
from src.tools.savings     import calculate_savings_gap, calculate_emergency_fund_target
from src.tools.pension     import calculate_pension_gap, calculate_drawdown_sustainability
from src.tools.mortgage    import calculate_mortgage_affordability
from src.tools.investments import calculate_jisa_projection

# Pydantic input schemas — used internally to validate inputs
from src.models.schemas import (
    DebtCostInput,
    TransferFeeVsInterestInput,
    SavingsGapInput,
    EmergencyFundInput,
    PensionGapInput,
    DrawdownSustainabilityInput,
    MortgageAffordabilityInput,
    JISAProjectionInput,
)

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level  = LOG_LEVEL,
    format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("Starting %s v%s", MCP_SERVER_NAME, MCP_SERVER_VERSION)

# ============================================================
# MCP SERVER INITIALISATION
# ============================================================
mcp = FastMCP(
    name = MCP_SERVER_NAME,
)

# ============================================================
# TOOL REGISTRATIONS — DEBT
# ============================================================

@mcp.tool()
def debt_cost(
    balance_gbp: float,
    annual_apr: float,
    monthly_payment_gbp: float,
) -> dict:
    """
    Calculate total interest, months to clear, and effective
    monthly rate for a single debt.

    Use this to compare the cost of two debts and confirm
    the adviser's debt-priority sequencing (highest interest
    first per the Consumer Duty debt framework).

    Args:
        balance_gbp: Current outstanding balance in GBP
        annual_apr: Annual interest rate as a percentage (e.g. 22.9 for 22.9% APR)
        monthly_payment_gbp: Fixed monthly payment amount in GBP
    """
    inp = DebtCostInput(
        balance_gbp=balance_gbp,
        annual_apr=annual_apr,
        monthly_payment_gbp=monthly_payment_gbp,
    )
    return calculate_debt_cost(inp).model_dump()


@mcp.tool()
def transfer_fee_vs_interest(
    balance_gbp: float,
    current_apr: float,
    transfer_fee_pct: float,
    promo_months: int,
) -> dict:
    """
    Compare the one-off balance transfer fee to the interest
    that would accrue on the existing card during the 0%
    promotional window.

    Returns saving_gbp (positive = transfer is worthwhile)
    and a plain-English recommendation string.

    Args:
        balance_gbp: Balance to transfer in GBP
        current_apr: Current card APR as a percentage
        transfer_fee_pct: Balance transfer fee as a percentage (e.g. 3.45)
        promo_months: Length of the 0% promotional period in months
    """
    inp = TransferFeeVsInterestInput(
        balance_gbp=balance_gbp,
        current_apr=current_apr,
        transfer_fee_pct=transfer_fee_pct,
        promo_months=promo_months,
    )
    return calculate_transfer_fee_vs_interest(inp).model_dump()


# ============================================================
# TOOL REGISTRATIONS — SAVINGS
# ============================================================

@mcp.tool()
def savings_gap(
    goal_gbp: float,
    current_balance_gbp: float,
    monthly_contribution_gbp: float,
    annual_interest_rate: float,
) -> dict:
    """
    Project how many months it takes to reach a savings goal
    at the client's monthly contribution rate with compound
    interest applied at the account's AER.

    Use this to confirm a regular saver or easy-access product
    recommendation is appropriate for the client's timeline.

    Args:
        goal_gbp: Target savings amount in GBP
        current_balance_gbp: Existing savings balance in GBP
        monthly_contribution_gbp: Amount added to savings each month
        annual_interest_rate: Gross AER of the savings account as a percentage
    """
    inp = SavingsGapInput(
        goal_gbp=goal_gbp,
        current_balance_gbp=current_balance_gbp,
        monthly_contribution_gbp=monthly_contribution_gbp,
        annual_interest_rate=annual_interest_rate,
    )
    return calculate_savings_gap(inp).model_dump()


@mcp.tool()
def emergency_fund_target(
    monthly_essential_expenses_gbp: float,
    months_cover: int = 3,
    current_easy_access_gbp: float = 0.0,
) -> dict:
    """
    Calculate the client's emergency fund target, their current
    shortfall, and how many months of essential expenses they
    currently hold.

    Must be called BEFORE recommending any long-term savings or
    investment product. A non-zero shortfall_gbp means the
    emergency fund must be prioritised first per Consumer Duty.

    Args:
        monthly_essential_expenses_gbp: Total monthly essential outgoings in GBP
        months_cover: Number of months of expenses to hold as emergency reserve (typically 3 to 6)
        current_easy_access_gbp: Cash already held in instant-access savings accounts
    """
    inp = EmergencyFundInput(
        monthly_essential_expenses_gbp=monthly_essential_expenses_gbp,
        months_cover=months_cover,
        current_easy_access_gbp=current_easy_access_gbp,
    )
    return calculate_emergency_fund_target(inp).model_dump()


# ============================================================
# TOOL REGISTRATIONS — PENSION
# ============================================================

@mcp.tool()
def pension_gap(
    pot_gbp: float,
    years_to_retirement: int,
    target_annual_income_gbp: float,
    monthly_contribution_gbp: float,
    assumed_annual_growth: float = 5.0,
    state_pension_weekly_gbp: float = 241.30,
) -> dict:
    """
    Project the client's pension pot to retirement, model a
    sustainable annual income at 3.5% drawdown rate, add the
    State Pension, and calculate the funding gap against the
    client's target retirement income.

    Returns monthly_extra_needed_gbp — the exact additional
    monthly contribution required to close the gap.

    Args:
        pot_gbp: Total current pension pot value across all schemes in GBP
        years_to_retirement: Number of years until the client's target retirement age
        target_annual_income_gbp: Client's desired gross annual retirement income in GBP
        monthly_contribution_gbp: Total monthly pension contribution (employee + employer combined)
        assumed_annual_growth: Assumed annual investment growth rate as a percentage (default 5.0)
        state_pension_weekly_gbp: Expected weekly State Pension (default = full 2026/27 amount of 241.30)
    """
    inp = PensionGapInput(
        current_pot_gbp=pot_gbp,
        monthly_contribution_gbp=monthly_contribution_gbp,
        years_to_retirement=years_to_retirement,
        target_annual_income_gbp=target_annual_income_gbp,
        assumed_annual_growth=assumed_annual_growth,
        state_pension_weekly_gbp=state_pension_weekly_gbp,
    )
    return calculate_pension_gap(inp).model_dump()


@mcp.tool()
def drawdown_sustainability(
    pot_gbp: float,
    annual_withdrawal_gbp: float,
    assumed_annual_growth: float = 4.0,
    state_pension_weekly_gbp: float = 241.30,
) -> dict:
    """
    Model how long a pension pot will last under flexi-access
    drawdown at the client's desired annual income.

    Returns years_pot_lasts and a sequencing_risk_flag (True
    when withdrawal rate exceeds 4%) requiring COBS 19 adviser
    documentation. State Pension is included in the income model.

    Args:
        pot_gbp: Total pension pot value at retirement in GBP
        annual_withdrawal_gbp: Desired gross annual income from drawdown
        assumed_annual_growth: Conservative assumed annual growth during drawdown (default 4.0)
        state_pension_weekly_gbp: Expected weekly State Pension in GBP (default 241.30)
    """
    inp = DrawdownSustainabilityInput(
        pot_gbp=pot_gbp,
        annual_withdrawal_gbp=annual_withdrawal_gbp,
        assumed_annual_growth=assumed_annual_growth,
        state_pension_weekly_gbp=state_pension_weekly_gbp,
    )
    return calculate_drawdown_sustainability(inp).model_dump()


# ============================================================
# TOOL REGISTRATIONS — MORTGAGE
# ============================================================

@mcp.tool()
def mortgage_affordability(
    gross_annual_income_gbp: float,
    loan_amount_gbp: float,
    property_value_gbp: float,
    current_interest_rate: float,
    monthly_debts_gbp: float = 0.0,
    mortgage_term_years: int = 25,
) -> dict:
    """
    Run the standard UK mortgage affordability stress test
    (FCA MCOB 11.6: initial rate + 3% buffer) and check the
    loan amount against the 4.5x income multiple.

    Returns affordability_flag (PASS / BORDERLINE / FAIL),
    LTV percentage, LTV band, and both standard and
    stress-tested monthly repayment amounts.

    Args:
        gross_annual_income_gbp: Total gross annual income for all applicants combined
        loan_amount_gbp: Requested mortgage loan amount in GBP
        property_value_gbp: Full property purchase price or estimated value in GBP
        current_interest_rate: Initial fixed or tracker rate offered by the lender (%)
        monthly_debts_gbp: Total existing monthly debt commitments in GBP (default 0.0)
        mortgage_term_years: Requested mortgage term in years (default 25)
    """
    inp = MortgageAffordabilityInput(
        gross_annual_income_gbp=gross_annual_income_gbp,
        loan_amount_gbp=loan_amount_gbp,
        property_value_gbp=property_value_gbp,
        current_interest_rate=current_interest_rate,
        monthly_debts_gbp=monthly_debts_gbp,
        mortgage_term_years=mortgage_term_years,
    )
    return calculate_mortgage_affordability(inp).model_dump()


# ============================================================
# TOOL REGISTRATIONS — INVESTMENTS / CHILD SAVINGS
# ============================================================

@mcp.tool()
def jisa_projection(
    child_age_years: int,
    monthly_contribution_gbp: float,
    current_balance_gbp: float = 0.0,
    assumed_annual_growth: float = 7.0,
) -> dict:
    """
    Project the balance of a Junior Stocks and Shares ISA at
    the child's 18th birthday, accounting for regular monthly
    contributions compounded at the assumed annual equity growth
    rate (default 7%).

    Returns projected_balance_gbp, total_contributions_gbp,
    and total_growth_gbp so the adviser can see how much of
    the final pot is investment growth vs. their own savings.

    Args:
        child_age_years: Child's current age in whole years
        monthly_contribution_gbp: Proposed monthly contribution into the Junior ISA in GBP
        current_balance_gbp: Existing Junior ISA balance if one is already open (default 0.0)
        assumed_annual_growth: Assumed annual equity growth rate as a percentage (default 7.0)
    """
    inp = JISAProjectionInput(
        child_age_years=child_age_years,
        monthly_contribution_gbp=monthly_contribution_gbp,
        current_balance_gbp=current_balance_gbp,
        assumed_annual_growth=assumed_annual_growth,
    )
    return calculate_jisa_projection(inp).model_dump()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import uvicorn
    logger.info("Running in SSE mode — tunnel via ngrok on port 8000")
    app = mcp.sse_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)