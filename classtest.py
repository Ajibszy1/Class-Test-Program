import streamlit as st
import pandas as pd
import time
import random
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(page_title="Academy CBT System", layout="wide")

# =============================
# GOOGLE SHEETS SETUP - FIXED VERSION
# =============================
def init_google_sheets():
    """Initialize connection to Google Sheets"""
    try:
        # For Streamlit Cloud, we'll use secrets
        if 'gcp_service_account' in st.secrets:
            # Running on Streamlit Cloud
            credentials_dict = st.secrets["gcp_service_account"]
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
            client = gspread.authorize(credentials)
            
            # Your Google Sheet ID
            SHEET_ID = "1rjmJg14yNGPF8oU_LhZnuiH7buTFsXkmltJ_9npVMj0"
            sheet = client.open_by_key(SHEET_ID).sheet1
            return sheet
        else:
            # Running locally - use local file
            return None
    except Exception as e:
        st.warning(f"Could not connect to Google Sheets: {str(e)}")
        return None

def save_to_google_sheets(name, email, score, percentage):
    """Save results to Google Sheets"""
    try:
        sheet = init_google_sheets()
        if sheet:
            # Prepare the row data
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = [name, email, score, percentage, timestamp]
            
            # Append to Google Sheets
            sheet.append_row(new_row)
            
            # Also save locally as backup
            save_locally(name, email, score, percentage)
            
            return True
        else:
            # Fallback to local save
            save_locally(name, email, score, percentage)
            return False
    except Exception as e:
        st.warning(f"Could not save to Google Sheets: {str(e)}. Saving locally instead.")
        save_locally(name, email, score, percentage)
        return False

def save_locally(name, email, score, percentage):
    """Fallback local save function"""
    new_row = pd.DataFrame([{
        "Name": name,
        "Email": email,
        "Score": score,
        "Percentage": percentage,
        "Timestamp": datetime.now()
    }])
    
    if os.path.exists("results.csv"):
        new_row.to_csv("results.csv", mode="a", header=False, index=False)
    else:
        new_row.to_csv("results.csv", index=False)

def get_all_results():
    """Get all results from Google Sheets or local file"""
    try:
        sheet = init_google_sheets()
        if sheet:
            # Get all records from Google Sheets
            records = sheet.get_all_records()
            if records:
                return pd.DataFrame(records)
    except:
        pass
    
    # Fallback to local file
    if os.path.exists("results.csv"):
        return pd.read_csv("results.csv")
    return pd.DataFrame()

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
        try:
            return pd.read_csv("questions.csv")
        except pd.errors.ParserError:
            try:
                return pd.read_csv("questions.csv", error_bad_lines=False, warn_bad_lines=True)
            except:
                try:
                    return pd.read_csv("questions.csv", encoding='utf-8', engine='python')
                except:
                    st.error("Error reading CSV file. Please check the file format.")
                    return pd.DataFrame()
    return pd.DataFrame()

# =============================
# CHECK IF STUDENT ALREADY SUBMITTED
# =============================
def has_submitted(email):
    # Check from Google Sheets
    df = get_all_results()
    if not df.empty and "Email" in df.columns:
        return email.lower() in df["Email"].astype(str).str.lower().values
    return False

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

    # Create a container for questions
    questions_container = st.container()
    
    with questions_container:
        for i, q in enumerate(st.session_state.questions):
            st.markdown("---")
            st.markdown(f"**Q{i+1}. {q['question']}**")

            if q["type"] == "short":
                answer = st.text_input("Your Answer:", key=f"q{i}")
            else:
                answer = st.radio("", q["options"], index=None, key=f"q{i}")

            if answer:
                st.session_state.answers[f"q{i}"] = answer

    # Submit button at the bottom
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📤 Submit Test", use_container_width=True):
            if len(st.session_state.answers) < total_questions:
                st.warning("⚠️ Please answer all questions before submitting.")
            else:
                st.session_state.page = "result"
                st.rerun()

    # Auto-refresh for timer
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

    # Display score in a nice format
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Score", f"{correct}/{total}")
    with col2:
        st.metric("Percentage", f"{percentage:.1f}%")
    with col3:
        if percentage >= 50:
            st.metric("Status", "✅ PASS")
        else:
            st.metric("Status", "❌ FAIL")

    # Save result only once
    if not st.session_state.result_saved:
        with st.spinner("Saving your results..."):
            # Try to save to Google Sheets
            success = save_to_google_sheets(
                st.session_state.student_name,
                st.session_state.student_email,
                correct,
                percentage
            )
            
            if success:
                st.success("✅ Results saved to Google Sheets!")
            else:
                st.info("📁 Results saved locally (backup)")
        
        st.session_state.result_saved = True

    if st.button("📝 View Detailed Corrections"):
        st.session_state.show_correction = True

    if st.session_state.show_correction:

        st.markdown("---")
        st.header("📝 Corrections")

        for i, q in enumerate(st.session_state.questions):

            student_answer = st.session_state.answers.get(f"q{i}")
            correct_answer = q["answer"]

            with st.expander(f"Question {i+1}: {q['question'][:50]}..."):
                st.markdown(f"**Question:** {q['question']}")
                
                if student_answer is None:
                    st.warning("❌ You did not answer this question.")
                    st.info(f"✅ Correct Answer: {correct_answer}")

                elif str(student_answer).strip().lower() == str(correct_answer).strip().lower():
                    st.success(f"✅ Your Answer: {student_answer} (Correct)")

                else:
                    st.error(f"❌ Your Answer: {student_answer}")
                    st.info(f"✅ Correct Answer: {correct_answer}")

        st.markdown("---")
        if st.button("🏠 Return to Login"):
            for key in ['page', 'answers', 'questions', 'show_correction', 'result_saved', 'start_time']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# =============================
# ADMIN DASHBOARD
# =============================
elif st.session_state.page == "admin":

    st.title("📊 Admin Dashboard")

    tab1, tab2, tab3 = st.tabs(["📋 Results", "📤 Upload Questions", "📈 Analytics"])

    with tab1:
        st.subheader("Test Results")
        
        # Get results from Google Sheets
        df = get_all_results()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download Results CSV",
                csv,
                "exam_results.csv",
                "text/csv",
                use_container_width=True
            )
            
            # Show total count
            st.info(f"Total records: {len(df)}")
        else:
            st.info("No results yet.")

    with tab2:
        st.subheader("Upload New Questions")
        st.info("Upload a CSV file with columns: question,option1,option2,option3,option4,answer,type")
        
        uploaded = st.file_uploader("Choose CSV file", type=["csv"])
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                # Validate columns
                required_cols = ['question', 'answer', 'type']
                if all(col in df.columns for col in required_cols):
                    df.to_csv("questions.csv", index=False)
                    st.success("✅ Questions updated successfully!")
                    st.dataframe(df.head())
                else:
                    st.error("CSV must contain: question, answer, and type columns")
            except Exception as e:
                st.error(f"Error uploading file: {str(e)}")

    with tab3:
        st.subheader("Analytics")
        
        # Load data for analytics
        df = get_all_results()
        
        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Students", len(df))
                st.metric("Average Score", f"{df['Score'].mean():.1f}")
            with col2:
                pass_rate = (df['Percentage'] >= 50).mean() * 100
                st.metric("Pass Rate", f"{pass_rate:.1f}%")
                st.metric("Highest Score", df['Score'].max())
            
            # Show distribution
            st.subheader("Score Distribution")
            score_dist = df['Score'].value_counts().sort_index()
            st.bar_chart(score_dist)
            
            # Show recent submissions
            st.subheader("Recent Submissions")
            if 'Timestamp' in df.columns:
                recent = df.sort_values('Timestamp', ascending=False).head(5)
                st.dataframe(recent)
        else:
            st.info("No data available for analytics.")
