import streamlit as st
import httpx

API_URL = "http://127.0.0.1:8000/api/run"

st.set_page_config(
    page_title="Agent Finance",
    page_icon="💳",
    layout="wide"
)

st.title("Agent Finance")
st.caption("AI Agent Routing + Budget Control + Blockchain Payment")

st.divider()

task = st.text_area(
    "Task",
    value="Analyze this code and find the bug.",
    height=120
)

budget = st.text_input(
    "Maximum Budget (USD)",
    value="0.050000"
)

if st.button("Run Agent", type="primary"):

    payload = {
        "task": task,
        "budget_usd": budget
    }

    try:
        with st.spinner("Agent is processing..."):
            response = httpx.post(
                API_URL,
                json=payload,
                timeout=60.0
            )

        response.raise_for_status()
        data = response.json()

        st.success("Execution completed")

        decision = data["decision"]
        cost = data["cost"]
        payment = data["payment"]
        usage = data["usage"]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Recommended Route",
                decision["recommended_route"]
            )

        with col2:
            st.metric(
                "Actual Route",
                decision["actual_route"]
            )

        with col3:
            st.metric(
                "Selected Model",
                decision["selected_model"]
            )

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Budget",
                f'${cost["budget_usd"]}'
            )

        with col2:
            st.metric(
                "Estimated Cost",
                f'${cost["estimated_cost_usd"]}'
            )

        with col3:
            st.metric(
                "Actual Cost",
                f'${cost["actual_cost_usd"]}'
            )

        st.divider()

        st.subheader("Payment")

        if payment["approved"]:
            st.success("Blockchain payment approved")

            st.write("Transaction Hash:")
            st.code(payment["tx_hash"])
        else:
            st.error("Payment rejected")

            if decision.get("fallback_reason"):
                st.write(
                    "Fallback reason:",
                    decision["fallback_reason"]
                )

        st.divider()

        st.subheader("Token Usage")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Input Tokens",
                usage["input_tokens"]
            )

        with col2:
            st.metric(
                "Output Tokens",
                usage["output_tokens"]
            )

        st.divider()

        st.subheader("Result")
        st.write(data["result"])

        with st.expander("Raw Response"):
            st.json(data)

    except Exception as e:
        st.error(f"Error: {e}")