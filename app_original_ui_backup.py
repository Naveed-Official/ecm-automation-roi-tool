import streamlit as st
import pandas as pd
from dataclasses import dataclass, asdict

st.set_page_config(page_title="ECM Automation ROI Tool", page_icon="⚙️", layout="wide")


# =============================
# Data model
# =============================
@dataclass
class ManualProcessInputs:
    changes_per_year: int
    engineering_hours_per_change: float
    manager_hours_per_change: float
    admin_hours_per_change: float
    avg_cycle_time_days: float
    rework_rate_pct: float
    rework_hours_per_change: float
    delay_cost_per_day: float
    engineer_hourly_rate: float
    manager_hourly_rate: float
    admin_hourly_rate: float


@dataclass
class AutomationScenarioInputs:
    engineering_effort_reduction_pct: float
    manager_effort_reduction_pct: float
    admin_effort_reduction_pct: float
    cycle_time_reduction_pct: float
    rework_reduction_pct: float
    workflow_automation_level: str
    data_integration_level: str
    approval_automation_level: str


@dataclass
class InvestmentInputs:
    software_license_cost: float
    implementation_cost: float
    integration_cost: float
    training_cost: float
    internal_project_effort_cost: float
    annual_maintenance_cost: float
    analysis_horizon_years: int
    discount_rate_pct: float


# =============================
# Helper functions
# =============================
def eur(value: float) -> str:
    return f"€{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def level_badge(label: str) -> str:
    colors = {
        "Low": "#e8f5e9",
        "Medium": "#fff8e1",
        "High": "#ffebee",
    }
    return colors.get(label, "#f3f4f6")


def automation_maturity_score(workflow: str, data: str, approval: str) -> tuple[float, str]:
    mapping = {"Low": 1, "Medium": 2, "High": 3}
    score = (mapping[workflow] + mapping[data] + mapping[approval]) / 3
    label = "Low" if score < 1.7 else "Medium" if score < 2.5 else "High"
    return score, label


def calculate_manual_costs(m: ManualProcessInputs) -> dict:
    annual_engineering_cost = (
        m.changes_per_year
        * m.engineering_hours_per_change
        * m.engineer_hourly_rate
    )
    annual_manager_cost = (
        m.changes_per_year
        * m.manager_hours_per_change
        * m.manager_hourly_rate
    )
    annual_admin_cost = (
        m.changes_per_year
        * m.admin_hours_per_change
        * m.admin_hourly_rate
    )
    annual_rework_cost = (
        m.changes_per_year
        * (m.rework_rate_pct / 100)
        * m.rework_hours_per_change
        * m.engineer_hourly_rate
    )
    annual_delay_cost = (
        m.changes_per_year
        * m.avg_cycle_time_days
        * m.delay_cost_per_day
    )

    total_manual_cost = (
        annual_engineering_cost
        + annual_manager_cost
        + annual_admin_cost
        + annual_rework_cost
        + annual_delay_cost
    )

    return {
        "annual_engineering_cost": annual_engineering_cost,
        "annual_manager_cost": annual_manager_cost,
        "annual_admin_cost": annual_admin_cost,
        "annual_rework_cost": annual_rework_cost,
        "annual_delay_cost": annual_delay_cost,
        "total_manual_cost": total_manual_cost,
    }


def calculate_automated_costs(
    m: ManualProcessInputs,
    a: AutomationScenarioInputs,
    inv: InvestmentInputs,
) -> dict:
    manual = calculate_manual_costs(m)

    automated_engineering_cost = manual["annual_engineering_cost"] * (1 - a.engineering_effort_reduction_pct / 100)
    automated_manager_cost = manual["annual_manager_cost"] * (1 - a.manager_effort_reduction_pct / 100)
    automated_admin_cost = manual["annual_admin_cost"] * (1 - a.admin_effort_reduction_pct / 100)
    automated_rework_cost = manual["annual_rework_cost"] * (1 - a.rework_reduction_pct / 100)
    automated_delay_cost = manual["annual_delay_cost"] * (1 - a.cycle_time_reduction_pct / 100)

    total_automated_operating_cost = (
        automated_engineering_cost
        + automated_manager_cost
        + automated_admin_cost
        + automated_rework_cost
        + automated_delay_cost
        + inv.annual_maintenance_cost
    )

    annual_savings = manual["total_manual_cost"] - total_automated_operating_cost

    return {
        "automated_engineering_cost": automated_engineering_cost,
        "automated_manager_cost": automated_manager_cost,
        "automated_admin_cost": automated_admin_cost,
        "automated_rework_cost": automated_rework_cost,
        "automated_delay_cost": automated_delay_cost,
        "total_automated_operating_cost": total_automated_operating_cost,
        "annual_savings": annual_savings,
    }


def calculate_investment_total(inv: InvestmentInputs) -> float:
    return (
        inv.software_license_cost
        + inv.implementation_cost
        + inv.integration_cost
        + inv.training_cost
        + inv.internal_project_effort_cost
    )


def calculate_financials(m: ManualProcessInputs, a: AutomationScenarioInputs, inv: InvestmentInputs) -> dict:
    manual = calculate_manual_costs(m)
    automated = calculate_automated_costs(m, a, inv)
    upfront_investment = calculate_investment_total(inv)

    annual_savings = automated["annual_savings"]
    roi_pct = ((annual_savings - upfront_investment) / upfront_investment * 100) if upfront_investment > 0 else 0
    payback_months = (upfront_investment / (annual_savings / 12)) if annual_savings > 0 else None

    discount_rate = inv.discount_rate_pct / 100
    cash_flows = [-upfront_investment]
    npv = -upfront_investment
    for year in range(1, inv.analysis_horizon_years + 1):
        annual_net_benefit = annual_savings
        cash_flows.append(annual_net_benefit)
        npv += annual_net_benefit / ((1 + discount_rate) ** year)

    tco_manual = manual["total_manual_cost"] * inv.analysis_horizon_years
    tco_automated = upfront_investment + automated["total_automated_operating_cost"] * inv.analysis_horizon_years

    if annual_savings <= 0:
        decision = "No-Go"
        rationale = "Automation does not generate positive annual savings under the current assumptions."
    elif roi_pct >= 20 and payback_months is not None and payback_months <= 24:
        decision = "Go"
        rationale = "The automation case is financially attractive with positive savings and a reasonable payback period."
    elif roi_pct >= 0 and payback_months is not None and payback_months <= 36:
        decision = "Review"
        rationale = "The case appears promising, but assumptions should be stress-tested before investment."
    else:
        decision = "No-Go"
        rationale = "The return profile is too weak compared with the required investment."

    return {
        **manual,
        **automated,
        "upfront_investment": upfront_investment,
        "roi_pct": roi_pct,
        "payback_months": payback_months,
        "npv": npv,
        "tco_manual": tco_manual,
        "tco_automated": tco_automated,
        "decision": decision,
        "rationale": rationale,
        "cash_flows": cash_flows,
    }


def init_state() -> None:
    if "saved_case" not in st.session_state:
        st.session_state.saved_case = None


init_state()


# =============================
# Sidebar navigation
# =============================
st.sidebar.title("ECM Automation ROI Tool")
page = st.sidebar.radio(
    "Navigation",
    [
        "1. Process Baseline",
        "2. Automation Scenario",
        "3. Investment Cost",
        "4. Results Comparison",
        "5. Sensitivity Analysis",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Master thesis prototype")
st.sidebar.info(
    "This app evaluates whether automating the Engineering Change Management (ECM) process is financially worthwhile by comparing a manual process with an automated scenario."
)

# Shared default inputs
manual_defaults = {
    "changes_per_year": 250,
    "engineering_hours_per_change": 6.0,
    "manager_hours_per_change": 1.5,
    "admin_hours_per_change": 2.0,
    "avg_cycle_time_days": 8.0,
    "rework_rate_pct": 18.0,
    "rework_hours_per_change": 3.0,
    "delay_cost_per_day": 120.0,
    "engineer_hourly_rate": 75.0,
    "manager_hourly_rate": 95.0,
    "admin_hourly_rate": 45.0,
}

automation_defaults = {
    "engineering_effort_reduction_pct": 20.0,
    "manager_effort_reduction_pct": 25.0,
    "admin_effort_reduction_pct": 50.0,
    "cycle_time_reduction_pct": 40.0,
    "rework_reduction_pct": 30.0,
    "workflow_automation_level": "High",
    "data_integration_level": "Medium",
    "approval_automation_level": "High",
}

investment_defaults = {
    "software_license_cost": 30000.0,
    "implementation_cost": 45000.0,
    "integration_cost": 25000.0,
    "training_cost": 8000.0,
    "internal_project_effort_cost": 15000.0,
    "annual_maintenance_cost": 12000.0,
    "analysis_horizon_years": 3,
    "discount_rate_pct": 8.0,
}

# Use session state for continuity across pages
for key, value in {**manual_defaults, **automation_defaults, **investment_defaults}.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =============================
# App guide
# =============================
with st.expander("Guide: What this app does, what problem it solves, and how to use it", expanded=True):
    st.markdown(
        """
### Purpose of the app
This prototype supports managers and decision-makers in evaluating whether investing in **ECM process automation** is financially justified.

### What problem it solves
In many companies, engineering changes are still handled through manual or semi-manual processes. This often creates high coordination effort, long approval times, rework, and delay costs. The app compares:
- the **current manual ECM process**, and
- a **future automated ECM process**

It then calculates key business metrics such as:
- annual manual process cost
- annual automated process cost
- annual savings
- ROI
- payback period
- NPV and TCO

### How to use the app
1. Start with **Process Baseline** and enter your current manual ECM process values.
2. Go to **Automation Scenario** and define the expected improvement from automation.
3. Open **Investment Cost** and enter one-time and recurring automation costs.
4. Review the output in **Results Comparison**.
5. Use **Sensitivity Analysis** to test different assumptions.

### Mandatory vs optional inputs
All current fields in this prototype are treated as **required inputs**, because the calculation model needs them to compare manual and automated scenarios consistently.

If you do not know an exact value, enter a reasonable estimate based on:
- company assumptions
- literature values
- expert judgement
- benchmark data
        """
    )

# =============================
# Page 1: Process Baseline
# =============================
if page == "1. Process Baseline":
    st.title("Process Baseline")
    st.write("Capture the current manual engineering change management process and its main cost drivers.")
    st.caption("All fields on this page are required for the current calculation logic.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Process Volume and Effort")
        st.session_state.changes_per_year = st.number_input(
            "Engineering changes per year",
            min_value=1,
            value=int(st.session_state.changes_per_year),
            step=10,
            help="Total number of engineering changes handled in one year. This drives the annual process workload and total cost volume. Required field."
        )
        st.session_state.engineering_hours_per_change = st.number_input(
            "Engineering hours per change",
            min_value=0.0,
            value=float(st.session_state.engineering_hours_per_change),
            step=0.5,
            help="Average engineering effort needed for one change in the current manual process, including review, updates, and coordination. Required field."
        )
        st.session_state.manager_hours_per_change = st.number_input(
            "Manager approval hours per change",
            min_value=0.0,
            value=float(st.session_state.manager_hours_per_change),
            step=0.5,
            help="Average management time spent per change for approvals, escalations, and review decisions. Required field."
        )
        st.session_state.admin_hours_per_change = st.number_input(
            "Admin / coordination hours per change",
            min_value=0.0,
            value=float(st.session_state.admin_hours_per_change),
            step=0.5,
            help="Average administrative or coordination effort per change, such as routing, follow-up, documentation, and status handling. Required field."
        )
        st.session_state.avg_cycle_time_days = st.number_input(
            "Average cycle time (days)",
            min_value=0.0,
            value=float(st.session_state.avg_cycle_time_days),
            step=1.0,
            help="Average end-to-end duration of one engineering change in the manual process, from request to completion. Required field."
        )

    with c2:
        st.subheader("Rates and Loss Drivers")
        st.session_state.rework_rate_pct = st.slider(
            "Rework rate (%)",
            0.0,
            100.0,
            float(st.session_state.rework_rate_pct),
            step=1.0,
            help="Estimated share of changes that require rework because of missing information, errors, or poor coordination. Required field."
        )
        st.session_state.rework_hours_per_change = st.number_input(
            "Rework hours per affected change",
            min_value=0.0,
            value=float(st.session_state.rework_hours_per_change),
            step=0.5,
            help="Average extra engineering effort required when a change must be corrected or repeated. Required field."
        )
        st.session_state.delay_cost_per_day = st.number_input(
            "Delay cost per day (€)",
            min_value=0.0,
            value=float(st.session_state.delay_cost_per_day),
            step=10.0,
            help="Estimated cost impact of one additional day of delay in the ECM process. This can reflect coordination overhead, waiting time, or business impact. Required field."
        )
        st.session_state.engineer_hourly_rate = st.number_input(
            "Engineer hourly rate (€)",
            min_value=0.0,
            value=float(st.session_state.engineer_hourly_rate),
            step=5.0,
            help="Average loaded hourly rate for engineering staff involved in processing changes. Required field."
        )
        st.session_state.manager_hourly_rate = st.number_input(
            "Manager hourly rate (€)",
            min_value=0.0,
            value=float(st.session_state.manager_hourly_rate),
            step=5.0,
            help="Average loaded hourly rate for managers or approvers participating in the ECM process. Required field."
        )
        st.session_state.admin_hourly_rate = st.number_input(
            "Admin hourly rate (€)",
            min_value=0.0,
            value=float(st.session_state.admin_hourly_rate),
            step=5.0,
            help="Average loaded hourly rate for administrative or coordinating roles. Required field."
        )

    manual_inputs = ManualProcessInputs(
        changes_per_year=st.session_state.changes_per_year,
        engineering_hours_per_change=st.session_state.engineering_hours_per_change,
        manager_hours_per_change=st.session_state.manager_hours_per_change,
        admin_hours_per_change=st.session_state.admin_hours_per_change,
        avg_cycle_time_days=st.session_state.avg_cycle_time_days,
        rework_rate_pct=st.session_state.rework_rate_pct,
        rework_hours_per_change=st.session_state.rework_hours_per_change,
        delay_cost_per_day=st.session_state.delay_cost_per_day,
        engineer_hourly_rate=st.session_state.engineer_hourly_rate,
        manager_hourly_rate=st.session_state.manager_hourly_rate,
        admin_hourly_rate=st.session_state.admin_hourly_rate,
    )
    manual_costs = calculate_manual_costs(manual_inputs)

    st.subheader("Current Manual ECM Cost Baseline")
    m1, m2, m3 = st.columns(3)
    m1.metric("Annual labor cost", eur(manual_costs["annual_engineering_cost"] + manual_costs["annual_manager_cost"] + manual_costs["annual_admin_cost"]))
    m2.metric("Annual rework cost", eur(manual_costs["annual_rework_cost"]))
    m3.metric("Annual delay cost", eur(manual_costs["annual_delay_cost"]))
    st.metric("Total annual manual ECM cost", eur(manual_costs["total_manual_cost"]))


# =============================
# Page 2: Automation Scenario
# =============================
elif page == "2. Automation Scenario":
    st.title("Automation Scenario")
    st.write("Define the automation levers and expected process improvements for the future-state ECM process.")
    st.caption("All fields on this page are required for the current calculation logic.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Improvement Assumptions")
        st.session_state.engineering_effort_reduction_pct = st.slider(
            "Engineering effort reduction (%)",
            0.0,
            100.0,
            float(st.session_state.engineering_effort_reduction_pct),
            step=1.0,
            help="Expected percentage reduction in engineering effort per change after automation. Required field."
        )
        st.session_state.manager_effort_reduction_pct = st.slider(
            "Manager effort reduction (%)",
            0.0,
            100.0,
            float(st.session_state.manager_effort_reduction_pct),
            step=1.0,
            help="Expected percentage reduction in approval or review effort for managers after automation. Required field."
        )
        st.session_state.admin_effort_reduction_pct = st.slider(
            "Admin effort reduction (%)",
            0.0,
            100.0,
            float(st.session_state.admin_effort_reduction_pct),
            step=1.0,
            help="Expected percentage reduction in coordination and administrative effort after automation. Required field."
        )
        st.session_state.cycle_time_reduction_pct = st.slider(
            "Cycle-time reduction (%)",
            0.0,
            100.0,
            float(st.session_state.cycle_time_reduction_pct),
            step=1.0,
            help="Expected percentage reduction in overall ECM lead time due to workflow automation, transparency, and faster routing. Required field."
        )
        st.session_state.rework_reduction_pct = st.slider(
            "Rework reduction (%)",
            0.0,
            100.0,
            float(st.session_state.rework_reduction_pct),
            step=1.0,
            help="Expected percentage reduction in rework caused by better data quality, templates, traceability, or automated routing. Required field."
        )

    with c2:
        st.subheader("Automation Levers")
        st.session_state.workflow_automation_level = st.selectbox(
            "Workflow automation level",
            ["Low", "Medium", "High"],
            index=["Low", "Medium", "High"].index(st.session_state.workflow_automation_level),
            help="Qualitative assessment of how strongly workflow routing, status handling, and process orchestration are automated. Required field."
        )
        st.session_state.data_integration_level = st.selectbox(
            "Data integration level",
            ["Low", "Medium", "High"],
            index=["Low", "Medium", "High"].index(st.session_state.data_integration_level),
            help="Qualitative assessment of how well the automated ECM solution integrates with PLM, ERP, or related data sources. Required field."
        )
        st.session_state.approval_automation_level = st.selectbox(
            "Approval automation level",
            ["Low", "Medium", "High"],
            index=["Low", "Medium", "High"].index(st.session_state.approval_automation_level),
            help="Qualitative assessment of how much the approval process is standardized, auto-routed, and digitally supported. Required field."
        )

        score, label = automation_maturity_score(
            st.session_state.workflow_automation_level,
            st.session_state.data_integration_level,
            st.session_state.approval_automation_level,
        )
        st.markdown(
            f"<div style='background:{level_badge(label)};padding:16px;border-radius:12px;border:1px solid #e5e7eb;'>"
            f"<strong>Automation maturity:</strong> {label} ({score:.2f}/3.00)"
            f"</div>",
            unsafe_allow_html=True,
        )


# =============================
# Page 3: Investment Cost
# =============================
elif page == "3. Investment Cost":
    st.title("Investment Cost")
    st.write("Capture the one-time and recurring costs of implementing ECM automation.")
    st.caption("All fields on this page are required for the current calculation logic.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Upfront Investment")
        st.session_state.software_license_cost = st.number_input(
            "Software / license cost (€)",
            min_value=0.0,
            value=float(st.session_state.software_license_cost),
            step=1000.0,
            help="Initial software or license expenditure required for the automation solution. Required field."
        )
        st.session_state.implementation_cost = st.number_input(
            "Implementation / configuration cost (€)",
            min_value=0.0,
            value=float(st.session_state.implementation_cost),
            step=1000.0,
            help="Cost for setup, configuration, workflow design, and system deployment. Required field."
        )
        st.session_state.integration_cost = st.number_input(
            "Integration cost (€)",
            min_value=0.0,
            value=float(st.session_state.integration_cost),
            step=1000.0,
            help="Cost for connecting the solution to PLM, ERP, or surrounding systems and data sources. Required field."
        )
        st.session_state.training_cost = st.number_input(
            "Training cost (€)",
            min_value=0.0,
            value=float(st.session_state.training_cost),
            step=1000.0,
            help="Cost of preparing users, approvers, and administrators to work with the automated ECM process. Required field."
        )
        st.session_state.internal_project_effort_cost = st.number_input(
            "Internal project effort cost (€)",
            min_value=0.0,
            value=float(st.session_state.internal_project_effort_cost),
            step=1000.0,
            help="Internal labor cost for subject matter experts, IT, project management, and change support during implementation. Required field."
        )

    with c2:
        st.subheader("Financial Settings")
        st.session_state.annual_maintenance_cost = st.number_input(
            "Annual maintenance cost (€)",
            min_value=0.0,
            value=float(st.session_state.annual_maintenance_cost),
            step=1000.0,
            help="Recurring yearly cost for support, maintenance, licenses, or operation of the automation solution. Required field."
        )
        st.session_state.analysis_horizon_years = st.selectbox(
            "Analysis horizon (years)",
            [1, 3, 5],
            index=[1, 3, 5].index(st.session_state.analysis_horizon_years),
            help="Time horizon over which the financial impact of automation should be evaluated. Required field."
        )
        st.session_state.discount_rate_pct = st.slider(
            "Discount rate (%)",
            0.0,
            20.0,
            float(st.session_state.discount_rate_pct),
            step=0.5,
            help="Rate used to discount future savings when calculating NPV. Required field."
        )

        upfront = (
            st.session_state.software_license_cost
            + st.session_state.implementation_cost
            + st.session_state.integration_cost
            + st.session_state.training_cost
            + st.session_state.internal_project_effort_cost
        )
        st.markdown(
            f"<div style='background:#f8fafc;padding:16px;border-radius:12px;border:1px solid #e5e7eb;'>"
            f"<strong>Total upfront investment:</strong> {eur(upfront)}<br>"
            f"<strong>Annual maintenance:</strong> {eur(st.session_state.annual_maintenance_cost)}"
            f"</div>",
            unsafe_allow_html=True,
        )


# =============================
# Build shared objects for results pages
# =============================
manual_inputs = ManualProcessInputs(
    changes_per_year=st.session_state.changes_per_year,
    engineering_hours_per_change=st.session_state.engineering_hours_per_change,
    manager_hours_per_change=st.session_state.manager_hours_per_change,
    admin_hours_per_change=st.session_state.admin_hours_per_change,
    avg_cycle_time_days=st.session_state.avg_cycle_time_days,
    rework_rate_pct=st.session_state.rework_rate_pct,
    rework_hours_per_change=st.session_state.rework_hours_per_change,
    delay_cost_per_day=st.session_state.delay_cost_per_day,
    engineer_hourly_rate=st.session_state.engineer_hourly_rate,
    manager_hourly_rate=st.session_state.manager_hourly_rate,
    admin_hourly_rate=st.session_state.admin_hourly_rate,
)

automation_inputs = AutomationScenarioInputs(
    engineering_effort_reduction_pct=st.session_state.engineering_effort_reduction_pct,
    manager_effort_reduction_pct=st.session_state.manager_effort_reduction_pct,
    admin_effort_reduction_pct=st.session_state.admin_effort_reduction_pct,
    cycle_time_reduction_pct=st.session_state.cycle_time_reduction_pct,
    rework_reduction_pct=st.session_state.rework_reduction_pct,
    workflow_automation_level=st.session_state.workflow_automation_level,
    data_integration_level=st.session_state.data_integration_level,
    approval_automation_level=st.session_state.approval_automation_level,
)

investment_inputs = InvestmentInputs(
    software_license_cost=st.session_state.software_license_cost,
    implementation_cost=st.session_state.implementation_cost,
    integration_cost=st.session_state.integration_cost,
    training_cost=st.session_state.training_cost,
    internal_project_effort_cost=st.session_state.internal_project_effort_cost,
    annual_maintenance_cost=st.session_state.annual_maintenance_cost,
    analysis_horizon_years=st.session_state.analysis_horizon_years,
    discount_rate_pct=st.session_state.discount_rate_pct,
)

results = calculate_financials(manual_inputs, automation_inputs, investment_inputs)


# =============================
# Page 4: Results Comparison
# =============================
if page == "4. Results Comparison":
    st.title("Results Comparison")
    st.write("Compare the current manual ECM process with the automated ECM scenario and assess the investment case.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Manual annual cost", eur(results["total_manual_cost"]))
    k2.metric("Automated annual cost", eur(results["total_automated_operating_cost"]))
    k3.metric("Annual savings", eur(results["annual_savings"]))
    k4.metric("Upfront investment", eur(results["upfront_investment"]))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("ROI", pct(results["roi_pct"]))
    k6.metric("Payback", "N/A" if results["payback_months"] is None else f"{results['payback_months']:.1f} mo")
    k7.metric("NPV", eur(results["npv"]))
    k8.metric("Decision", results["decision"])

    compare_df = pd.DataFrame(
        {
            "Category": ["Manual annual cost", "Automated annual cost", "Annual savings", "Upfront investment"],
            "Value": [
                results["total_manual_cost"],
                results["total_automated_operating_cost"],
                results["annual_savings"],
                results["upfront_investment"],
            ],
        }
    ).set_index("Category")
    st.subheader("Financial comparison")
    st.bar_chart(compare_df)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Manual vs automated process cost structure")
        cost_breakdown = pd.DataFrame(
            {
                "Manual": [
                    results["annual_engineering_cost"],
                    results["annual_manager_cost"],
                    results["annual_admin_cost"],
                    results["annual_rework_cost"],
                    results["annual_delay_cost"],
                ],
                "Automated": [
                    results["automated_engineering_cost"],
                    results["automated_manager_cost"],
                    results["automated_admin_cost"],
                    results["automated_rework_cost"],
                    results["automated_delay_cost"],
                ],
            },
            index=["Engineering", "Manager", "Admin", "Rework", "Delay"],
        )
        st.dataframe(cost_breakdown.style.format("€{:,.0f}"), use_container_width=True)

    with c2:
        st.subheader("Decision summary")
        bg = "#e8f5e9" if results["decision"] == "Go" else "#fff8e1" if results["decision"] == "Review" else "#ffebee"
        st.markdown(
            f"<div style='background:{bg};padding:18px;border-radius:12px;border:1px solid #e5e7eb;'>"
            f"<h3 style='margin-top:0'>{results['decision']}</h3>"
            f"<p>{results['rationale']}</p>"
            f"<p><strong>{investment_inputs.analysis_horizon_years}-year manual TCO:</strong> {eur(results['tco_manual'])}</p>"
            f"<p><strong>{investment_inputs.analysis_horizon_years}-year automated TCO:</strong> {eur(results['tco_automated'])}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Manager interpretation")
    st.write(
        f"Under the current assumptions, the manual ECM process costs {eur(results['total_manual_cost'])} per year. "
        f"The automated scenario reduces annual operating cost to {eur(results['total_automated_operating_cost'])}, "
        f"creating annual savings of {eur(results['annual_savings'])}. The required upfront investment is "
        f"{eur(results['upfront_investment'])}, resulting in an ROI of {pct(results['roi_pct'])} and a payback period of "
        f"{'N/A' if results['payback_months'] is None else f'{results['payback_months']:.1f} months'} over a {investment_inputs.analysis_horizon_years}-year horizon."
    )


# =============================
# Page 5: Sensitivity Analysis
# =============================
if page == "5. Sensitivity Analysis":
    st.title("Sensitivity Analysis")
    st.write("Stress-test the business case under different assumptions for process volume, savings impact, and investment size.")

    col1, col2, col3 = st.columns(3)
    with col1:
        sim_changes = st.slider("Changes per year", 50, 1000, int(st.session_state.changes_per_year), step=10)
    with col2:
        sim_cycle_reduction = st.slider("Cycle-time reduction (%)", 0, 100, int(st.session_state.cycle_time_reduction_pct), step=1)
    with col3:
        sim_upfront_investment = st.slider(
            "Upfront investment (€)",
            10000,
            300000,
            int(results["upfront_investment"]),
            step=5000,
        )

    sim_manual = ManualProcessInputs(
        changes_per_year=sim_changes,
        engineering_hours_per_change=manual_inputs.engineering_hours_per_change,
        manager_hours_per_change=manual_inputs.manager_hours_per_change,
        admin_hours_per_change=manual_inputs.admin_hours_per_change,
        avg_cycle_time_days=manual_inputs.avg_cycle_time_days,
        rework_rate_pct=manual_inputs.rework_rate_pct,
        rework_hours_per_change=manual_inputs.rework_hours_per_change,
        delay_cost_per_day=manual_inputs.delay_cost_per_day,
        engineer_hourly_rate=manual_inputs.engineer_hourly_rate,
        manager_hourly_rate=manual_inputs.manager_hourly_rate,
        admin_hourly_rate=manual_inputs.admin_hourly_rate,
    )

    sim_auto = AutomationScenarioInputs(
        engineering_effort_reduction_pct=automation_inputs.engineering_effort_reduction_pct,
        manager_effort_reduction_pct=automation_inputs.manager_effort_reduction_pct,
        admin_effort_reduction_pct=automation_inputs.admin_effort_reduction_pct,
        cycle_time_reduction_pct=float(sim_cycle_reduction),
        rework_reduction_pct=automation_inputs.rework_reduction_pct,
        workflow_automation_level=automation_inputs.workflow_automation_level,
        data_integration_level=automation_inputs.data_integration_level,
        approval_automation_level=automation_inputs.approval_automation_level,
    )

    sim_inv = InvestmentInputs(
        software_license_cost=float(sim_upfront_investment),
        implementation_cost=0.0,
        integration_cost=0.0,
        training_cost=0.0,
        internal_project_effort_cost=0.0,
        annual_maintenance_cost=investment_inputs.annual_maintenance_cost,
        analysis_horizon_years=investment_inputs.analysis_horizon_years,
        discount_rate_pct=investment_inputs.discount_rate_pct,
    )

    sim_results = calculate_financials(sim_manual, sim_auto, sim_inv)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Simulated annual savings", eur(sim_results["annual_savings"]))
    s2.metric("Simulated ROI", pct(sim_results["roi_pct"]))
    s3.metric("Simulated payback", "N/A" if sim_results["payback_months"] is None else f"{sim_results['payback_months']:.1f} mo")
    s4.metric("Decision", sim_results["decision"])

    sensitivity_df = pd.DataFrame(
        {
            "Metric": ["Manual annual cost", "Automated annual cost", "Annual savings", "Upfront investment", "NPV"],
            "Value": [
                sim_results["total_manual_cost"],
                sim_results["total_automated_operating_cost"],
                sim_results["annual_savings"],
                sim_results["upfront_investment"],
                sim_results["npv"],
            ],
        }
    ).set_index("Metric")
    st.bar_chart(sensitivity_df)

    st.write(
        f"With {sim_changes} changes per year, a cycle-time reduction of {sim_cycle_reduction}%, and an upfront investment of "
        f"{eur(sim_upfront_investment)}, the model produces {eur(sim_results['annual_savings'])} in annual savings. "
        f"This results in {pct(sim_results['roi_pct'])} ROI and a decision of **{sim_results['decision']}**."
    )
