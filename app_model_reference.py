import streamlit as st
import pandas as pd
from dataclasses import dataclass


st.set_page_config(
    page_title="ECM Automation ROI Tool",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================
# Thesis model inputs
# =============================
@dataclass
class BaselineInputs:
    changes_per_year: int
    engineering_hours_per_change: float
    manager_hours_per_change: float
    admin_hours_per_change: float
    engineer_hourly_rate: float
    manager_hourly_rate: float
    admin_hourly_rate: float
    rework_rate_pct: float
    rework_hours_per_event: float
    delay_cost_per_day: float
    manual_cycle_time_days: float
    discount_rate_pct: float
    analysis_horizon_years: int


@dataclass
class ScenarioInputs:
    engineering_effort_reduction_pct: float
    manager_effort_reduction_pct: float
    admin_effort_reduction_pct: float
    rework_reduction_pct: float
    cycle_time_reduction_pct: float
    upfront_investment: float
    annual_operating_cost: float


SCENARIOS = {
    "Conservative": ScenarioInputs(30.0, 25.0, 40.0, 20.0, 30.0, 150000.0, 75000.0),
    "Base Case": ScenarioInputs(45.0, 40.0, 55.0, 40.0, 50.0, 215000.0, 111600.0),
    "Optimistic": ScenarioInputs(65.0, 60.0, 75.0, 65.0, 75.0, 350000.0, 160000.0),
}


# =============================
# UI helpers
# =============================
def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f7fafc 0%, #eef4f7 100%);
            color: #182230;
        }
        .block-container {
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        section[data-testid="stSidebar"] {
            background: #102b36;
        }
        section[data-testid="stSidebar"] * {
            color: #eff8f8;
        }
        .hero {
            background: linear-gradient(135deg, #0f5f66 0%, #112f3b 100%);
            border-radius: 18px;
            padding: 30px 34px;
            color: white;
            box-shadow: 0 24px 60px rgba(15, 47, 59, 0.20);
            margin-bottom: 24px;
        }
        .hero h1 {
            color: white;
            margin: 0 0 8px;
            font-size: 2.15rem;
        }
        .hero p {
            color: rgba(255,255,255,0.84);
            margin: 0;
            max-width: 900px;
            line-height: 1.55;
        }
        .eyebrow {
            color: #bceee8;
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }
        .panel {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 16px 38px rgba(17, 47, 59, 0.07);
            margin-bottom: 18px;
        }
        .kpi {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 15px;
            padding: 18px;
            box-shadow: 0 14px 34px rgba(17, 47, 59, 0.08);
            min-height: 124px;
        }
        .kpi .label {
            color: #65758b;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 800;
        }
        .kpi .value {
            color: #182230;
            font-size: 1.55rem;
            font-weight: 850;
            margin-top: 8px;
            line-height: 1.15;
        }
        .kpi .note {
            color: #65758b;
            font-size: 0.88rem;
            margin-top: 8px;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 15px;
            padding: 16px;
            box-shadow: 0 12px 30px rgba(17, 47, 59, 0.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "Chapter 5 decision-support prototype") -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div class="eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="kpi">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def eur(value: float) -> str:
    return f"EUR {value:,.0f}"


def pct(value: float) -> str:
    return f"{value:,.1f}%"


def years(value: float | None) -> str:
    return "N/A" if value is None else f"{value:,.2f} years"


def number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:,.0f}"


# =============================
# Calculation model
# =============================
def annuity_factor(discount_rate_pct: float, horizon_years: int) -> float:
    """A = (1 - (1+r)^(-T_h)) / r."""
    r = discount_rate_pct / 100
    if horizon_years <= 0:
        return 0
    if r == 0:
        return float(horizon_years)
    return (1 - (1 + r) ** (-horizon_years)) / r


def baseline_components_per_change(b: BaselineInputs) -> dict:
    """Manual cost components per engineering change."""
    engineering = b.engineering_hours_per_change * b.engineer_hourly_rate
    manager = b.manager_hours_per_change * b.manager_hourly_rate
    admin = b.admin_hours_per_change * b.admin_hourly_rate
    rework = (b.rework_rate_pct / 100) * b.rework_hours_per_event * b.engineer_hourly_rate
    delay = b.delay_cost_per_day * b.manual_cycle_time_days
    return {
        "engineering": engineering,
        "manager": manager,
        "admin": admin,
        "rework": rework,
        "delay": delay,
    }


def savings_per_change(b: BaselineInputs, s: ScenarioInputs, include_delay: bool) -> dict:
    """Per-change gross process savings before annual operating cost."""
    manual = baseline_components_per_change(b)
    engineering = manual["engineering"] * s.engineering_effort_reduction_pct / 100
    manager = manual["manager"] * s.manager_effort_reduction_pct / 100
    admin = manual["admin"] * s.admin_effort_reduction_pct / 100
    rework = manual["rework"] * s.rework_reduction_pct / 100
    delay = manual["delay"] * s.cycle_time_reduction_pct / 100 if include_delay else 0
    total = engineering + manager + admin + rework + delay
    return {
        "engineering": engineering,
        "manager": manager,
        "admin": admin,
        "rework": rework,
        "delay": delay,
        "total": total,
    }


def calculate_model(b: BaselineInputs, s: ScenarioInputs, include_delay: bool) -> dict:
    """
    Calculates either:
    - full model: labour + rework + delay, including annual operating cost, or
    - labour-only net model: labour + rework, excluding delay but including annual operating cost.
    """
    manual = baseline_components_per_change(b)
    spc = savings_per_change(b, s, include_delay=include_delay)

    manual_per_change = manual["engineering"] + manual["manager"] + manual["admin"] + manual["rework"]
    if include_delay:
        manual_per_change += manual["delay"]

    gross_process_savings = b.changes_per_year * spc["total"]
    manual_annual_cost = b.changes_per_year * manual_per_change
    automated_annual_cost = manual_annual_cost - gross_process_savings + s.annual_operating_cost
    annual_net_savings = manual_annual_cost - automated_annual_cost

    a_factor = annuity_factor(b.discount_rate_pct, b.analysis_horizon_years)
    npv = -s.upfront_investment + annual_net_savings * a_factor
    roi_pct = (((annual_net_savings * b.analysis_horizon_years) - s.upfront_investment) / s.upfront_investment * 100) if s.upfront_investment > 0 else 0
    payback_years = s.upfront_investment / annual_net_savings if annual_net_savings > 0 else None
    tco_manual = manual_annual_cost * b.analysis_horizon_years
    tco_automated = s.upfront_investment + automated_annual_cost * b.analysis_horizon_years
    tco_saving = tco_manual - tco_automated

    # Break-even volume: N_be = (I_0 + C_op x A) / (s_per_change x A)
    if spc["total"] <= 0 or a_factor <= 0:
        break_even_changes = None
    else:
        break_even_changes = (s.upfront_investment + s.annual_operating_cost * a_factor) / (spc["total"] * a_factor)

    return {
        "manual_annual_cost": manual_annual_cost,
        "automated_annual_cost": automated_annual_cost,
        "gross_process_savings": gross_process_savings,
        "annual_net_savings": annual_net_savings,
        "roi_pct": roi_pct,
        "payback_years": payback_years,
        "npv": npv,
        "tco_manual": tco_manual,
        "tco_automated": tco_automated,
        "tco_saving": tco_saving,
        "break_even_changes": break_even_changes,
        "saving_per_change": spc["total"],
        "engineering_saving_per_change": spc["engineering"],
        "manager_saving_per_change": spc["manager"],
        "admin_saving_per_change": spc["admin"],
        "rework_saving_per_change": spc["rework"],
        "delay_saving_per_change": spc["delay"],
    }


def scenario_comparison_table(b: BaselineInputs, include_delay: bool) -> pd.DataFrame:
    rows = []
    for name, scenario in SCENARIOS.items():
        r = calculate_model(b, scenario, include_delay=include_delay)
        rows.append(
            {
                "Scenario": name,
                "Manual annual cost": r["manual_annual_cost"],
                "Automated annual cost": r["automated_annual_cost"],
                "Annual savings": r["annual_net_savings"],
                "ROI": r["roi_pct"],
                "Payback": r["payback_years"],
                "NPV": r["npv"],
                "TCO saving": r["tco_saving"],
                "Break-even changes/year": r["break_even_changes"],
            }
        )
    return pd.DataFrame(rows).set_index("Scenario")


def format_financial_table(df: pd.DataFrame):
    return df.style.format(
        {
            "Manual annual cost": "EUR {:,.0f}",
            "Automated annual cost": "EUR {:,.0f}",
            "Annual savings": "EUR {:,.0f}",
            "ROI": "{:,.1f}%",
            "Payback": "{:,.2f}",
            "NPV": "EUR {:,.0f}",
            "TCO saving": "EUR {:,.0f}",
            "Break-even changes/year": "{:,.0f}",
        },
        na_rep="N/A",
    )


# =============================
# State
# =============================
def init_state() -> None:
    defaults = {
        "changes_per_year": 500,
        "engineering_hours_per_change": 10.0,
        "manager_hours_per_change": 1.0,
        "admin_hours_per_change": 2.0,
        "engineer_hourly_rate": 85.0,
        "manager_hourly_rate": 100.0,
        "admin_hourly_rate": 55.0,
        "rework_rate_pct": 20.0,
        "rework_hours_per_event": 4.0,
        "delay_cost_per_day": 500.0,
        "manual_cycle_time_days": 15.0,
        "discount_rate_pct": 10.0,
        "analysis_horizon_years": 5,
        "scenario_name": "Base Case",
        "custom_engineering_effort_reduction_pct": 45.0,
        "custom_manager_effort_reduction_pct": 40.0,
        "custom_admin_effort_reduction_pct": 55.0,
        "custom_rework_reduction_pct": 40.0,
        "custom_cycle_time_reduction_pct": 50.0,
        "custom_upfront_investment": 215000.0,
        "custom_annual_operating_cost": 111600.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_baseline() -> BaselineInputs:
    return BaselineInputs(
        changes_per_year=st.session_state.changes_per_year,
        engineering_hours_per_change=st.session_state.engineering_hours_per_change,
        manager_hours_per_change=st.session_state.manager_hours_per_change,
        admin_hours_per_change=st.session_state.admin_hours_per_change,
        engineer_hourly_rate=st.session_state.engineer_hourly_rate,
        manager_hourly_rate=st.session_state.manager_hourly_rate,
        admin_hourly_rate=st.session_state.admin_hourly_rate,
        rework_rate_pct=st.session_state.rework_rate_pct,
        rework_hours_per_event=st.session_state.rework_hours_per_event,
        delay_cost_per_day=st.session_state.delay_cost_per_day,
        manual_cycle_time_days=st.session_state.manual_cycle_time_days,
        discount_rate_pct=st.session_state.discount_rate_pct,
        analysis_horizon_years=st.session_state.analysis_horizon_years,
    )


def get_selected_scenario() -> ScenarioInputs:
    if st.session_state.scenario_name != "Custom":
        return SCENARIOS[st.session_state.scenario_name]
    return ScenarioInputs(
        engineering_effort_reduction_pct=st.session_state.custom_engineering_effort_reduction_pct,
        manager_effort_reduction_pct=st.session_state.custom_manager_effort_reduction_pct,
        admin_effort_reduction_pct=st.session_state.custom_admin_effort_reduction_pct,
        rework_reduction_pct=st.session_state.custom_rework_reduction_pct,
        cycle_time_reduction_pct=st.session_state.custom_cycle_time_reduction_pct,
        upfront_investment=st.session_state.custom_upfront_investment,
        annual_operating_cost=st.session_state.custom_annual_operating_cost,
    )


apply_theme()
init_state()


# =============================
# Sidebar
# =============================
st.sidebar.title("ECM ROI Tool")
st.sidebar.caption("MBA thesis Chapter 5 prototype")
page = st.sidebar.radio(
    "Navigation",
    [
        "Model Inputs",
        "Results",
        "Scenario Comparison",
        "Assumptions & Model Logic",
        "Formula Explanation",
    ],
)
st.sidebar.markdown("---")
st.sidebar.info(
    "Decision-support prototype for measuring ROI of ECM automation. It is not PLM software and not a process optimisation system."
)


baseline = get_baseline()
scenario = get_selected_scenario()
full_results = calculate_model(baseline, scenario, include_delay=True)
labour_results = calculate_model(baseline, scenario, include_delay=False)


# =============================
# Model Inputs
# =============================
if page == "Model Inputs":
    hero(
        "ECM Automation ROI Decision Model",
        "Enter the manual ECM baseline, choose a scenario, and evaluate the financial case for process automation.",
    )

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Manual ECM Baseline")
        st.session_state.changes_per_year = st.number_input("Annual change volume N", min_value=1, value=int(st.session_state.changes_per_year), step=25)
        st.session_state.engineering_hours_per_change = st.number_input("Engineering hours per change", min_value=0.0, value=float(st.session_state.engineering_hours_per_change), step=0.5)
        st.session_state.manager_hours_per_change = st.number_input("Manager approval hours per change", min_value=0.0, value=float(st.session_state.manager_hours_per_change), step=0.5)
        st.session_state.admin_hours_per_change = st.number_input("Admin / coordination hours per change", min_value=0.0, value=float(st.session_state.admin_hours_per_change), step=0.5)
        st.session_state.rework_rate_pct = st.slider("Rework rate (%)", 0.0, 100.0, float(st.session_state.rework_rate_pct), step=1.0)
        st.session_state.rework_hours_per_event = st.number_input("Rework hours per event", min_value=0.0, value=float(st.session_state.rework_hours_per_event), step=0.5)
        st.session_state.manual_cycle_time_days = st.number_input("Manual cycle time (days)", min_value=0.0, value=float(st.session_state.manual_cycle_time_days), step=1.0)
        st.session_state.delay_cost_per_day = st.number_input("Delay cost per ECO per day (EUR)", min_value=0.0, value=float(st.session_state.delay_cost_per_day), step=50.0)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Rates and Financial Settings")
        st.session_state.engineer_hourly_rate = st.number_input("Engineer hourly rate (EUR)", min_value=0.0, value=float(st.session_state.engineer_hourly_rate), step=5.0)
        st.session_state.manager_hourly_rate = st.number_input("Manager hourly rate (EUR)", min_value=0.0, value=float(st.session_state.manager_hourly_rate), step=5.0)
        st.session_state.admin_hourly_rate = st.number_input("Admin hourly rate (EUR)", min_value=0.0, value=float(st.session_state.admin_hourly_rate), step=5.0)
        st.session_state.discount_rate_pct = st.slider("Discount rate (%)", 0.0, 25.0, float(st.session_state.discount_rate_pct), step=0.5)
        st.session_state.analysis_horizon_years = st.selectbox("Analysis horizon (years)", [1, 3, 5, 7, 10], index=[1, 3, 5, 7, 10].index(st.session_state.analysis_horizon_years))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Scenario Selection")
    st.session_state.scenario_name = st.selectbox(
        "Automation scenario",
        ["Conservative", "Base Case", "Optimistic", "Custom"],
        index=["Conservative", "Base Case", "Optimistic", "Custom"].index(st.session_state.scenario_name),
    )

    if st.session_state.scenario_name == "Custom":
        a, b, c, d = st.columns(4)
        with a:
            st.session_state.custom_engineering_effort_reduction_pct = st.slider("Engineering reduction (%)", 0.0, 100.0, float(st.session_state.custom_engineering_effort_reduction_pct), step=1.0)
            st.session_state.custom_manager_effort_reduction_pct = st.slider("Manager reduction (%)", 0.0, 100.0, float(st.session_state.custom_manager_effort_reduction_pct), step=1.0)
        with b:
            st.session_state.custom_admin_effort_reduction_pct = st.slider("Admin reduction (%)", 0.0, 100.0, float(st.session_state.custom_admin_effort_reduction_pct), step=1.0)
            st.session_state.custom_rework_reduction_pct = st.slider("Rework reduction (%)", 0.0, 100.0, float(st.session_state.custom_rework_reduction_pct), step=1.0)
        with c:
            st.session_state.custom_cycle_time_reduction_pct = st.slider("Cycle-time reduction (%)", 0.0, 100.0, float(st.session_state.custom_cycle_time_reduction_pct), step=1.0)
        with d:
            st.session_state.custom_upfront_investment = st.number_input("Upfront investment (EUR)", min_value=0.0, value=float(st.session_state.custom_upfront_investment), step=5000.0)
            st.session_state.custom_annual_operating_cost = st.number_input("Annual operating cost (EUR)", min_value=0.0, value=float(st.session_state.custom_annual_operating_cost), step=5000.0)
    else:
        selected = SCENARIOS[st.session_state.scenario_name]
        scenario_df = pd.DataFrame(
            {
                "Parameter": [
                    "Engineering effort reduction",
                    "Manager effort reduction",
                    "Admin effort reduction",
                    "Rework reduction",
                    "Cycle-time reduction",
                    "Upfront investment",
                    "Annual operating cost",
                ],
                "Value": [
                    pct(selected.engineering_effort_reduction_pct),
                    pct(selected.manager_effort_reduction_pct),
                    pct(selected.admin_effort_reduction_pct),
                    pct(selected.rework_reduction_pct),
                    pct(selected.cycle_time_reduction_pct),
                    eur(selected.upfront_investment),
                    eur(selected.annual_operating_cost),
                ],
            }
        )
        st.dataframe(scenario_df, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =============================
# Results
# =============================
if page == "Results":
    hero(
        "Financial Results",
        "Full model includes delay cost. Labour-only net model excludes delay cost but still includes annual system operating cost.",
        "Selected scenario results",
    )

    selected_name = st.session_state.scenario_name
    st.subheader(f"Selected Scenario: {selected_name}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Full annual net savings", eur(full_results["annual_net_savings"]), "Includes delay savings and operating cost")
    with c2:
        kpi_card("Full ROI", pct(full_results["roi_pct"]), f"Payback: {years(full_results['payback_years'])}")
    with c3:
        kpi_card("Labour-only net savings", eur(labour_results["annual_net_savings"]), "Excludes delay, includes operating cost")
    with c4:
        kpi_card("Labour-only ROI", pct(labour_results["roi_pct"]), f"Payback: {years(labour_results['payback_years'])}")

    full_tab, labour_tab = st.tabs(["Full Model", "Labour-Only Net Model"])

    with full_tab:
        metrics = pd.DataFrame(
            {
                "Metric": [
                    "Manual annual cost",
                    "Automated annual cost",
                    "Annual net savings",
                    "ROI",
                    "Payback period",
                    "NPV",
                    "TCO manual",
                    "TCO automated",
                    "TCO saving",
                    "Break-even changes/year",
                ],
                "Value": [
                    eur(full_results["manual_annual_cost"]),
                    eur(full_results["automated_annual_cost"]),
                    eur(full_results["annual_net_savings"]),
                    pct(full_results["roi_pct"]),
                    years(full_results["payback_years"]),
                    eur(full_results["npv"]),
                    eur(full_results["tco_manual"]),
                    eur(full_results["tco_automated"]),
                    eur(full_results["tco_saving"]),
                    number(full_results["break_even_changes"]),
                ],
            }
        )
        st.dataframe(metrics, use_container_width=True, hide_index=True)

    with labour_tab:
        metrics = pd.DataFrame(
            {
                "Metric": [
                    "Manual labour-only cost",
                    "Automated labour-only cost",
                    "Gross labour/rework process savings",
                    "Labour-only net savings",
                    "ROI",
                    "Payback period",
                    "NPV",
                    "TCO manual",
                    "TCO automated",
                    "TCO saving",
                    "Break-even changes/year",
                ],
                "Value": [
                    eur(labour_results["manual_annual_cost"]),
                    eur(labour_results["automated_annual_cost"]),
                    eur(labour_results["gross_process_savings"]),
                    eur(labour_results["annual_net_savings"]),
                    pct(labour_results["roi_pct"]),
                    years(labour_results["payback_years"]),
                    eur(labour_results["npv"]),
                    eur(labour_results["tco_manual"]),
                    eur(labour_results["tco_automated"]),
                    eur(labour_results["tco_saving"]),
                    number(labour_results["break_even_changes"]),
                ],
            }
        )
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        st.info(
            "Labour-only net savings subtract annual operating cost. This prevents ROI, payback, NPV, TCO, and break-even from being overstated."
        )


# =============================
# Scenario Comparison
# =============================
if page == "Scenario Comparison":
    hero(
        "Scenario Comparison",
        "Conservative, Base Case, and Optimistic scenarios are recalculated side by side using the same formulas.",
    )

    full_df = scenario_comparison_table(baseline, include_delay=True)
    labour_df = scenario_comparison_table(baseline, include_delay=False)

    st.subheader("Full Model: Labour, Rework, Delay, and Annual Operating Cost")
    st.dataframe(format_financial_table(full_df), use_container_width=True)

    st.subheader("Labour-Only Net Model: Labour, Rework, and Annual Operating Cost")
    st.dataframe(format_financial_table(labour_df), use_container_width=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Consistency Check")
    base_full = full_df.loc["Base Case"]
    base_labour = labour_df.loc["Base Case"]
    st.write(
        f"With the default Chapter 5 baseline, the Base Case full model produces manual annual cost of "
        f"{eur(base_full['Manual annual cost'])}, automated annual cost of {eur(base_full['Automated annual cost'])}, "
        f"and annual savings of {eur(base_full['Annual savings'])}."
    )
    st.write(
        f"The Base Case labour-only net model separates gross process savings of "
        f"{eur(calculate_model(baseline, SCENARIOS['Base Case'], include_delay=False)['gross_process_savings'])} "
        f"from net savings of {eur(base_labour['Annual savings'])} after annual operating cost."
    )
    st.markdown("</div>", unsafe_allow_html=True)


# =============================
# Assumptions & Model Logic
# =============================
if page == "Assumptions & Model Logic":
    hero(
        "Assumptions & Model Logic",
        "The app is a transparent thesis prototype for ROI measurement, not a PLM system or production optimisation tool.",
    )

    rows = [
        ("Purpose", "Decision-support prototype for measuring the ROI of ECM automation in product development."),
        ("Full model", "Includes engineering, manager, admin, rework, delay cost, upfront investment, and annual operating cost."),
        ("Labour-only net model", "Excludes delay cost but includes annual system operating cost for a fair comparison."),
        ("Delay cost", "Most uncertain parameter because it translates time into business impact. It should be tested through sensitivity analysis or company-specific data."),
        ("Illustrative values", "Default values are representative Chapter 5 assumptions and can be replaced with company-specific ECM data."),
        ("Scenario values", "Conservative, Base Case, and Optimistic assumptions describe different expected automation impact levels."),
        ("Not included", "The app does not model PLM workflow execution, process mining, routing logic, resource scheduling, or operational optimisation."),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Topic", "Explanation"]), use_container_width=True, hide_index=True)


# =============================
# Formula Explanation
# =============================
if page == "Formula Explanation":
    hero("Formula Explanation", "Plain-English formulas used in the Chapter 5 ROI model.")

    formulas = [
        ("Manual annual ECM cost", "N x (engineering labour + manager labour + admin labour + rework cost + delay cost). In the labour-only model, delay cost is excluded."),
        ("Automated annual ECM cost", "N x reduced process cost per change + annual operating cost C_op."),
        ("Annual net savings", "Manual annual cost - automated annual cost."),
        ("ROI", "((S_annual x T_h) - I_0) / I_0 x 100."),
        ("Payback", "I_0 / S_annual. The app displays this in years."),
        ("NPV", "-I_0 + S_annual x [(1 - (1+r)^(-T_h)) / r]."),
        ("TCO manual", "Manual annual cost x analysis horizon T_h."),
        ("TCO automated", "I_0 + automated annual cost x analysis horizon T_h."),
        ("Break-even changes/year", "N_be = (I_0 + C_op x A) / (s_per_change x A), where A = [(1 - (1+r)^(-T_h)) / r]."),
        ("Full-model s_per_change", "Engineering saving + manager saving + admin saving + rework saving + delay saving."),
        ("Labour-only s_per_change", "Engineering saving + manager saving + admin saving + rework saving. Delay saving is excluded."),
    ]
    st.dataframe(pd.DataFrame(formulas, columns=["Metric", "Formula"]), use_container_width=True, hide_index=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Current Base Case Reference")
    base_full = calculate_model(baseline, SCENARIOS["Base Case"], include_delay=True)
    base_labour = calculate_model(baseline, SCENARIOS["Base Case"], include_delay=False)
    st.write(
        f"Full model Base Case: manual annual cost {eur(base_full['manual_annual_cost'])}, "
        f"automated annual cost {eur(base_full['automated_annual_cost'])}, "
        f"annual net savings {eur(base_full['annual_net_savings'])}."
    )
    st.write(
        f"Labour-only Base Case: gross labour/rework savings {eur(base_labour['gross_process_savings'])}, "
        f"net labour-only savings {eur(base_labour['annual_net_savings'])} after annual operating cost."
    )
    st.markdown("</div>", unsafe_allow_html=True)
