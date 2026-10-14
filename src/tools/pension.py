"""
Module:      src/tools/pension.py
Description: Pension and retirement calculation tools for the Sovereign
             Advisor MCP server. Two tools are exposed here:

             1. calculate_pension_gap — projects the client's pension pot at
                retirement, models an annual income from that pot at a 3.5%
                sustainable withdrawal rate, adds the State Pension, and
                surfaces any income gap against the client's target. Foundry
                uses this to confirm whether a SIPP top-up or increased
                workplace contributions are required.

             2. calculate_drawdown_sustainability — models how long a given
                pension pot lasts under flexi-access drawdown (FAD) at the
                client's desired annual withdrawal. Surfaces a sequencing risk
                flag when the withdrawal rate exceeds 4% — the FCA COBS 19
                documentation threshold that advisers must evidence in the
                client file (KB005, Rule 5).

Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from src.models.schemas import (
    PensionGapInput,
    PensionGapOutput,
    DrawdownSustainabilityInput,
    DrawdownSustainabilityOutput,
)

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
# Sustainable withdrawal rate benchmark per KB005 Rule 5 and
# standard UK adviser practice. Foundry should flag any client
# plan above this rate as requiring sequencing-risk documentation.
SUSTAINABLE_WITHDRAWAL_RATE: float = 0.035   # 3.5%
SEQUENCING_RISK_THRESHOLD:   float = 0.040   # 4.0%
WEEKS_IN_YEAR:               int   = 52


# ============================================================
# TOOL 1 - CALCULATE PENSION GAP
# ============================================================

def calculate_pension_gap(inp: PensionGapInput) -> PensionGapOutput:
    """
    Project a client's pension pot to their target retirement age
    and compare projected income to their stated target.

    Growth model:
        Future pot = (current_pot x (1+r)^n)
                   + monthly_contribution x [((1+r)^n - 1) / r]
    where r = monthly growth rate and n = total months.

    The annual income is modelled at the SUSTAINABLE_WITHDRAWAL_RATE
    (3.5%) to avoid exhausting the pension. State Pension is added
    to the income projection.

    The monthly_extra_needed_gbp output tells Foundry exactly
    how much additional contribution would close the gap, so the
    adviser can have a precise conversation with the client.
    """
    logger.debug("calculate_pension_gap: pot=%.2f, monthly=%.2f, years=%d, target_income=%.2f",
                 inp.current_pot_gbp, inp.monthly_contribution_gbp,
                 inp.years_to_retirement, inp.target_annual_income_gbp)

    # --------------------------------------------------------
    # Convert annual growth rate to monthly
    # --------------------------------------------------------
    annual_rate:  float = inp.assumed_annual_growth / 100
    monthly_rate: float = (1 + annual_rate) ** (1 / 12) - 1
    n_months:     int   = inp.years_to_retirement * 12

    # --------------------------------------------------------
    # Project the current pot forward
    # --------------------------------------------------------
    pot_growth: float = inp.current_pot_gbp * (1 + monthly_rate) ** n_months

    # --------------------------------------------------------
    # Future value of monthly contributions (standard annuity formula).
    # Guard against zero monthly rate edge case.
    # --------------------------------------------------------
    if monthly_rate > 0:
        contribution_fv: float = (
            inp.monthly_contribution_gbp
            * (((1 + monthly_rate) ** n_months - 1) / monthly_rate)
        )
    else:
        contribution_fv = inp.monthly_contribution_gbp * n_months

    projected_pot_gbp: float = pot_growth + contribution_fv

    # --------------------------------------------------------
    # Annual income at 3.5% sustainable withdrawal rate
    # --------------------------------------------------------
    projected_annual_drawdown: float = projected_pot_gbp * SUSTAINABLE_WITHDRAWAL_RATE

    # --------------------------------------------------------
    # State Pension contribution to total income
    # --------------------------------------------------------
    state_pension_annual: float = inp.state_pension_weekly_gbp * WEEKS_IN_YEAR

    total_projected_income: float = projected_annual_drawdown + state_pension_annual

    # --------------------------------------------------------
    # Income gap (positive = shortfall; negative = surplus)
    # --------------------------------------------------------
    income_gap: float = inp.target_annual_income_gbp - total_projected_income

    # --------------------------------------------------------
    # How much more per month the client needs to contribute
    # to close the gap. Derived by back-solving the future
    # value annuity formula.
    # --------------------------------------------------------
    if income_gap > 0 and monthly_rate > 0 and n_months > 0:
        additional_pot_needed: float = income_gap / SUSTAINABLE_WITHDRAWAL_RATE
        fv_factor:             float = ((1 + monthly_rate) ** n_months - 1) / monthly_rate
        monthly_extra_needed:  float = additional_pot_needed / fv_factor
    else:
        monthly_extra_needed = 0.0

    return PensionGapOutput(
        projected_pot_gbp             = round(projected_pot_gbp, 2),
        projected_annual_drawdown_gbp = round(projected_annual_drawdown, 2),
        state_pension_annual_gbp      = round(state_pension_annual, 2),
        total_projected_income_gbp    = round(total_projected_income, 2),
        income_gap_gbp                = round(income_gap, 2),
        monthly_extra_needed_gbp      = round(max(0.0, monthly_extra_needed), 2),
    )


# ============================================================
# TOOL 2 - CALCULATE DRAWDOWN SUSTAINABILITY
# ============================================================

def calculate_drawdown_sustainability(inp: DrawdownSustainabilityInput) -> DrawdownSustainabilityOutput:
    """
    Model how long a pension pot lasts under flexi-access
    drawdown (FAD) and flag sequencing risk.

    The model runs a year-by-year simulation:
        pot_start_year x (1 + growth_rate) - annual_withdrawal
    until the pot is exhausted or 100 years have passed.

    State Pension is subtracted from the desired drawdown amount
    because it covers part of the client's income need — only the
    remaining gap is drawn from the pension pot. This is the
    correct adviser approach per KB005 Rule 5.

    Sequencing risk flag: if the withdrawal rate from the pot
    exceeds 4%, Foundry must include the sequencing risk
    documentation reminder in its output per FCA COBS 19.
    """
    logger.debug("calculate_drawdown_sustainability: pot=%.2f, withdrawal=%.2f, growth=%.2f%%",
                 inp.pot_gbp, inp.annual_withdrawal_gbp, inp.assumed_annual_growth)

    # --------------------------------------------------------
    # State Pension reduces how much needs to come from the pot
    # --------------------------------------------------------
    state_pension_annual: float = inp.state_pension_weekly_gbp * WEEKS_IN_YEAR
    net_drawdown_needed:  float = max(0.0, inp.annual_withdrawal_gbp - state_pension_annual)

    # --------------------------------------------------------
    # Withdrawal rate as % of the pot (adviser benchmark metric)
    # --------------------------------------------------------
    withdrawal_rate_pct: float = (
        round((net_drawdown_needed / inp.pot_gbp) * 100, 2) if inp.pot_gbp > 0 else 0.0
    )

    # --------------------------------------------------------
    # Year-by-year simulation
    # --------------------------------------------------------
    annual_growth: float = inp.assumed_annual_growth / 100
    pot:           float = inp.pot_gbp
    years:         float = 0.0
    MAX_YEARS:     int   = 100

    while pot > 0 and years < MAX_YEARS:
        pot    = pot * (1 + annual_growth) - net_drawdown_needed
        years += 1

    years_pot_lasts: float = years if pot <= 0 else MAX_YEARS

    # --------------------------------------------------------
    # Maximum sustainable annual income at 3.5% withdrawal rate
    # (from the pot alone — State Pension is additive on top)
    # --------------------------------------------------------
    sustainable_from_pot: float = inp.pot_gbp * SUSTAINABLE_WITHDRAWAL_RATE
    sustainable_total:    float = sustainable_from_pot + state_pension_annual

    shortfall_vs_desired: float = max(0.0, inp.annual_withdrawal_gbp - sustainable_total)

    # --------------------------------------------------------
    # Sequencing risk flag: withdrawal rate from pot exceeds 4%
    # --------------------------------------------------------
    sequencing_risk: bool = (withdrawal_rate_pct / 100) > SEQUENCING_RISK_THRESHOLD

    return DrawdownSustainabilityOutput(
        withdrawal_rate_pct           = withdrawal_rate_pct,
        years_pot_lasts               = round(years_pot_lasts, 1),
        sustainable_annual_income_gbp = round(sustainable_total, 2),
        shortfall_vs_desired_gbp      = round(shortfall_vs_desired, 2),
        sequencing_risk_flag          = sequencing_risk,
    )