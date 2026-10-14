"""
Module:      src/tools/mortgage.py
Description: Mortgage affordability calculation tool for the Sovereign
             Advisor MCP server. One tool is exposed here:

             calculate_mortgage_affordability — applies the standard UK
             lender affordability stress test (initial rate + 3% buffer,
             per FCA MCOB 11.6) and checks the requested loan amount
             against the 4.5x income multiple. Returns a clear
             PASS / BORDERLINE / FAIL flag that the Foundry Suitability
             Engine can use to drive its recommendation and adviser
             documentation output.

             LTV is also computed here because it determines the rate
             band and SDLT bracket relevant to the KB003 recommendation.

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from src.models.schemas import (
    MortgageAffordabilityInput,
    MortgageAffordabilityOutput,
)

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
# FCA MCOB 11.6 stress test buffer — lenders must assess
# affordability at the initial rate PLUS 3 percentage points.
STRESS_TEST_BUFFER_PCT:     float = 3.0

# Standard UK income multiple cap. Most lenders will stretch
# to 4.5x for strong credit profiles; a minority to 5x or 5.5x
# for high-income professionals. We use 4.5x as the benchmark.
MAX_INCOME_MULTIPLE:        float = 4.5
BORDERLINE_INCOME_MULTIPLE: float = 4.0  # Flag as BORDERLINE above this

# LTV bands that determine which product tier applies (KB003)
LTV_THRESHOLDS: list[tuple[float, str]] = [
    (60.0,  "60% LTV (best rate band)"),
    (75.0,  "75% LTV (standard rate band)"),
    (85.0,  "85% LTV (higher rate band)"),
    (90.0,  "90% LTV (high LTV - limited product range)"),
    (95.0,  "95% LTV (maximum standard LTV - Help to Buy / specialist only)"),
    (100.0, "Above 95% LTV - not mortgageable on standard terms"),
]


# ============================================================
# TOOL - CALCULATE MORTGAGE AFFORDABILITY
# ============================================================

def calculate_mortgage_affordability(inp: MortgageAffordabilityInput) -> MortgageAffordabilityOutput:
    """
    Run the standard UK mortgage affordability assessment.

    Steps:
    1. Compute LTV and identify the rate band.
    2. Compute the income multiple for the requested loan.
    3. Calculate the standard monthly repayment at the quoted rate.
    4. Calculate the stress-tested monthly repayment at (rate + 3%).
    5. Derive the affordability flag:
         PASS       — income multiple <= 4.0x AND stress payment is
                      less than 40% of gross monthly income
         BORDERLINE — income multiple 4.0x to 4.5x OR stress payment
                      is 40% to 45% of gross monthly income
         FAIL       — income multiple > 4.5x OR stress payment
                      exceeds 45% of gross monthly income

    The Foundry agent uses this flag to determine whether to
    recommend proceeding, refer for specialist underwriting, or
    advise the client to reduce the loan amount or increase their
    deposit before applying.
    """
    logger.debug("calculate_mortgage_affordability: income=%.2f, loan=%.2f, value=%.2f, rate=%.2f%%",
                 inp.gross_annual_income_gbp, inp.loan_amount_gbp,
                 inp.property_value_gbp, inp.current_interest_rate)

    # --------------------------------------------------------
    # 1. Loan-to-Value
    # --------------------------------------------------------
    ltv_pct: float = round((inp.loan_amount_gbp / inp.property_value_gbp) * 100, 2)

    ltv_band: str = "Above 95% LTV - not mortgageable on standard terms"
    for threshold, label in LTV_THRESHOLDS:
        if ltv_pct <= threshold:
            ltv_band = label
            break

    # --------------------------------------------------------
    # 2. Income multiple
    # --------------------------------------------------------
    income_multiple:   float = round(inp.loan_amount_gbp / inp.gross_annual_income_gbp, 2)
    max_loan_at_4_5x:  float = round(inp.gross_annual_income_gbp * MAX_INCOME_MULTIPLE, 2)

    # --------------------------------------------------------
    # 3. Monthly repayment helper (standard capital repayment).
    # Uses the standard mortgage payment formula:
    #   M = P x [r(1+r)^n] / [(1+r)^n - 1]
    # where P = principal, r = monthly rate, n = total months.
    # --------------------------------------------------------
    def monthly_repayment(principal: float, annual_rate_pct: float, term_years: int) -> float:
        monthly_rate = annual_rate_pct / 100 / 12
        n_months     = term_years * 12
        if monthly_rate == 0:
            return principal / n_months
        return principal * (monthly_rate * (1 + monthly_rate) ** n_months) / \
               ((1 + monthly_rate) ** n_months - 1)

    # --------------------------------------------------------
    # 4. Standard and stress-tested monthly payments
    # --------------------------------------------------------
    standard_monthly: float = round(
        monthly_repayment(inp.loan_amount_gbp, inp.current_interest_rate, inp.mortgage_term_years), 2
    )

    stress_rate:    float = inp.current_interest_rate + STRESS_TEST_BUFFER_PCT
    stress_monthly: float = round(
        monthly_repayment(inp.loan_amount_gbp, stress_rate, inp.mortgage_term_years), 2
    )

    # --------------------------------------------------------
    # 5. Affordability flag
    # The 40% / 45% gross income thresholds are the most common
    # lender benchmarks for total housing cost as a share of
    # gross monthly income.
    # --------------------------------------------------------
    gross_monthly_income: float = inp.gross_annual_income_gbp / 12
    total_stress_burden:  float = stress_monthly + inp.monthly_debts_gbp
    stress_burden_pct:    float = (total_stress_burden / gross_monthly_income) * 100

    if income_multiple > MAX_INCOME_MULTIPLE or stress_burden_pct > 45:
        affordability_flag = "FAIL"
    elif income_multiple > BORDERLINE_INCOME_MULTIPLE or stress_burden_pct > 40:
        affordability_flag = "BORDERLINE"
    else:
        affordability_flag = "PASS"

    return MortgageAffordabilityOutput(
        ltv_pct                   = ltv_pct,
        income_multiple           = income_multiple,
        stress_tested_monthly_gbp = stress_monthly,
        standard_monthly_gbp      = standard_monthly,
        max_loan_at_4_5x_gbp     = max_loan_at_4_5x,
        affordability_flag        = affordability_flag,
        ltv_band                  = ltv_band,
    )