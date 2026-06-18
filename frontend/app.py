import streamlit as st
import requests
import pandas as pd

API = "http://localhost:8000"

st.set_page_config(
    page_title="AWS Agreement Chatbot",
    page_icon="☁️",
    layout="wide",
)

st.sidebar.title("☁️ AWS Agreement Chatbot")
page = st.sidebar.radio("Go to", ["Chat", "Analytics"])

st.sidebar.markdown("---")
if st.sidebar.button("Ingest PDF"):
    with st.spinner("Processing PDF..."):
        try:
            r = requests.post(f"{API}/ingest", timeout=120)
            if r.status_code == 200:
                d = r.json()
                st.sidebar.success(f"Done! {d['pages_loaded']} pages, {d['chunks_created']} chunks")
            else:
                st.sidebar.error(r.json().get("detail", "Something went wrong"))
        except requests.exceptions.ConnectionError:
            st.sidebar.error("Can't reach the backend. Is FastAPI running on port 8000?")

st.sidebar.markdown("Run `POST /ingest` once before chatting.")


if page == "Chat":
    st.title("Ask about the AWS Customer Agreement")

    if "history" not in st.session_state:
        st.session_state.history = []

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander("Sources"):
                    st.markdown(msg["sources"])
            if msg["role"] == "assistant":
                found_label = "Answer found in document" if msg.get("found") else "Not found in document"
                st.caption(f"{msg.get('time', '')}s   ·   {found_label}")

    if prompt := st.chat_input("e.g. What is AWS data privacy policy?"):
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching..."):
                try:
                    r = requests.post(f"{API}/ask", json={"question": prompt}, timeout=120)
                    if r.status_code == 200:
                        d = r.json()
                        st.markdown(d["answer"])

                        src_md = ""
                        for i, s in enumerate(d["sources"][:4], 1):
                            src_md += f"**Source {i} — Page {s['page']}**\n> {s['snippet'][:200]}…\n\n"

                        with st.expander("Sources"):
                            st.markdown(src_md or "No sources.")

                        label = "Answer found in document" if d["answer_found"] else "Not found in document"
                        st.caption(f"{d['response_time_seconds']}s   ·   {label}")

                        st.session_state.history.append({
                            "role": "assistant",
                            "content": d["answer"],
                            "sources": src_md,
                            "found": d["answer_found"],
                            "time": d["response_time_seconds"],
                        })
                    elif r.status_code == 503:
                        st.error(r.json().get("detail", "Backend not ready. Run /ingest first."))
                    else:
                        st.error(f"Error {r.status_code}: {r.json().get('detail', '')}")
                except requests.exceptions.ConnectionError:
                    st.error("Can't reach the backend on port 8000.")

    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()


elif page == "Analytics":
    st.title("Analytics Dashboard")

    if st.button("Refresh"):
        st.rerun()

    try:
        r = requests.get(f"{API}/analytics", timeout=30)
        if r.status_code != 200:
            st.error(f"Failed to load analytics: {r.text}")
            st.stop()

        d = r.json()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Queries", d["total_queries"])
        c2.metric("Avg Response Time", f"{d['average_response_time_seconds']}s")
        c3.metric("No-Answer Queries", len(d["no_answer_queries"]))

        st.divider()

        left, right = st.columns(2)

        with left:
            st.subheader("Most Asked Questions")
            if d["most_asked_questions"]:
                df = pd.DataFrame(d["most_asked_questions"])
                df.index += 1
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No data yet.")

        with right:
            st.subheader("Queries per Day (last 7 days)")
            if d["queries_per_day"]:
                df2 = pd.DataFrame(d["queries_per_day"]).rename(
                    columns={"date": "Date", "count": "Queries"}
                )
                st.bar_chart(df2.set_index("Date"))
            else:
                st.info("No data yet.")

        st.divider()
        st.subheader("Questions With No Answer Found")
        if d["no_answer_queries"]:
            st.dataframe(pd.DataFrame(d["no_answer_queries"]), use_container_width=True)
        else:
            st.success("All questions were answered from the document.")

    except requests.exceptions.ConnectionError:
        st.error("Can't connect to the backend. Make sure FastAPI is running on port 8000.")
