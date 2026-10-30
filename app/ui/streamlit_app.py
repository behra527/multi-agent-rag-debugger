import streamlit as st

from app.core.models import IssueRequest
from app.factory import create_project_manager


st.set_page_config(
    page_title="Multi-Agent RAG Debugger",
    page_icon="",
    layout="wide",
)

st.title("Multi-Agent RAG Debugger")
st.caption(
    "Repository analysis, evidence retrieval, root-cause analysis, "
    "patch generation, and test validation."
)

st.warning(
    "Use only trusted local repositories. Validation runs project "
    "tests on your machine; this application is not a security sandbox."
)

with st.form("debug_issue_form"):
    title = st.text_input(
        "Issue title",
        placeholder="Example: Login fails for valid credentials",
    )

    description = st.text_area(
        "Issue description",
        placeholder="Describe the observed behavior and expected result.",
        height=140,
    )

    repository_path = st.text_input(
        "Absolute repository path",
        placeholder=r"D:\AI TASK\your-project",
    )

    submitted = st.form_submit_button(
        "Analyze and debug",
        type="primary",
    )

if submitted:
    if not title.strip() or not description.strip() or not repository_path.strip():
        st.error("Complete all three fields before submitting.")
        st.stop()

    issue = IssueRequest(
        title=title.strip(),
        description=description.strip(),
        repository_path=repository_path.strip(),
    )

    try:
        with st.spinner(
            "Running agents, retrieving evidence, and validating the proposed fix..."
        ):
            manager = create_project_manager()
            report = manager.handle_issue(issue)

        st.subheader("Debugging result")

        if report.status == "validated":
            st.success(report.message)
        else:
            st.error(report.message)

        left, right = st.columns(2)

        with left:
            st.metric("Status", report.status)
            st.metric("Validation attempts", report.validation_attempts)

        with right:
            st.metric("Evidence items", len(report.evidence))
            st.metric("Workflow stages", len(report.stage_traces))

        if report.analysis:
            with st.expander("Issue analysis", expanded=True):
                st.json(report.analysis.model_dump(mode="json"))

        if report.evidence:
            with st.expander("Retrieved repository evidence", expanded=True):
                for number, evidence in enumerate(report.evidence, start=1):
                    st.markdown(
                        f"**{number}. {evidence.source}:"
                        f"{evidence.start_line}-{evidence.end_line}**"
                    )
                    st.caption(
                        f"Language: {evidence.language} | "
                        f"Score: {evidence.score:.4f}"
                    )
                    st.code(evidence.content)

        if report.root_cause:
            with st.expander("Root-cause analysis", expanded=True):
                st.json(report.root_cause.model_dump(mode="json"))

        if report.proposed_fix:
            with st.expander("Proposed fix", expanded=True):
                st.write(report.proposed_fix.summary)
                st.write(report.proposed_fix.reasoning)

                if report.proposed_fix.patch:
                    st.code(
                        report.proposed_fix.patch,
                        language="diff",
                    )
                else:
                    st.warning("The agent did not return a patch.")

        if report.validation:
            with st.expander("Validation details", expanded=True):
                st.json(report.validation.model_dump(mode="json"))

        if report.stage_traces:
            with st.expander("Workflow execution trace"):
                st.json([
                    trace.model_dump(mode="json")
                    for trace in report.stage_traces
                ])

        if report.errors:
            with st.expander("Workflow errors"):
                st.json([
                    error.model_dump(mode="json")
                    for error in report.errors
                ])

        with st.expander("Complete report JSON"):
            st.json(report.model_dump(mode="json"))

    except ValueError as exc:
        st.error(f"Configuration or input error: {exc}")
    except Exception as exc:
        st.error(
            f"Application error: {type(exc).__name__}: {exc}"
        )
