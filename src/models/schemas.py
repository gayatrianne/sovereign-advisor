"""
Module:      src/models/schemas.py
Description: Pydantic input and output schemas for every tool exposed by the
             Sovereign Advisor MCP server. Each tool has a dedicated Input
             and Output class so Azure AI Foundry generates an accurate JSON
             Schema for the tool manifest and can validate arguments before
             calling the tool function.

             Schema naming convention:
               <ToolName>Input   — arguments the Foundry agent passes in
               <ToolName>Output  — structured result the tool returns

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
from pydantic import BaseModel, Field
from typing   import Optional

# ============================================================
# DEBT TOOLS
# ============================================================

class DebtCostInput(BaseModel):
    """
    Input for calculate_debt_cost.
    Computes total interest paid and monthly payment on a
    single debt — used by Foundry to prioritise debts and
    determine whether a balance transfer is worthwhile.
    """
    balance_gbp:         float = Field(..., description="Current outstanding balance in GBP")
    annual_apr:          float = Field(..., description="Annual interest rate as a percentage (e.g. 22.9 for 22.9% APR)")
    monthly_payment_gbp: float = Field(..., description="Fixed monthly payment amount in GBP")


class DebtCostOutput(BaseModel):
    """
    Output for calculate_debt_cost.
    """
    months_to_clear:        int
    total_interest_gbp:     float
    total_repaid_gbp:       float
    effective_monthly_rate: float   # APR converted to monthly for transparency


class TransferFeeVsInterestInput(BaseModel):
    """
    Input for calculate_transfer_fee_vs_interest.
    Compares the one-off balance transfer fee against the
    interest that would accrue if the balance stays on the
    existing card for the 0% promotional window.
    """
    balance_gbp:      float = Field(..., description="Balance to transfer in GBP")
    current_apr:      float = Field(..., description="Current card APR as a percentage")
    transfer_fee_pct: float = Field(..., description="Balance transfer fee as a percentage (e.g. 3.45)")
    promo_months:     int   = Field(..., description="Length of the 0% promotional period in months")


class TransferFeeVsInterestOutput(BaseModel):
    """
    Output for calculate_transfer_fee_vs_interest.
    """
    transfer_fee_gbp:     float
    interest_if_stay_gbp: float
    saving_gbp:           float   # Positive = transfer is worthwhile
    recommendation:       str     # Plain-English summary for Foundry to relay


# ============================================================
# SAVINGS TOOLS
# ============================================================

class SavingsGapInput(BaseModel):
    """
    Input for calculate_savings_gap.
    Determines how many months it will take to reach a
    savings goal at the client's current monthly contribution
    rate, accounting for interest earned.
    """
    goal_gbp:                 float = Field(..., description="Target savings amount in GBP")
    current_balance_gbp:      float = Field(..., description="Existing savings balance in GBP")
    monthly_contribution_gbp: float = Field(..., description="Amount added to savings each month")
    annual_interest_rate:     float = Field(..., description="Gross AER of the savings account as a percentage")


class SavingsGapOutput(BaseModel):
    """
    Output for calculate_savings_gap.
    """
    months_to_goal:            int
    total_interest_earned_gbp: float
    projected_balance_gbp:     float   # Balance after months_to_goal months


class EmergencyFundInput(BaseModel):
    """
    Input for calculate_emergency_fund_target.
    FCA Consumer Duty requires advisers to ensure clients
    hold liquid emergency reserves before committing to
    long-term savings or investment products.
    """
    monthly_essential_expenses_gbp: float = Field(
        ..., description="Total monthly essential outgoings: rent/mortgage, utilities, food, transport"
    )
    months_cover:            int   = Field(
        default=3, description="Number of months of expenses to hold as emergency reserve (typically 3 to 6)"
    )
    current_easy_access_gbp: float = Field(
        default=0.0, description="Cash already held in instant-access savings accounts"
    )


class EmergencyFundOutput(BaseModel):
    """
    Output for calculate_emergency_fund_target.
    """
    target_gbp:           float
    shortfall_gbp:        float   # How much more needs to be saved; 0 if already met
    months_of_cover_held: float   # Current holdings expressed as months of expenses


# ============================================================
# PENSION TOOLS
# ============================================================

class PensionGapInput(BaseModel):
    """
    Input for calculate_pension_gap.
    Projects the client's pension pot at their target
    retirement age and compares it to their target annual
    income, surfacing any funding shortfall for Foundry
    to reason over.
    """
    current_pot_gbp:          float = Field(..., description="Total current pension pot value across all schemes")
    monthly_contribution_gbp: float = Field(..., description="Total monthly pension contribution (employee + employer combined)")
    years_to_retirement:      int   = Field(..., description="Number of years until the client's target retirement age")
    assumed_annual_growth:    float = Field(default=5.0, description="Assumed annual investment growth rate as a percentage")
    target_annual_income_gbp: float = Field(..., description="Client's desired gross annual retirement income in GBP")
    state_pension_weekly_gbp: float = Field(default=241.30, description="Expected weekly State Pension (default = full 2026/27 amount)")


class PensionGapOutput(BaseModel):
    """
    Output for calculate_pension_gap.
    """
    projected_pot_gbp:             float
    projected_annual_drawdown_gbp: float   # At 3.5% sustainable withdrawal rate
    state_pension_annual_gbp:      float
    total_projected_income_gbp:    float
    income_gap_gbp:                float   # Positive = shortfall; negative = surplus
    monthly_extra_needed_gbp:      float   # Additional monthly contribution to close the gap


class DrawdownSustainabilityInput(BaseModel):
    """
    Input for calculate_drawdown_sustainability.
    Models how long a pension pot will last under flexi-access
    drawdown at the client's desired withdrawal rate.
    Foundry uses this to flag sequencing risk and MPAA
    trigger consequences before recommending drawdown.
    """
    pot_gbp:                  float = Field(..., description="Total pension pot value at retirement in GBP")
    annual_withdrawal_gbp:    float = Field(..., description="Desired gross annual income from drawdown")
    assumed_annual_growth:    float = Field(default=4.0, description="Conservative assumed annual growth during drawdown (%)")
    state_pension_weekly_gbp: float = Field(default=241.30, description="Expected weekly State Pension in GBP")


class DrawdownSustainabilityOutput(BaseModel):
    """
    Output for calculate_drawdown_sustainability.
    """
    withdrawal_rate_pct:           float   # Annual withdrawal as % of pot
    years_pot_lasts:               float   # Estimated years before pot is exhausted
    sustainable_annual_income_gbp: float   # Max annual withdrawal at 3.5% sustainable rate
    shortfall_vs_desired_gbp:      float   # Desired minus sustainable; 0 if sustainable
    sequencing_risk_flag:          bool    # True if withdrawal rate > 4%


# ============================================================
# MORTGAGE TOOLS
# ============================================================

class MortgageAffordabilityInput(BaseModel):
    """
    Input for calculate_mortgage_affordability.
    Applies the standard UK lender affordability stress test
    (Bank Rate + 3% buffer, as required by FCA MCOB 11.6)
    and checks whether the requested loan amount is within
    the typical 4 to 4.5x income multiple.
    """
    gross_annual_income_gbp: float = Field(..., description="Total gross annual income for all applicants combined")
    loan_amount_gbp:         float = Field(..., description="Requested mortgage loan amount in GBP")
    property_value_gbp:      float = Field(..., description="Full property purchase price or estimated value in GBP")
    monthly_debts_gbp:       float = Field(default=0.0, description="Total existing monthly debt commitments in GBP")
    mortgage_term_years:     int   = Field(default=25, description="Requested mortgage term in years")
    current_interest_rate:   float = Field(..., description="Initial fixed or tracker rate offered by the lender (%)")


class MortgageAffordabilityOutput(BaseModel):
    """
    Output for calculate_mortgage_affordability.
    """
    ltv_pct:                   float   # Loan-to-Value percentage
    income_multiple:           float   # Loan as multiple of gross income
    stress_tested_monthly_gbp: float   # Monthly payment at stress rate (current rate + 3%)
    standard_monthly_gbp:      float   # Monthly payment at the initial quoted rate
    max_loan_at_4_5x_gbp:      float   # Maximum affordable loan at 4.5x income multiple
    affordability_flag:        str     # PASS | BORDERLINE | FAIL
    ltv_band:                  str     # e.g. "75% LTV (standard rate band)"


# ============================================================
# CHILD / EDUCATION SAVINGS TOOLS
# ============================================================

class JISAProjectionInput(BaseModel):
    """
    Input for calculate_jisa_projection.
    Projects the value of a Junior Stocks and Shares ISA at
    the child's 18th birthday, assuming regular monthly
    contributions invested into a global equity tracker.
    """
    child_age_years:          int   = Field(..., description="Child's current age in whole years")
    monthly_contribution_gbp: float = Field(..., description="Proposed monthly contribution into the Junior ISA in GBP")
    current_balance_gbp:      float = Field(default=0.0, description="Existing Junior ISA balance if one is already open")
    assumed_annual_growth:    float = Field(default=7.0, description="Assumed annual equity growth rate as a percentage")


class JISAProjectionOutput(BaseModel):
    """
    Output for calculate_jisa_projection.
    """
    years_to_18:                int
    projected_balance_gbp:      float
    total_contributions_gbp:    float
    total_growth_gbp:           float
    effective_annual_return_pct: float   # Confirms the growth rate used in the model