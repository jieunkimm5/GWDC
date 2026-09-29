import html
import textwrap

import httpx
import streamlit as st


# =========================================================
# Config
# =========================================================

API_URL = "http://127.0.0.1:8000/api/run"

DEFAULT_TASK = """
Analyze a multi-component Python backend system that includes:

1. A FastAPI API layer
2. AI model routing
3. Budget validation
4. Blockchain payment authorization
5. An external paid AI API
6. A local fallback model

Identify possible bugs, security risks, failure scenarios, and performance
bottlenecks across the entire workflow.

Explain how failures in one component can affect the others, and propose
concrete code-level and architectural improvements for making the system
reliable, secure, and cost-efficient.
""".strip()

st.set_page_config(
    page_title="Agent Finance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# Helper
# =========================================================

def md(content: str):
    cleaned = textwrap.dedent(content).strip()

    
    if "<" in cleaned and ">" in cleaned:
        cleaned = "\n".join(
            line.strip()
            for line in cleaned.splitlines()
        )

    st.markdown(
        cleaned,
        unsafe_allow_html=True,
    )


# =========================================================
# State
# =========================================================

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = "PAID"

if "task" not in st.session_state:
    st.session_state.task = DEFAULT_TASK

if "budget" not in st.session_state:
    st.session_state.budget = "0.050000"

if "result_data" not in st.session_state:
    st.session_state.result_data = None


# =========================================================
# CSS
# =========================================================

md("""
<style>

/* ---------- page ---------- */

.stApp {
    background:
        radial-gradient(circle at 90% 0%,
        rgba(49, 130, 246, 0.10),
        transparent 28%),
        #f7f9fc;
}

[data-testid="stHeader"] {
    background: transparent;
}

#MainMenu, footer {
    visibility: hidden;
}

.block-container {
    max-width: 1200px;
    padding-top: 2.2rem;
    padding-bottom: 5rem;
}

/* ---------- typography ---------- */

html, body, [class*="css"] {
    font-family:
        Pretendard,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

/* ---------- hero ---------- */

.hero {
    padding: 18px 4px 30px 4px;
}

.brand {
    display: flex;
    align-items: center;
    gap: 15px;
}

.logo-box {
    width: 58px;
    height: 58px;
    border-radius: 17px;
    display: flex;
    align-items: center;
    justify-content: center;

    background:
        linear-gradient(
            135deg,
            #4593ff,
            #2f6be5
        );

    color: white;
    font-size: 29px;

    box-shadow:
        0 10px 25px
        rgba(49, 130, 246, 0.22);
}

.brand-name {
    font-size: 45px;
    line-height: 1;
    letter-spacing: -0.045em;
    font-weight: 800;
    color: #191f28;
}

.hero-description {
    margin-top: 17px;
    color: #6b7684;
    font-size: 17px;
    line-height: 1.6;
    letter-spacing: -0.02em;
}

.features {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 20px;
}

.feature {
    background: rgba(255,255,255,0.78);
    border: 1px solid #e7ebf0;
    padding: 9px 14px;
    border-radius: 999px;

    color: #4e5968;
    font-size: 13px;
    font-weight: 600;

    box-shadow:
        0 3px 12px
        rgba(25,31,40,0.025);
}

/* ---------- bordered streamlit containers ---------- */

[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(255,255,255,0.97);
    border: 1px solid #e5eaf0 !important;
    border-radius: 24px !important;
    box-shadow:
        0 10px 35px
        rgba(25,31,40,0.055);
}

/* ---------- section ---------- */

.section-title {
    font-size: 19px;
    font-weight: 750;
    color: #191f28;
    margin-bottom: 2px;
}

.section-description {
    color: #8b95a1;
    font-size: 13px;
    margin-bottom: 12px;
}

/* ---------- demo mode ---------- */

.demo-status {
    padding: 11px 14px;
    border-radius: 12px;

    color: #1b64da;
    background: #f1f6ff;
    border: 1px solid #c9ddff;

    font-size: 13px;
    font-weight: 650;
    margin-top: 4px;
}

/* ---------- buttons ---------- */

div.stButton > button {
    border-radius: 15px;
    min-height: 60px;

    background: #ffffff;
    border: 1px solid #dfe5ec;

    color: #333d4b;
    font-weight: 650;

    transition: 0.15s ease;
}

div.stButton > button:hover {
    border-color: #3182f6;
    color: #1b64da;

    transform: translateY(-1px);

    box-shadow:
        0 8px 22px
        rgba(49,130,246,0.10);
}

div.stButton > button[kind="primary"] {

    min-height: 52px;

    background:
        linear-gradient(
            135deg,
            #3182f6,
            #2563df
        ) !important;

    border: none !important;

    color: white !important;

    font-size: 15px;
    font-weight: 700;

    box-shadow:
        0 9px 24px
        rgba(49,130,246,0.23);
}

/* ---------- inputs ---------- */

[data-testid="stTextArea"] textarea {
    background: #f8fafc !important;
    border: 1px solid #e4e9ef !important;

    border-radius: 14px !important;

    padding: 16px !important;

    min-height: 145px;

    color: #191f28 !important;

    font-size: 14px;
}

[data-testid="stTextInput"] input {
    background: #f8fafc !important;
    border: 1px solid #e4e9ef !important;

    border-radius: 14px !important;

    min-height: 50px;

    color: #191f28 !important;
}

[data-testid="stTextArea"] textarea:focus,
[data-testid="stTextInput"] input:focus {

    border-color: #3182f6 !important;

    box-shadow:
        0 0 0 3px
        rgba(49,130,246,0.09) !important;
}

/* ---------- result title ---------- */

.result-header {
    margin-top: 32px;
    margin-bottom: 15px;

    display: flex;
    justify-content: space-between;
    align-items: center;
}

.result-title {
    font-size: 22px;
    font-weight: 800;
    color: #191f28;
}

.result-sub {
    margin-top: 3px;
    color: #8b95a1;
    font-size: 13px;
}

.complete {
    background: #e9f9ef;
    color: #15803d;

    padding: 7px 12px;
    border-radius: 999px;

    font-size: 12px;
    font-weight: 700;
}

/* ---------- cards ---------- */

.card-title {
    font-size: 16px;
    font-weight: 750;

    color: #191f28;

    margin-bottom: 3px;
}

.card-subtitle {
    color: #8b95a1;
    font-size: 12px;

    margin-bottom: 15px;
}

.data-panel {
    background: #f8fafc;
    border-radius: 14px;

    padding: 10px 13px;
}

.data-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;

    padding: 9px 0;

    border-bottom:
        1px solid #edf0f3;
}

.data-row:last-child {
    border-bottom: none;
}

.data-label {
    color: #8b95a1;
    font-size: 12px;
}

.data-value {
    color: #333d4b;
    font-size: 12px;

    font-weight: 700;

    text-align: right;

    word-break: break-all;
}

.blue-pill {
    color: #1b64da;

    background: #e8f2ff;

    padding: 4px 8px;

    border-radius: 999px;

    font-size: 11px;

    font-weight: 750;
}

.green-pill {
    color: #15803d;

    background: #e5f7ec;

    padding: 4px 8px;

    border-radius: 999px;

    font-size: 11px;

    font-weight: 750;
}

.money {
    color: #00a66b;
}

/* ---------- payment ---------- */

.payment-success {
    background: #eaf9ef;

    color: #15803d;

    padding: 12px;

    border-radius: 13px;

    font-weight: 700;

    font-size: 13px;

    margin-bottom: 10px;
}

/* ---------- usage ---------- */

.bar-background {
    width: 100%;
    height: 8px;

    background: #e6ebf1;

    border-radius: 100px;

    overflow: hidden;

    margin: 5px 0 14px;
}

.bar-fill {
    height: 100%;

    background:
        linear-gradient(
            90deg,
            #6db5ff,
            #3182f6
        );

    border-radius: 100px;
}

/* ---------- AI answer ---------- */

.answer-title {
    font-size: 18px;
    font-weight: 750;

    color: #191f28;

    margin-bottom: 4px;
}

.answer-sub {
    color: #8b95a1;

    font-size: 12px;

    margin-bottom: 12px;
}

.hero-grid {
    display: grid;
    grid-template-columns: 1.45fr 0.8fr;
    gap: 70px;
    align-items: center;

    padding: 28px 5px 34px 5px;
}

.hero-left {
    min-width: 0;
}

.system-card {
    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,0.96),
            rgba(245,249,255,0.96)
        );

    border: 1px solid #e3eaf3;
    border-radius: 22px;

    padding: 20px;

    box-shadow:
        0 14px 40px
        rgba(25,31,40,0.07);
}

.system-card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;

    margin-bottom: 15px;
}

.system-label {
    font-size: 10px;
    letter-spacing: 0.11em;
    font-weight: 800;
    color: #8b95a1;
}

.system-title {
    margin-top: 4px;

    font-size: 16px;
    font-weight: 750;

    color: #191f28;
}

.live-pill {
    padding: 6px 10px;

    border-radius: 999px;

    background: #e7f8ed;
    color: #16883e;

    font-size: 11px;
    font-weight: 750;
}

.system-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.system-row {
    display: grid;
    grid-template-columns: 1fr 1fr auto;

    gap: 12px;
    align-items: center;

    padding: 9px 4px;

    border-bottom: 1px solid #edf1f5;

    font-size: 12px;

    color: #8b95a1;
}

.system-row:last-child {
    border-bottom: none;
}

.system-row strong {
    color: #333d4b;
    font-weight: 650;
}

.system-ok {
    color: #16883e;
    font-size: 11px;
    font-weight: 700;
}

@media (max-width: 900px) {
    .hero-grid {
        grid-template-columns: 1fr;
        gap: 22px;
    }
}
</style>
""")



# =========================================================
# Hero
# =========================================================

md("""
<div class="hero-grid">

    <div class="hero-left">

        <div class="brand">
            <div class="logo-box">⚡</div>
            <div class="brand-name">Agent Finance</div>
        </div>

        <div class="hero-description">
            AI가 작업을 분석하고, 비용과 예산을 확인한 뒤<br>
            가장 적절한 실행 경로를 선택합니다.
        </div>

        <div class="features">
            <div class="feature">
                ✦ 최적의 실행 경로 선택
            </div>

            <div class="feature">
                ◎ 비용과 예산 자동 확인
            </div>

            <div class="feature">
                ✓ 안전한 결제 및 실행
            </div>
        </div>

    </div>

    <div class="system-card">

        <div class="system-card-top">
            <div>
                <div class="system-label">
                    SYSTEM STATUS
                </div>
                <div class="system-title">
                    Agent Finance is ready
                </div>
            </div>

            <div class="live-pill">
                ● LIVE
            </div>
        </div>

        <div class="system-list">

            <div class="system-row">
                <span>Routing</span>
                <strong>Kiln</strong>
                <span class="system-ok">Ready</span>
            </div>

            <div class="system-row">
                <span>Payment</span>
                <strong>Sepolia</strong>
                <span class="system-ok">Ready</span>
            </div>

            <div class="system-row">
                <span>Paid Model</span>
                <strong>Claude</strong>
                <span class="system-ok">Ready</span>
            </div>

            <div class="system-row">
                <span>Local Model</span>
                <strong>Qwen3 8B</strong>
                <span class="system-ok">Ready</span>
            </div>

        </div>

    </div>

</div>
""")


# =========================================================
# Input Panel
# =========================================================

with st.container(border=True):

    md("""
    <div class="section-title">
        ⚙ 데모 방식 선택
    </div>

    <div class="section-description">
        실행할 에이전트 동작 방식을 선택하세요.
    </div>
    """)

    left, right = st.columns(2)

    with left:
        paid_clicked = st.button(
            "💳  Paid Demo\n\n실제 결제를 통한 전체 플로우",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.demo_mode == "PAID"
                else "secondary"
            ),
            key="paid_demo_button",
        )

    with right:
        local_clicked = st.button(
            "⌨  Local Fallback Demo\n\n결제 없이 로컬 대체 실행",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.demo_mode == "LOCAL"
                else "secondary"
            ),
            key="local_demo_button",
        )

    if paid_clicked:
        st.session_state.demo_mode = "PAID"
        st.session_state.budget = "0.050000"
        st.session_state.task = DEFAULT_TASK
        st.rerun()

    if local_clicked:
        st.session_state.demo_mode = "LOCAL"
        st.session_state.budget = "0.000000"
        st.session_state.task = DEFAULT_TASK
        st.rerun()

    if st.session_state.demo_mode == "PAID":
        md("""
        <div class="demo-status">
            ● Paid Demo 선택됨 ·
            Kiln → Budget Check → Blockchain → Paid Model
        </div>
        """)
    else:
        md("""
        <div class="demo-status">
            ● Local Fallback Demo 선택됨 ·
            예산 부족 시 qwen3:8b 로컬 모델로 실행
        </div>
        """)

    st.write("")

    md("""
    <div class="section-title">
        ✎ 작업 요청
    </div>
    """)

    task = st.text_area(
        "Task",
        key="task",
        label_visibility="collapsed",
        height=145,
    )

    budget_col, button_col = st.columns(
        [0.42, 0.58]
    )

    with budget_col:

        md("""
        <div class="section-title"
        style="font-size:14px; margin-top:8px;">
            최대 예산 (USD)
        </div>
        """)

        budget = st.text_input(
            "Budget",
            key="budget",
            label_visibility="collapsed",
        )

    with button_col:

        md("""
        <div style="height:31px;"></div>
        """)

        run_button = st.button(
            "▶  Run Agent",
            type="primary",
            use_container_width=True,
        )

    

# =========================================================
# API
# =========================================================

if run_button:

    if not task.strip():
        st.error("Task를 입력해주세요.")
        st.stop()

    try:

        with st.spinner(
            "AI가 작업을 분석하고 있습니다..."
        ):

            response = httpx.post(
                API_URL,
                json={
                    "task": task,
                    "budget_usd": budget,
                },
                timeout=180.0,
            )

            response.raise_for_status()

            st.session_state.result_data = (
                response.json()
            )

    except httpx.ConnectError:

        st.error(
            "FastAPI 서버에 연결할 수 없습니다. "
            "uvicorn 실행 여부를 확인해주세요."
        )

    except httpx.HTTPStatusError as exc:

        st.error(
            f"Backend error: "
            f"{exc.response.status_code}"
        )

    except Exception as exc:

        st.error(
            f"Request failed: {exc}"
        )


# =========================================================
# Result
# =========================================================

data = st.session_state.result_data

if data:

    decision = data["decision"]
    cost = data["cost"]
    payment = data["payment"]
    usage = data["usage"]

    recommended = html.escape(
        str(decision["recommended_route"])
    )

    actual = html.escape(
        str(decision["actual_route"])
    )

    model = html.escape(
        str(decision["selected_model"])
    )

    fallback = (
        html.escape(
            str(decision["fallback_reason"])
        )
        if decision.get("fallback_reason")
        else "없음"
    )

    tx_hash = payment.get("tx_hash")

    if tx_hash:
        tx_short = (
            tx_hash[:8]
            + "..."
            + tx_hash[-6:]
        )
    else:
        tx_short = "없음"

    total_tokens = (
        int(usage["input_tokens"])
        + int(usage["output_tokens"])
    )

    max_usage = max(
        int(usage["input_tokens"]),
        int(usage["output_tokens"]),
        1,
    )

    input_percent = int(
        int(usage["input_tokens"])
        / max_usage
        * 100
    )

    output_percent = int(
        int(usage["output_tokens"])
        / max_usage
        * 100
    )


    # -----------------------------------------------------
    # Result title
    # -----------------------------------------------------

    md("""
    <div class="result-header">

        <div>
            <div class="result-title">
                ▥ 실행 결과
            </div>

            <div class="result-sub">
                실행 경로와 비용,
                결제 및 토큰 사용량을 확인하세요.
            </div>
        </div>

        <div class="complete">
            ● 실행 완료
        </div>

    </div>
    """)


    # -----------------------------------------------------
    # Four result cards
    # -----------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)


    # Route
    with c1:

        with st.container(border=True):

            md(f"""
            <div class="card-title">
                ◈ 실행 경로
            </div>

            <div class="card-subtitle">
                AI가 선택한 실행 경로
            </div>

            <div class="data-panel">

                <div class="data-row">
                    <span class="data-label">
                        추천 경로
                    </span>
                    <span class="blue-pill">
                        {recommended}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        실제 경로
                    </span>
                    <span class="blue-pill">
                        {actual}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        선택 모델
                    </span>
                    <span class="data-value">
                        {model}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        대체 사유
                    </span>
                    <span class="data-value">
                        {fallback}
                    </span>
                </div>

            </div>
            """)


    # Cost
    with c2:

        with st.container(border=True):

            md(f"""
            <div class="card-title">
                ＄ 비용 요약
            </div>

            <div class="card-subtitle">
                예상 비용과 실제 비용
            </div>

            <div class="data-panel">

                <div class="data-row">
                    <span class="data-label">
                        budget
                    </span>
                    <span class="data-value">
                        ${cost["budget_usd"]}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        estimated
                    </span>
                    <span class="data-value">
                        ${cost["estimated_cost_usd"]}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        actual
                    </span>
                    <span class="data-value money">
                        ${cost["actual_cost_usd"]}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        you pay
                    </span>
                    <span class="data-value money">
                        ${cost["user_charge_usd"]}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        platform
                    </span>
                    <span class="data-value">
                        ${cost["platform_charge_usd"]}
                    </span>
                </div>

            </div>
            """)


    # Payment
    with c3:

        with st.container(border=True):

            approved = bool(
                payment["approved"]
            )

            approved_text = (
                "true"
                if approved
                else "false"
            )

            payment_title = (
                "결제 승인 완료"
                if approved
                else "결제 없음"
            )

            md(f"""
            <div class="card-title">
                ▣ 결제 정보
            </div>

            <div class="card-subtitle">
                Blockchain authorization
            </div>

            <div class="payment-success">
                ✓ {payment_title}
            </div>

            <div class="data-panel">

                <div class="data-row">
                    <span class="data-label">
                        approved
                    </span>
                    <span class="green-pill">
                        {approved_text}
                    </span>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        tx_hash
                    </span>
                    <span class="data-value">
                        {tx_short}
                    </span>
                </div>

            </div>
            """)

            if tx_hash:

                st.link_button(
                    "Sepolia에서 보기 ↗",
                    (
                        "https://sepolia.etherscan.io/"
                        f"tx/{tx_hash}"
                    ),
                    use_container_width=True,
                )


    # Usage
    with c4:

        with st.container(border=True):

            md(f"""
            <div class="card-title">
                ▤ 사용량
            </div>

            <div class="card-subtitle">
                Token usage
            </div>

            <div class="data-panel">

                <div class="data-row">
                    <span class="data-label">
                        input_tokens
                    </span>
                    <span class="data-value">
                        {usage["input_tokens"]}
                    </span>
                </div>

                <div class="bar-background">
                    <div
                        class="bar-fill"
                        style="width:{input_percent}%;">
                    </div>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        output_tokens
                    </span>
                    <span class="data-value">
                        {usage["output_tokens"]}
                    </span>
                </div>

                <div class="bar-background">
                    <div
                        class="bar-fill"
                        style="width:{output_percent}%;">
                    </div>
                </div>

                <div class="data-row">
                    <span class="data-label">
                        total_tokens
                    </span>
                    <span class="data-value">
                        {total_tokens}
                    </span>
                </div>

            </div>
            """)


    # -----------------------------------------------------
    # Platform overrun
    # -----------------------------------------------------

    if float(
        cost["platform_charge_usd"]
    ) > 0:

        st.info(
            "🛡 실제 비용이 예상 비용을 초과해 "
            "Agent Finance가 "
            f"${cost['platform_charge_usd']}를 부담했습니다."
        )


    # -----------------------------------------------------
    # AI result
    # -----------------------------------------------------

    st.write("")

    with st.container(border=True):

        md("""
        <div class="answer-title">
            ✦ AI Result
        </div>

        <div class="answer-sub">
            선택된 실행 모델의 최종 응답
        </div>
        """)

        st.markdown(
            data["result"]
        )


    # -----------------------------------------------------
    # Developer details
    # -----------------------------------------------------

    with st.expander(
        "개발자용 전체 실행 정보"
    ):

        st.write(
            f"Run ID: {data['run_id']}"
        )

        st.write(
            f"Status: {data['status']}"
        )

        st.json(data)