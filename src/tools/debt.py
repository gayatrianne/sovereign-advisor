"""
Module:      src/tools/debt.py
Description: Debt calculation tools for the Sovereign Advisor MCP server.
             Two tools are exposed here:

             1. calculate_debt_cost — computes total interest and months to
                clear a single debt at a fixed monthly payment. Used by the
                Foundry Suitability Engine to rank debts and confirm the
                adviser's debt-priority sequencing.

             2. calculate_transfer_fee_vs_interest — compares the one-off
                balance transfer fee against the interest that would accrue
                on the existing card during the 0% promotional window. Lets
                Foundry confirm whether KB002's balance-transfer recommendation
                is financially justified for the specific client numbers.

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from src.models.schemas import (
    DebtCostInput,
    DebtCostOutput,
    TransferFeeVsInterestInput,
    TransferFeeVsInterestOutput,
)

logger = logging.getLogger(__name__)


# ============================================================
# TOOL 1 - CALCULATE DEBT COST
# ============================================================

def calculate_debt_cost(inp: DebtCostInput) -> DebtCostOutput:
    """
    Amortise a single debt and return the total interest paid
    and months required to clear it.

    The monthly rate is derived from the APR using the standard
    UK convention: monthly_rate = (1 + APR/100)^(1/12) - 1
    This is more accurate than the simplified APR/12 division
    used by some tools, especially at higher APR values (22%+
    credit card rates where the difference matters).

    Returns an error-state output if the monthly payment does
    not cover the first month's interest — the debt would grow
    forever, which the Foundry agent needs to flag to the adviser.
    """
    logger.debug("calculate_debt_cost called: balance=%.2f, APR=%.2f, payment=%.2f",
                 inp.balance_gbp, inp.annual_apr, inp.monthly_payment_gbp)

    # --------------------------------------------------------
    # Derive the true monthly rate from the annual APR
    # --------------------------------------------------------
    monthly_rate:          float = (1 + inp.annual_apr / 100) ** (1 / 12) - 1
    effective_monthly_pct: float = round(monthly_rate * 100, 4)

    # --------------------------------------------------------
    # Guard: if the payment does not cover the first month's
    # interest, the balance grows indefinitely. Return a sentinel
    # value so Foundry can identify and escalate this case.
    # --------------------------------------------------------
    first_month_interest: float = inp.balance_gbp * monthly_rate
    if inp.monthly_payment_gbp <= first_month_interest:
        logger.warning("Monthly payment %.2f does not cover first month interest %.2f",
                       inp.monthly_payment_gbp, first_month_interest)
        return DebtCostOutput(
            months_to_clear        = 9999,   # Sentinel: will never clear
            total_interest_gbp     = -1.0,
            total_repaid_gbp       = -1.0,
            effective_monthly_rate = effective_monthly_pct,
        )

    # --------------------------------------------------------
    # Standard amortisation loop
    # Runs month by month until the balance is cleared.
    # Capped at 600 months (50 years) to prevent infinite loops
    # on edge cases where a near-zero payment barely beats
    # the interest charge.
    # --------------------------------------------------------
    balance:        float = inp.balance_gbp
    total_interest: float = 0.0
    months:         int   = 0
    MAX_MONTHS:     int   = 600

    while balance > 0 and months < MAX_MONTHS:
        interest_this_month  = balance * monthly_rate
        principal_this_month = inp.monthly_payment_gbp - interest_this_month

        total_interest += interest_this_month
        balance        -= principal_this_month
        months         += 1

        # Final partial month: avoid a tiny negative balance
        if balance < 0:
            balance = 0

    total_repaid = inp.balance_gbp + total_interest

    return DebtCostOutput(
        months_to_clear        = months,
        total_interest_gbp     = round(total_interest, 2),
        total_repaid_gbp       = round(total_repaid, 2),
        effective_monthly_rate = effective_monthly_pct,
    )


# ============================================================
# TOOL 2 - CALCULATE TRANSFER FEE VS INTEREST
# ============================================================

def calculate_transfer_fee_vs_interest(inp: TransferFeeVsInterestInput) -> TransferFeeVsInterestOutput:
    """
    Compare the one-off balance transfer fee against the
    interest that would accrue on the existing card if the
    balance is left in place for the promotional window.

    Decision rule (from KB002):
      - If saving_gbp > 0  : transfer is worthwhile
      - If saving_gbp <= 0 : transfer fee outweighs interest saved;
                             do not recommend the switch

    The interest calculation uses true monthly compounding over
    the promotional period — a conservative estimate since the
    balance would typically reduce as the client makes minimum
    payments on the old card.
    """
    logger.debug("calculate_transfer_fee_vs_interest: balance=%.2f, APR=%.2f, fee=%.2f%%, months=%d",
                 inp.balance_gbp, inp.current_apr, inp.transfer_fee_pct, inp.promo_months)

    # --------------------------------------------------------
    # One-off cost of doing the transfer
    # --------------------------------------------------------
    transfer_fee_gbp: float = round(inp.balance_gbp * inp.transfer_fee_pct / 100, 2)

    # --------------------------------------------------------
    # Interest that would accrue on the existing card over the
    # promotional window if the client does NOT transfer.
    # Using true monthly rate compounding for accuracy.
    # --------------------------------------------------------
    monthly_rate:         float = (1 + inp.current_apr / 100) ** (1 / 12) - 1
    balance_after_promo:  float = inp.balance_gbp * (1 + monthly_rate) ** inp.promo_months
    interest_if_stay_gbp: float = round(balance_after_promo - inp.balance_gbp, 2)

    # --------------------------------------------------------
    # Net saving from transferring (positive = transfer wins)
    # --------------------------------------------------------
    saving_gbp: float = round(interest_if_stay_gbp - transfer_fee_gbp, 2)

    if saving_gbp > 0:
        recommendation = (
            f"Balance transfer is recommended. "
            f"Paying the {inp.transfer_fee_pct}% transfer fee (£{transfer_fee_gbp:.2f}) "
            f"saves £{saving_gbp:.2f} compared with leaving the balance at {inp.current_apr}% APR "
            f"for {inp.promo_months} months."
        )
    else:
        recommendation = (
            f"Balance transfer is NOT recommended. "
            f"The {inp.transfer_fee_pct}% transfer fee (£{transfer_fee_gbp:.2f}) "
            f"exceeds the interest saving of £{interest_if_stay_gbp:.2f} "
            f"over the {inp.promo_months}-month promotional period."
        )

    return TransferFeeVsInterestOutput(
        transfer_fee_gbp     = transfer_fee_gbp,
        interest_if_stay_gbp = interest_if_stay_gbp,
        saving_gbp           = saving_gbp,
        recommendation       = recommendation,
    )