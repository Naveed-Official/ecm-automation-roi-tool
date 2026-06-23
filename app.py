"""
ECM Automation ROI Decision Tool
Master Thesis Decision-Support Prototype

Developed by Naveed Anwar
MBA Business in a Digital World
Westsächsische Hochschule Zwickau (WHZ)

Thesis: "Process Automation for Cost Optimization in Product Development:
         Measuring ROI Through Engineering Change Management"

Run with:
    streamlit run app.py
"""

import os
import streamlit as st


# =============================================================================
# APP CONFIGURATION
# =============================================================================
APP_VERSION = "ECM-ROI-SIMPLIFIED-2026-06-23-V4"

st.set_page_config(
    page_title="ECM Automation ROI Decision Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# BASE CASE ASSUMPTIONS
# The normal application flow uses one representative Base Case.
# Detailed assumptions remain editable for research testing.
# =============================================================================
BASE_CASE = {
    "N": 500,                    # Annual engineering changes
    "H_eng": 10.0,               # Engineering hours per change
    "H_mgr": 1.0,                # Management approval hours per change
    "H_adm": 2.0,                # Administration / coordination hours per change
    "R_eng": 85.0,               # Engineer hourly rate
    "R_mgr": 100.0,              # Manager hourly rate
    "R_adm": 55.0,               # Admin / coordinator hourly rate
    "r_rw_pct": 20.0,            # Rework rate (%)
    "H_rw": 4.0,                 # Rework hours per event
    "C_del": 500.0,              # Daily delay cost per ECO
    "T_cyc": 15.0,               # Average cycle time (days)
    "discount_pct": 10.0,        # Discount rate (%)
    "T_h": 5,                    # Analysis horizon (years)
    "upfront": 215_000.0,        # Upfront investment
    "annual_system": 111_600.0,  # Annual system cost
    "delta_eng_pct": 45.0,       # Engineering effort reduction (%)
    "delta_mgr_pct": 40.0,       # Management effort reduction (%)
    "delta_adm_pct": 55.0,       # Admin effort reduction (%)
    "delta_rw_pct": 40.0,        # Rework reduction (%)
    "delta_cyc_pct": 50.0,       # Cycle-time / delay reduction (%)
}

# Unique, versioned widget keys deliberately avoid stale values stored from
# earlier Streamlit app versions in the same browser session.
UI_PREFIX = "ecm_roi_v4_"
UI_KEYS = {name: f"{UI_PREFIX}{name}" for name in BASE_CASE}


# =============================================================================
# STATE HELPERS
# =============================================================================
def ui_value(name):
    """Return current widget state or the Base Case default."""
    return st.session_state.get(UI_KEYS[name], BASE_CASE[name])


def reset_inputs_to_base_case():
    """Remove versioned widget state so the next run recreates Base Case values."""
    for key in UI_KEYS.values():
        st.session_state.pop(key, None)


def clamp(value, lower, upper):
    """Keep an initial slider value within its permitted range."""
    return max(lower, min(value, upper))


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================
def annuity_factor(discount_rate, horizon_years):
    """Present-value annuity factor.

    A = (1 - (1+r)^-T) / r
    If r = 0, the present-value factor is simply T.
    """
    if horizon_years <= 0:
        return 0.0
    if abs(discount_rate) < 1e-12:
        return float(horizon_years)
    return (1 - (1 + discount_rate) ** (-horizon_years)) / discount_rate


def manual_labour_cost(p):
    """Annual manual labour plus rework cost, excluding delay cost."""
    return p["N"] * (
        p["H_eng"] * p["R_eng"]
        + p["H_mgr"] * p["R_mgr"]
        + p["H_adm"] * p["R_adm"]
        + p["r_rw"] * p["H_rw"] * p["R_eng"]
    )


def manual_delay_cost(p):
    """Annual manual delay cost."""
    return p["N"] * p["C_del"] * p["T_cyc"]


def manual_total_cost(p):
    """Full manual annual ECM cost."""
    return manual_labour_cost(p) + manual_delay_cost(p)


def automated_labour_cost(p):
    """Annual automated labour plus rework cost, excluding delay and system cost."""
    return p["N"] * (
        p["H_eng"] * (1 - p["delta_eng"]) * p["R_eng"]
        + p["H_mgr"] * (1 - p["delta_mgr"]) * p["R_mgr"]
        + p["H_adm"] * (1 - p["delta_adm"]) * p["R_adm"]
        + p["r_rw"] * (1 - p["delta_rw"]) * p["H_rw"] * p["R_eng"]
    )


def automated_delay_cost(p):
    """Annual automated delay cost after the cycle-time reduction."""
    return p["N"] * p["C_del"] * p["T_cyc"] * (1 - p["delta_cyc"])


def automated_total_cost(p):
    """Full automated annual cost, including annual system cost."""
    return (
        automated_labour_cost(p)
        + automated_delay_cost(p)
        + p["annual_system"]
    )


def breakeven_changes(p, saving_per_change, annuity):
    """Minimum changes/year required for NPV = 0.

    N_be = (I_0 + C_op × A) / (s_per_change × A)
    """
    if saving_per_change <= 0 or annuity <= 0:
        return None
    return (
        p["upfront"] + p["annual_system"] * annuity
    ) / (saving_per_change * annuity)


def compute_full_model(p):
    """Full economic impact model, including delay cost."""
    c_manual = manual_total_cost(p)
    c_auto = automated_total_cost(p)
    annual_savings = c_manual - c_auto
    annuity = annuity_factor(p["r"], p["T_h"])

    roi = None
    if p["upfront"] > 0:
        roi = ((annual_savings * p["T_h"]) - p["upfront"]) / p["upfront"] * 100

    npv = -p["upfront"] + annual_savings * annuity
    payback_years = p["upfront"] / annual_savings if annual_savings > 0 else None

    manual_per_change = (
        p["H_eng"] * p["R_eng"]
        + p["H_mgr"] * p["R_mgr"]
        + p["H_adm"] * p["R_adm"]
        + p["r_rw"] * p["H_rw"] * p["R_eng"]
        + p["C_del"] * p["T_cyc"]
    )
    automated_per_change = (
        p["H_eng"] * (1 - p["delta_eng"]) * p["R_eng"]
        + p["H_mgr"] * (1 - p["delta_mgr"]) * p["R_mgr"]
        + p["H_adm"] * (1 - p["delta_adm"]) * p["R_adm"]
        + p["r_rw"] * (1 - p["delta_rw"]) * p["H_rw"] * p["R_eng"]
        + p["C_del"] * p["T_cyc"] * (1 - p["delta_cyc"])
    )

    saving_per_change = manual_per_change - automated_per_change
    break_even = breakeven_changes(p, saving_per_change, annuity)

    return {
        "c_manual": c_manual,
        "c_auto": c_auto,
        "annual_savings": annual_savings,
        "roi": roi,
        "npv": npv,
        "payback_years": payback_years,
        "tco_manual": c_manual * p["T_h"],
        "tco_auto": p["upfront"] + c_auto * p["T_h"],
        "break_even": break_even,
    }


def compute_conservative_model(p):
    """Conservative model: labour and rework savings only, net of system cost."""
    manual_lab = manual_labour_cost(p)
    automated_lab = automated_labour_cost(p)
    gross_savings = manual_lab - automated_lab
    net_savings = gross_savings - p["annual_system"]
    annuity = annuity_factor(p["r"], p["T_h"])

    roi = None
    if p["upfront"] > 0:
        roi = ((net_savings * p["T_h"]) - p["upfront"]) / p["upfront"] * 100

    npv = -p["upfront"] + net_savings * annuity
    payback_years = p["upfront"] / net_savings if net_savings > 0 else None

    saving_per_change = gross_savings / p["N"] if p["N"] > 0 else 0
    break_even = breakeven_changes(p, saving_per_change, annuity)

    return {
        "manual_lab": manual_lab,
        "automated_lab": automated_lab,
        "gross_savings": gross_savings,
        "net_savings": net_savings,
        "roi": roi,
        "npv": npv,
        "payback_years": payback_years,
        "break_even": break_even,
    }


def collect_params():
    """Build model parameters from the current interface values."""
    return {
        "N": int(ui_value("N")),
        "H_eng": float(ui_value("H_eng")),
        "H_mgr": float(ui_value("H_mgr")),
        "H_adm": float(ui_value("H_adm")),
        "R_eng": float(ui_value("R_eng")),
        "R_mgr": float(ui_value("R_mgr")),
        "R_adm": float(ui_value("R_adm")),
        "r_rw": float(ui_value("r_rw_pct")) / 100,
        "H_rw": float(ui_value("H_rw")),
        "C_del": float(ui_value("C_del")),
        "T_cyc": float(ui_value("T_cyc")),
        "r": float(ui_value("discount_pct")) / 100,
        "T_h": int(ui_value("T_h")),
        "upfront": float(ui_value("upfront")),
        "annual_system": float(ui_value("annual_system")),
        "delta_eng": float(ui_value("delta_eng_pct")) / 100,
        "delta_mgr": float(ui_value("delta_mgr_pct")) / 100,
        "delta_adm": float(ui_value("delta_adm_pct")) / 100,
        "delta_rw": float(ui_value("delta_rw_pct")) / 100,
        "delta_cyc": float(ui_value("delta_cyc_pct")) / 100,
    }


# =============================================================================
# FORMATTING HELPERS
# =============================================================================
def euro(value):
    if value is None:
        return "n/a"
    return f"€{value:,.0f}"


def pct(value):
    if value is None:
        return "n/a"
    return f"{value:,.0f}%"


def payback_text(years):
    if years is None:
        return "No payback"
    if years < 1:
        return f"{years * 12:.1f} months"
    return f"{years:.2f} years"


def metric_number(value):
    return f"{value:,.0f}" if value is not None else "n/a"


# =============================================================================
# UI COMPONENTS
# =============================================================================
def render_header():
    """Render optional logos and stable text branding."""
    logo_whz = "assets/whz_logo.png"
    logo_mba = "assets/mba_logo.png"

    left, centre, right = st.columns([1, 4, 1])

    with left:
        if os.path.exists(logo_whz):
            st.image(logo_whz, width=110)

    with centre:
        st.markdown(
            "<h1 style='margin-bottom:0;'>ECM Automation ROI Decision Tool</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#2E75B6; font-size:1.05rem; margin-top:0;'>"
            "Master Thesis Decision-Support Prototype</p>",
            unsafe_allow_html=True,
        )

    with right:
        if os.path.exists(logo_mba):
            st.image(logo_mba, width=110)

    st.markdown(
        "<p style='color:#555; margin-top:-8px;'>"
        "Developed by <b>Naveed Anwar</b> &nbsp;|&nbsp; "
        "MBA Business in a Digital World &nbsp;|&nbsp; "
        "Westsächsische Hochschule Zwickau (WHZ)</p>",
        unsafe_allow_html=True,
    )
    st.divider()


def page_start():
    st.header("Start Here")
    st.markdown(
        """
        This tool estimates whether **Engineering Change Management (ECM) automation**
        can be financially attractive under representative assumptions.

        It compares a **manual ECM process** with an **automated ECM process** and
        calculates annual savings, payback period, NPV, ROI, and the minimum annual
        number of changes needed to justify the investment.
        """
    )

    st.info(
        "This is a **decision-support prototype**, not a PLM system and not a "
        "guaranteed forecast. It is based on representative thesis assumptions and "
        "is intended to structure an investment discussion."
    )

    st.subheader("How the tool works")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown("### 1️⃣")
        st.markdown("**Manual ECM cost**")
        st.caption("Estimate the annual cost of running the ECM process manually.")

    with c2:
        st.markdown("### 2️⃣")
        st.markdown("**Automation effect**")
        st.caption("Apply Base Case reductions in effort, rework, and waiting time.")

    with c3:
        st.markdown("### 3️⃣")
        st.markdown("**Investment comparison**")
        st.caption("Include upfront investment and recurring system cost.")

    with c4:
        st.markdown("### 4️⃣")
        st.markdown("**Decision result**")
        st.caption("Review NPV, payback, ROI, and the break-even volume.")

    st.divider()
    st.subheader("Two models, one decision")
    st.markdown(
        """
        The tool presents two complementary views of the investment case:

        - **Conservative model:** the primary decision basis. It excludes uncertain
          delay-cost savings and evaluates whether labour and rework savings alone
          justify the investment.
        - **Full economic impact model:** a broader estimate that includes potential
          savings from faster change resolution. It should be interpreted carefully
          because the daily delay-cost assumption is uncertain.

        This approach allows the model to show both a cautious financial floor and
        potential upside.
        """
    )

    st.success(
        "Next step: open the **Calculator** page to review the Base Case or enter "
        "organisation-specific values."
    )


def page_calculator():
    st.header("Calculator")
    st.caption(
        "Start with the most important inputs. Defaults are the thesis Base Case. "
        "Open *Detailed research assumptions* only to review or test the detailed parameters."
    )
    st.caption(
        "This prototype uses a representative Base Case derived from the thesis "
        "assumptions. Uncertainty can be explored in the Sensitivity Check page."
    )

    st.divider()
    st.subheader("Key inputs")
    left, right = st.columns(2)

    with left:
        st.number_input(
            "Annual number of engineering changes",
            min_value=1,
            max_value=100_000,
            step=10,
            value=int(BASE_CASE["N"]),
            key=UI_KEYS["N"],
            help="How many engineering changes the organisation processes per year.",
        )
        st.number_input(
            "Engineering hours per change",
            min_value=0.0,
            max_value=200.0,
            step=0.5,
            value=float(BASE_CASE["H_eng"]),
            key=UI_KEYS["H_eng"],
            help="Average direct engineering effort per change.",
        )
        st.number_input(
            "Average cycle time (days)",
            min_value=0.0,
            max_value=365.0,
            step=1.0,
            value=float(BASE_CASE["T_cyc"]),
            key=UI_KEYS["T_cyc"],
            help="Average calendar days from change request to closure.",
        )
        st.number_input(
            "Daily delay cost per ECO (€)",
            min_value=0.0,
            max_value=50_000.0,
            step=50.0,
            value=float(BASE_CASE["C_del"]),
            key=UI_KEYS["C_del"],
            help="Illustrative indirect cost per day a change remains open.",
        )

    with right:
        st.number_input(
            "Upfront investment (€)",
            min_value=0.0,
            max_value=10_000_000.0,
            step=5_000.0,
            value=float(BASE_CASE["upfront"]),
            key=UI_KEYS["upfront"],
            help="One-time software, integration, training, and internal effort cost.",
        )
        st.number_input(
            "Annual system cost (€)",
            min_value=0.0,
            max_value=5_000_000.0,
            step=5_000.0,
            value=float(BASE_CASE["annual_system"]),
            key=UI_KEYS["annual_system"],
            help="Recurring licence, maintenance, support, and minor enhancement cost.",
        )

    with st.expander("Detailed research assumptions"):
        st.caption(
            "These assumptions are included for transparency and can be adjusted "
            "for research testing. For a standard demonstration, the Base Case "
            "values should be retained."
        )

        st.markdown("**Effort and rate parameters**")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.number_input(
                "Manager hours per change",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                value=float(BASE_CASE["H_mgr"]),
                key=UI_KEYS["H_mgr"],
            )
            st.number_input(
                "Admin hours per change",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                value=float(BASE_CASE["H_adm"]),
                key=UI_KEYS["H_adm"],
            )

        with col2:
            st.number_input(
                "Engineer hourly rate (€)",
                min_value=0.0,
                max_value=500.0,
                step=5.0,
                value=float(BASE_CASE["R_eng"]),
                key=UI_KEYS["R_eng"],
            )
            st.number_input(
                "Manager hourly rate (€)",
                min_value=0.0,
                max_value=500.0,
                step=5.0,
                value=float(BASE_CASE["R_mgr"]),
                key=UI_KEYS["R_mgr"],
            )
            st.number_input(
                "Admin hourly rate (€)",
                min_value=0.0,
                max_value=500.0,
                step=5.0,
                value=float(BASE_CASE["R_adm"]),
                key=UI_KEYS["R_adm"],
            )

        with col3:
            st.number_input(
                "Rework rate (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["r_rw_pct"]),
                key=UI_KEYS["r_rw_pct"],
            )
            st.number_input(
                "Rework hours per event",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                value=float(BASE_CASE["H_rw"]),
                key=UI_KEYS["H_rw"],
            )

        st.markdown("**Financial parameters**")
        fin1, fin2 = st.columns(2)

        with fin1:
            st.number_input(
                "Discount rate (%)",
                min_value=0.0,
                max_value=40.0,
                step=0.5,
                value=float(BASE_CASE["discount_pct"]),
                key=UI_KEYS["discount_pct"],
            )

        with fin2:
            st.number_input(
                "Analysis horizon (years)",
                min_value=1,
                max_value=15,
                step=1,
                value=int(BASE_CASE["T_h"]),
                key=UI_KEYS["T_h"],
            )

        st.markdown("**Base Case automation reduction percentages**")
        st.caption(
            "These Base Case reductions remain adjustable only for transparent research testing."
        )
        red1, red2, red3 = st.columns(3)

        with red1:
            st.number_input(
                "Engineering effort reduction (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["delta_eng_pct"]),
                key=UI_KEYS["delta_eng_pct"],
            )
            st.number_input(
                "Manager effort reduction (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["delta_mgr_pct"]),
                key=UI_KEYS["delta_mgr_pct"],
            )

        with red2:
            st.number_input(
                "Admin effort reduction (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["delta_adm_pct"]),
                key=UI_KEYS["delta_adm_pct"],
            )
            st.number_input(
                "Rework reduction (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["delta_rw_pct"]),
                key=UI_KEYS["delta_rw_pct"],
            )

        with red3:
            st.number_input(
                "Cycle-time / delay reduction (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=float(BASE_CASE["delta_cyc_pct"]),
                key=UI_KEYS["delta_cyc_pct"],
            )

    st.success(
        "Inputs are ready. Open the **Results** page to see the decision outcome. "
        "Use **Reset inputs to Base Case** in the sidebar anytime to restore thesis defaults."
    )


def page_results():
    st.header("Results")
    st.caption(
        "The Conservative model is the primary decision basis because it excludes "
        "uncertain delay-cost savings. The Full economic impact model shows potential "
        "upside if delay-cost assumptions are valid."
    )

    p = collect_params()
    full = compute_full_model(p)
    conservative = compute_conservative_model(p)

    if conservative["npv"] > 0:
        outcome = "Financially attractive under current assumptions"
        outcome_icon = "✅"
    elif full["npv"] > 0:
        outcome = "Depends on delay-cost assumptions"
        outcome_icon = "⚠️"
    else:
        outcome = "Not financially attractive under current assumptions"
        outcome_icon = "❌"

    top1, top2, top3 = st.columns(3)
    with top1:
        st.metric("Decision outcome", outcome_icon)
        st.markdown(f"**{outcome}**")
        st.caption("Decision is based on the Conservative model first.")

    with top2:
        st.metric(
            "Conservative model payback",
            payback_text(conservative["payback_years"]),
            help="Time to recover the upfront investment through labour and rework savings alone.",
        )

    with top3:
        st.metric(
            "Minimum changes/year needed",
            metric_number(conservative["break_even"]),
            help="Break-even annual change volume for the Conservative model.",
        )

    st.divider()
    st.subheader("Primary decision basis: Conservative model")
    st.caption(
        "This safer view excludes uncertain delay-cost savings and evaluates whether "
        "labour and rework savings, after annual system cost, justify the investment."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Annual net savings", euro(conservative["net_savings"]))
    c2.metric("NPV", euro(conservative["npv"]))
    c3.metric("Payback", payback_text(conservative["payback_years"]))

    c4, c5 = st.columns(2)
    c4.metric("Minimum changes/year needed", metric_number(conservative["break_even"]))
    c5.metric("5-year total ROI", pct(conservative["roi"]))

    st.divider()
    st.subheader("Potential upside: Full economic impact model")
    st.caption(
        "This broader view includes potential savings from faster change resolution "
        "and is therefore dependent on the delay-cost assumption."
    )

    f1, f2, f3 = st.columns(3)
    f1.metric("Annual savings", euro(full["annual_savings"]))
    f2.metric("NPV", euro(full["npv"]))
    f3.metric(
        "Assumption-dependent 5-year ROI",
        pct(full["roi"]),
        help=(
            "This ROI includes assumed savings from reduced delay cost. It is shown "
            "as potential economic upside and should be validated using organisation-specific delay-cost data."
        ),
    )
    f3.caption(
        "Includes assumed delay-cost savings. Validate this with organisation-specific data."
    )

    f4, f5, f6 = st.columns(3)
    f4.metric("Payback", payback_text(full["payback_years"]))
    f5.metric("TCO manual (5yr)", euro(full["tco_manual"]))
    f6.metric("TCO automated (5yr)", euro(full["tco_auto"]))

    st.warning(
        "The Full economic impact model includes assumed delay-cost savings. Its ROI "
        "is therefore assumption-dependent and should be interpreted as potential "
        "upside, not as a universal or guaranteed return."
    )

    st.divider()
    with st.expander("Base Case validation"):
        st.caption(
            "This check reproduces the accepted thesis Base Case when the defaults "
            "are retained. Values may differ after changing any input."
        )
        validation_row("Manual annual ECM cost", full["c_manual"], 4_314_000)
        validation_row("Automated annual cost (full model)", full["c_auto"], 2_295_500)
        validation_row("Full-model NPV", full["npv"], 7_436_703, tolerance=0.02)
        validation_row("Conservative model NPV", conservative["npv"], 328_978, tolerance=0.02)
        validation_row(
            "Conservative break-even (changes/year)",
            conservative["break_even"],
            330,
            tolerance=0.02,
            is_count=True,
        )
        validation_row(
            "Full-model break-even (changes/year)",
            full["break_even"],
            40,
            tolerance=0.10,
            is_count=True,
        )


def validation_row(label, actual, target, tolerance=0.01, is_count=False):
    if actual is None:
        st.write(f"❓ **{label}:** n/a")
        return

    difference = abs(actual - target) / target if target else 0
    status = "✅" if difference <= tolerance else "⚠️"

    if is_count:
        displayed = f"{actual:.0f} (target ≈ {target:.0f})"
    else:
        displayed = f"{euro(actual)} (target ≈ {euro(target)})"

    st.write(f"{status} **{label}:** {displayed}")


def page_sensitivity():
    st.header("Sensitivity Check")
    st.caption(
        "This page tests the three assumptions that have the strongest effect on the "
        "investment case. It is used to examine uncertainty around the Base Case "
        "rather than to create additional automation scenarios."
    )

    p = collect_params()
    default_n = clamp(int(p["N"]), 50, 2_000)
    default_delay = clamp(int(p["C_del"]), 0, 2_000)
    default_upfront = clamp(int(p["upfront"]), 50_000, 1_000_000)

    s1, s2, s3 = st.columns(3)
    with s1:
        p["N"] = st.slider(
            "Annual change volume",
            min_value=50,
            max_value=2_000,
            value=default_n,
            step=10,
            key=f"{UI_PREFIX}sensitivity_N",
        )

    with s2:
        p["C_del"] = st.slider(
            "Daily delay cost (€)",
            min_value=0,
            max_value=2_000,
            value=default_delay,
            step=50,
            key=f"{UI_PREFIX}sensitivity_delay",
        )

    with s3:
        p["upfront"] = st.slider(
            "Upfront investment (€)",
            min_value=50_000,
            max_value=1_000_000,
            value=default_upfront,
            step=10_000,
            key=f"{UI_PREFIX}sensitivity_upfront",
        )

    full = compute_full_model(p)
    conservative = compute_conservative_model(p)

    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Conservative model NPV", euro(conservative["npv"]))
    r2.metric("Conservative model payback", payback_text(conservative["payback_years"]))
    r3.metric("Full economic impact NPV", euro(full["npv"]))
    r4.metric("Full economic impact payback", payback_text(full["payback_years"]))

    st.subheader("NPV comparison")
    st.bar_chart(
        {
            "NPV (€)": {
                "Conservative model": conservative["npv"],
                "Full economic impact model": full["npv"],
            }
        }
    )

    st.info(
        "If the Conservative model remains positive, the investment case does not "
        "depend on delay-cost assumptions. If only the Full economic impact model is "
        "positive, the decision depends strongly on whether the delay cost is realistic."
    )


def page_methodology():
    st.header("Methodology")
    st.caption("Short, MBA-friendly explanations of the model logic and formulas.")

    with st.expander("Manual cost formula"):
        st.markdown(
            "**Manual annual ECM cost** = labour and rework cost + delay cost.\n\n"
            "`C_manual = N × [H_eng×R_eng + H_mgr×R_mgr + H_adm×R_adm + "
            "r_rw×H_rw×R_eng] + N × C_del × T_cyc`"
        )

    with st.expander("Automated cost formula"):
        st.markdown(
            "Each cost element is reduced by its automation percentage, then the "
            "annual system cost is added.\n\n"
            "`C_auto = N × [H_eng(1−δ_eng)R_eng + H_mgr(1−δ_mgr)R_mgr + "
            "H_adm(1−δ_adm)R_adm + r_rw(1−δ_rw)H_rw×R_eng + "
            "C_del×T_cyc(1−δ_cyc)] + Annual system cost`"
        )

    with st.expander("Conservative model formula"):
        st.markdown(
            "The Conservative model excludes delay cost and deducts the annual "
            "system cost from labour and rework savings.\n\n"
            "`Net savings = (manual labour+rework) − (automated labour+rework) − "
            "annual system cost`"
        )

    with st.expander("ROI formula"):
        st.markdown(
            "`5-year total ROI (%) = ((annual savings × analysis horizon) − upfront investment) "
            "/ upfront investment × 100`"
        )

    with st.expander("Payback formula"):
        st.markdown("`Payback = upfront investment / annual savings`")

    with st.expander("NPV formula"):
        st.markdown(
            "`NPV = −upfront investment + annual savings × A`, where "
            "`A = (1 − (1 + r)^(−T_h)) / r`.\n\n"
            "When the discount rate is 0%, the model uses the analysis horizon as the annuity factor."
        )

    with st.expander("TCO formula"):
        st.markdown(
            "`TCO manual = C_manual × T_h`\n\n"
            "`TCO automated = upfront investment + C_auto × T_h`"
        )

    with st.expander("Break-even formula"):
        st.markdown(
            "`Minimum changes/year = (upfront investment + annual system cost × A) / "
            "(saving per change × A)`\n\n"
            "For the Conservative model, the saving per change includes only labour "
            "and rework savings, not delay cost.\n\n"
            "For the Full economic impact model, the saving per change includes labour, "
            "rework, and delay-cost savings before annual system cost is added separately "
            "in the break-even formula."
        )

    with st.expander("Why two models are used"):
        st.markdown(
            "The **Conservative model** is used as the primary decision basis because "
            "it excludes uncertain delay-cost savings. The **Full economic impact model** "
            "is presented as potential upside if the organisation can validate its "
            "specific delay-cost exposure."
        )

    with st.expander("Why delay cost is uncertain"):
        st.markdown(
            "Delay cost can be the largest single item in a manual process, but there "
            "is no neutral industry benchmark that applies across all firms. It varies "
            "by industry, product complexity, production flexibility, and how well "
            "downstream activities can absorb delays. It is therefore treated as an "
            "**illustrative assumption** and should be replaced with organisation-specific "
            "data where available."
        )

    with st.expander("Source and assumption notes"):
        st.markdown(
            """
            - **Loch and Terwiesch (1999)** and **Terwiesch and Loch (1999)** provide
              the main academic anchors for ECO effort, queueing, and congestion logic.
            - **Jarratt et al. (2011)** supports the ECM definition and process structure.
            - **Aberdeen Group (2007)** is industry benchmark evidence, not peer-reviewed evidence.
            - **Ellram (1995)** supports the total cost of ownership logic.
            - **Brealey, Myers and Allen (2020)** support the ROI, payback, and NPV logic.
            - **Delay cost is illustrative** and should be validated with organisation-specific data.
            """
        )


# =============================================================================
# MAIN APP
# =============================================================================
def main():
    render_header()

    page = st.sidebar.radio(
        "Navigate",
        ["Start Here", "Calculator", "Results", "Sensitivity Check", "Methodology"],
        key=f"{UI_PREFIX}navigation",
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "ECM Automation ROI Decision Tool\n\n"
        "Master Thesis prototype — Naveed Anwar, MBA, WHZ Zwickau."
    )

    if st.sidebar.button("Reset inputs to Base Case", key=f"{UI_PREFIX}reset"):
        reset_inputs_to_base_case()
        st.rerun()

    st.sidebar.caption(f"Build: {APP_VERSION}")

    if page == "Start Here":
        page_start()
    elif page == "Calculator":
        page_calculator()
    elif page == "Results":
        page_results()
    elif page == "Sensitivity Check":
        page_sensitivity()
    else:
        page_methodology()


if __name__ == "__main__":
    main()
