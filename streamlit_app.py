import streamlit as st
import httpx

# =========================================================
# 기본 설정
# =========================================================

API_URL = "http://127.0.0.1:8000/api/run"

st.set_page_config(
    page_title="Agent Finance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    /* ---------- 전체 화면 ---------- */

    .stApp {
        background: #f7f8fa;
    }

    .block-container {
        max-width: 1080px;
        padding-top: 3.5rem;
        padding-bottom: 5rem;
    }

    html, body, [class*="css"] {
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            "Pretendard",
            sans-serif;
    }


    /* ---------- Streamlit 기본 메뉴 최소화 ---------- */

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }


    /* ---------- 제목 ---------- */

    .hero-title {
        font-size: 46px;
        font-weight: 800;
        color: #191f28;
        letter-spacing: -1.8px;
        line-height: 1.15;
        margin-bottom: 12px;
    }

    .hero-subtitle {
        font-size: 18px;
        color: #6b7684;
        line-height: 1.6;
        margin-bottom: 34px;
    }

    .brand-badge {
        display: inline-block;
        padding: 7px 12px;
        background: #e8f3ff;
        color: #3182f6;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 18px;
    }


    /* ---------- 섹션 제목 ---------- */

    .section-label {
        font-size: 14px;
        font-weight: 700;
        color: #8b95a1;
        margin-bottom: 7px;
    }

    .section-title {
        font-size: 24px;
        font-weight: 800;
        color: #191f28;
        letter-spacing: -0.7px;
        margin-bottom: 18px;
    }


    /* ---------- 카드 ---------- */

    .custom-card {
        background: #ffffff;
        border: 1px solid #edf0f2;
        border-radius: 22px;
        padding: 26px;
        box-shadow: 0px 4px 18px rgba(0, 0, 0, 0.035);
        margin-bottom: 18px;
    }

    .status-card {
        background: #ffffff;
        border: 1px solid #edf0f2;
        border-radius: 24px;
        padding: 28px;
        box-shadow: 0px 4px 18px rgba(0, 0, 0, 0.035);
        margin-top: 12px;
        margin-bottom: 24px;
    }

    .status-small {
        font-size: 14px;
        font-weight: 600;
        color: #8b95a1;
        margin-bottom: 7px;
    }

    .status-title {
        font-size: 28px;
        font-weight: 800;
        color: #191f28;
        letter-spacing: -0.8px;
    }

    .status-paid {
        color: #3182f6;
        font-size: 15px;
        font-weight: 700;
        margin-top: 8px;
    }

    .status-local {
        color: #f04452;
        font-size: 15px;
        font-weight: 700;
        margin-top: 8px;
    }


    /* ---------- Input ---------- */

    .stTextInput input,
    .stTextArea textarea {
        background: #ffffff !important;
        border: 1px solid #e5e8eb !important;
        border-radius: 16px !important;
        color: #191f28 !important;
        padding: 14px !important;
        box-shadow: none !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border: 1px solid #3182f6 !important;
        box-shadow: 0 0 0 1px #3182f6 !important;
    }

    .stTextArea textarea {
        min-height: 145px;
    }


    /* ---------- 버튼 ---------- */

    .stButton > button {
        width: 100%;
        min-height: 52px;
        border: none !important;
        border-radius: 15px !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        transition: 0.15s ease;
    }

    .stButton > button[kind="primary"] {
        background: #3182f6 !important;
        color: #ffffff !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: #1b64da !important;
    }


    /* ---------- Metric ---------- */

    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #edf0f2;
        border-radius: 20px;
        padding: 22px 22px 20px 22px;
        box-shadow: 0px 3px 14px rgba(0, 0, 0, 0.03);
    }

    [data-testid="stMetricLabel"] {
        color: #8b95a1;
        font-size: 14px;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #191f28;
        font-weight: 800;
        font-size: 25px;
    }


    /* ---------- alert ---------- */

    [data-testid="stAlert"] {
        border-radius: 16px;
        border: none;
    }


    /* ---------- 코드 ---------- */

    .stCodeBlock {
        border-radius: 16px;
    }


    /* ---------- expander ---------- */

    [data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #edf0f2;
        border-radius: 18px;
        overflow: hidden;
    }


    /* ---------- divider ---------- */

    hr {
        border: none;
        border-top: 1px solid #e5e8eb;
        margin-top: 28px;
        margin-bottom: 28px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 세션 상태
# =========================================================

if "budget" not in st.session_state:
    st.session_state.budget = "0.050000"


def demo_paid():
    st.session_state.budget = "0.050000"


def demo_blocked():
    st.session_state.budget = "0.000000"


# =========================================================
# Header
# =========================================================

st.markdown(
    """
    <div class="brand-badge">
        AI × FINANCE × BLOCKCHAIN
    </div>

    <div class="hero-title">
        Agent Finance
    </div>

    <div class="hero-subtitle">
        필요한 만큼만 AI에 지불하세요.<br>
        AI가 적절한 모델을 추천하고,
        예산 정책과 블록체인이 실제 지출을 통제합니다.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Task 입력
# =========================================================

st.markdown(
    """
    <div class="section-label">NEW REQUEST</div>
    <div class="section-title">AI에게 작업을 요청해보세요</div>
    """,
    unsafe_allow_html=True,
)

task = st.text_area(
    "Task",
    value="Analyze this code and find the bug.",
    label_visibility="collapsed",
    placeholder="What do you want the AI agent to do?",
)


# =========================================================
# Budget
# =========================================================

st.markdown(
    """
    <div style="height:8px;"></div>
    <div class="section-label">SPENDING LIMIT</div>
    """,
    unsafe_allow_html=True,
)

budget_col, preset_col = st.columns([2, 1])

with budget_col:
    budget = st.text_input(
        "Maximum Budget (USD)",
        key="budget",
        placeholder="0.050000",
    )

with preset_col:
    st.markdown(
        """
        <div style="
            color:#8b95a1;
            font-size:14px;
            font-weight:600;
            margin-bottom:8px;
        ">
            Demo preset
        </div>
        """,
        unsafe_allow_html=True,
    )

    demo1, demo2 = st.columns(2)

    with demo1:
        st.button(
            "$0.05",
            on_click=demo_paid,
            use_container_width=True,
        )

    with demo2:
        st.button(
            "$0",
            on_click=demo_blocked,
            use_container_width=True,
        )


st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

run_button = st.button(
    "Run Agent",
    type="primary",
    use_container_width=True,
)


# =========================================================
# API 실행
# =========================================================

if run_button:

    payload = {
        "task": task,
        "budget_usd": budget,
    }

    try:
        with st.spinner("Analyzing task and checking authorization..."):

            response = httpx.post(
                API_URL,
                json=payload,
                timeout=120.0,
            )

        response.raise_for_status()

        data = response.json()

        decision = data["decision"]
        cost = data["cost"]
        payment = data["payment"]
        usage = data["usage"]

        st.markdown("<hr>", unsafe_allow_html=True)


        # =================================================
        # 실행 상태
        # =================================================

        if decision["actual_route"] == "PAID":

            st.markdown(
                """
                <div class="status-card">
                    <div class="status-small">
                        EXECUTION STATUS
                    </div>

                    <div class="status-title">
                        Paid AI selected
                    </div>

                    <div class="status-paid">
                        ✓ Budget authorization passed
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            st.markdown(
                """
                <div class="status-card">
                    <div class="status-small">
                        EXECUTION STATUS
                    </div>

                    <div class="status-title">
                        Local AI selected
                    </div>

                    <div class="status-local">
                        Paid execution was blocked
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


        # =================================================
        # Routing
        # =================================================

        st.markdown(
            """
            <div class="section-label">ROUTING DECISION</div>
            <div class="section-title">AI 실행 경로</div>
            """,
            unsafe_allow_html=True,
        )

        route1, route2, route3 = st.columns(3)

        with route1:
            st.metric(
                "Recommended Route",
                decision["recommended_route"],
            )

        with route2:
            st.metric(
                "Actual Route",
                decision["actual_route"],
            )

        with route3:
            st.metric(
                "Selected Model",
                decision["selected_model"],
            )

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        st.info(f'Why this route?  {decision["reason"]}')


        # =================================================
        # Cost
        # =================================================

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="section-label">COST CONTROL</div>
            <div class="section-title">비용</div>
            """,
            unsafe_allow_html=True,
        )

        cost1, cost2, cost3 = st.columns(3)

        with cost1:
            st.metric(
                "Maximum Budget",
                f'${cost["budget_usd"]}',
            )

        with cost2:
            st.metric(
                "Estimated Cost",
                f'${cost["estimated_cost_usd"]}',
            )

        with cost3:
            st.metric(
                "Actual Cost",
                f'${cost["actual_cost_usd"]}',
            )


        # =================================================
        # Blockchain
        # =================================================

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="section-label">BLOCKCHAIN AUTHORIZATION</div>
            <div class="section-title">Payment Security</div>
            """,
            unsafe_allow_html=True,
        )

        if payment["approved"]:

            st.success(
                "Payment approved · Blockchain transaction completed"
            )

            tx_hash = payment.get("tx_hash")

            if tx_hash:
                st.markdown("**Transaction Hash**")
                st.code(tx_hash, language=None)

                clean_hash = (
                    tx_hash
                    if tx_hash.startswith("0x")
                    else f"0x{tx_hash}"
                )

                explorer_url = (
                    f"https://sepolia.etherscan.io/tx/{clean_hash}"
                )

                st.link_button(
                    "View transaction on Sepolia ↗",
                    explorer_url,
                    use_container_width=True,
                )

        else:

            st.error(
                "Payment rejected · No blockchain transaction created"
            )

            fallback_reason = decision.get("fallback_reason")

            if fallback_reason:
                st.markdown("**Fallback reason**")
                st.code(
                    fallback_reason,
                    language=None,
                )


        # =================================================
        # Token Usage
        # =================================================

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="section-label">AI USAGE</div>
            <div class="section-title">Token Usage</div>
            """,
            unsafe_allow_html=True,
        )

        token1, token2 = st.columns(2)

        with token1:
            st.metric(
                "Input Tokens",
                f'{usage["input_tokens"]:,}',
            )

        with token2:
            st.metric(
                "Output Tokens",
                f'{usage["output_tokens"]:,}',
            )


        # =================================================
        # 결과
        # =================================================

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="section-label">FINAL OUTPUT</div>
            <div class="section-title">AI Response</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="
                background:#ffffff;
                border:1px solid #edf0f2;
                border-radius:20px;
                padding:10px 22px;
                margin-bottom:16px;
            ">
            """,
            unsafe_allow_html=True,
        )

        # 사용자/AI 결과는 HTML에 직접 삽입하지 않고
        # Streamlit이 안전하게 출력하도록 함
        st.write(data["result"])

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )


        # =================================================
        # Debug / Raw response
        # =================================================

        with st.expander("Developer details"):

            st.markdown("**Run ID**")
            st.code(
                data["run_id"],
                language=None,
            )

            st.markdown("**Raw API response**")
            st.json(data)


    # =====================================================
    # API 오류 처리
    # =====================================================

    except httpx.ConnectError:

        st.error(
            "Backend API에 연결할 수 없습니다. "
            "FastAPI 서버가 실행 중인지 확인해주세요."
        )

        st.code(
            "uvicorn app.main:app --reload",
            language="bash",
        )

    except httpx.HTTPStatusError as e:

        st.error(
            f"API request failed "
            f"(HTTP {e.response.status_code})"
        )

        try:
            st.json(e.response.json())
        except Exception:
            st.write(e.response.text)

    except Exception as e:

        st.error("Unexpected error occurred.")
        st.code(str(e), language=None)