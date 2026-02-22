import streamlit as st
import pandas as pd
import time
import random
import os
from datetime import datetime

st.set_page_config(page_title="Academy CBT System", layout="wide")

# =============================
# BASIC SECURITY
# =============================
st.markdown("""
<script>
document.addEventListener('contextmenu', event => event.preventDefault());
document.addEventListener('copy', event => event.preventDefault());
document.addEventListener('paste', event => event.preventDefault());
document.onselectstart = function() { return false; }
</script>
""", unsafe_allow_html=True)

# =============================
# SESSION INIT
# =============================
if "page" not in st.session_state:
    st.session_state.page = "login"

if "answers" not in st.session_state:
    st.session_state.answers = {}

if "questions" not in st.session_state:
    st.session_state.questions = []

if "show_correction" not in st.session_state:
    st.session_state.show_correction = False

if "result_saved" not in st.session_state:
    st.session_state.result_saved = False

if "start_time" not in st.session_state:
    st.session_state.start_time = None

# =============================
# TIMER CONFIG
# =============================
EXAM_DURATION = 60 * 40  # 40 minutes

# =============================
# LOAD QUESTIONS
# =============================
def load_questions():
    if os.path.exists("questions.csv"):
        return pd.read_csv("questions.csv")
    return pd.DataFrame()

# =============================
# CHECK IF STUDENT ALREADY SUBMITTED
# =============================
def has_submitted(email):
    if not os.path.exists("results.csv"):
        return False
    df = pd.read_csv("results.csv")
    return email.lower() in df["Email"].astype(str).str.lower().values

# =============================
# LOGIN PAGE
# =============================
if st.session_state.page == "login":

    st.title("🎓 Academy CBT System")

    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        # ADMIN LOGIN
        if email == "admin@academy.com" and password == "admin123":
            st.session_state.page = "admin"
            st.rerun()

        if not name or not email:
            st.warning("Enter required details.")
            st.stop()

        if has_submitted(email):
            st.error("You have already submitted this test.")
            st.stop()

        st.session_state.student_name = name
        st.session_state.student_email = email

        df = load_questions()

        if df.empty:
            st.error("No questions uploaded yet.")
            st.stop()

        df = df.sample(frac=1).reset_index(drop=True)

        questions = []

        for _, row in df.iterrows():

            q_type = row["type"] if "type" in df.columns else "mcq"

            if q_type == "mcq":
                options = [row["option1"], row["option2"], row["option3"], row["option4"]]
                options = [opt for opt in options if pd.notna(opt)]
                random.shuffle(options)
            else:
                options = []

            questions.append({
                "question": row["question"],
                "options": options,
                "answer": row["answer"],
                "type": q_type
            })

        st.session_state.questions = questions
        st.session_state.answers = {}
        st.session_state.show_correction = False
        st.session_state.result_saved = False
        st.session_state.start_time = None
        st.session_state.page = "quiz"
        st.rerun()

# =============================
# QUIZ PAGE
# =============================
elif st.session_state.page == "quiz":

    st.title("📝 Assessment")

    # Start timer only here
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    elapsed_time = time.time() - st.session_state.start_time
    remaining_time = EXAM_DURATION - elapsed_time

    if remaining_time <= 0:
        st.error("⛔ Time is up! Submitting your test...")
        st.session_state.page = "result"
        st.rerun()

    mins = int(remaining_time // 60)
    secs = int(remaining_time % 60)
    st.warning(f"⏳ Time Remaining: {mins:02d}:{secs:02d}")

    total_questions = len(st.session_state.questions)

    for i, q in enumerate(st.session_state.questions):

        st.markdown("---")
        st.markdown(f"**Q{i+1}. {q['question']}**")

        if q["type"] == "short":
            answer = st.text_input("Your Answer:", key=f"q{i}")
        else:
            answer = st.radio("", q["options"], index=None, key=f"q{i}")

        if answer:
            st.session_state.answers[f"q{i}"] = answer

    if st.button("Submit Test"):

        if len(st.session_state.answers) < total_questions:
            st.warning("Answer all questions before submitting.")
            st.stop()

        st.session_state.page = "result"
        st.rerun()

    time.sleep(1)
    st.rerun()

# =============================
# RESULT PAGE
# =============================
elif st.session_state.page == "result":

    st.title("📊 Test Result")

    correct = 0
    total = len(st.session_state.questions)

    for i, q in enumerate(st.session_state.questions):
        student_answer = st.session_state.answers.get(f"q{i}")
        correct_answer = q["answer"]

        if student_answer is not None:
            if str(student_answer).strip().lower() == str(correct_answer).strip().lower():
                correct += 1

    percentage = (correct / total) * 100 if total > 0 else 0

    st.write(f"Score: {correct}/{total}")
    st.write(f"Percentage: {percentage:.2f}%")

    # Save result only once
    if not st.session_state.result_saved:

        df = pd.DataFrame([{
            "Name": st.session_state.student_name,
            "Email": st.session_state.student_email,
            "Score": correct,
            "Percentage": percentage,
            "Timestamp": datetime.now()
        }])

        if os.path.exists("results.csv"):
            df.to_csv("results.csv", mode="a", header=False, index=False)
        else:
            df.to_csv("results.csv", index=False)

        st.session_state.result_saved = True

    st.success("Test Submitted Successfully!")

    if st.button("View Detailed Corrections"):
        st.session_state.show_correction = True

    if st.session_state.show_correction:

        st.markdown("---")
        st.header("📝 Corrections")

        for i, q in enumerate(st.session_state.questions):

            student_answer = st.session_state.answers.get(f"q{i}")
            correct_answer = q["answer"]

            st.markdown(f"**Q{i+1}. {q['question']}**")

            if student_answer is None:
                st.warning("You did not answer this question.")
                st.info(f"Correct Answer: {correct_answer}")

            elif str(student_answer).strip().lower() == str(correct_answer).strip().lower():
                st.success(f"Your Answer: {student_answer} ✅ Correct")

            else:
                st.error(f"Your Answer: {student_answer} ❌ Incorrect")
                st.info(f"Correct Answer: {correct_answer}")

        st.markdown("---")
        st.success("End of Test. Thank you.")
        st.stop()

# =============================
# ADMIN DASHBOARD
# =============================
elif st.session_state.page == "admin":

    st.title("📊 Admin Dashboard")

    tab1, tab2, tab3 = st.tabs(["Results", "Upload Questions", "Analytics"])

    with tab1:
        if os.path.exists("results.csv"):
            df = pd.read_csv("results.csv")
            st.dataframe(df)
            st.download_button("Download Results", df.to_csv(index=False), "results.csv")
        else:
            st.info("No results yet.")

    with tab2:
        uploaded = st.file_uploader("Upload Questions CSV", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
            df.to_csv("questions.csv", index=False)
            st.success("Questions updated successfully!")

    with tab3:
        if os.path.exists("results.csv"):
            df = pd.read_csv("results.csv")
            st.write("Average Score:", df["Score"].mean())
            st.write("Pass Rate (%):", (df["Percentage"] >= 50).mean() * 100)
        else:
            st.info("No data available.")