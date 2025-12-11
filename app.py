import streamlit as st
import google.generativeai as genai
import sqlite3
import hashlib
import uuid
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
# --- Cấu hình --- 
st.set_page_config(
    page_title= "DudesChaseMoney",
    page_icon= "👔",
    layout="wide"
)

# --- Giao diện --- 
st.markdown("""
<style>
    /* --- 1. CỐ ĐỊNH NỀN CHÍNH (QUAN TRỌNG) --- */
    .stApp {
        /* Dùng fixed để nền không bao giờ bị trôi khi cuộn */
        background: radial-gradient(circle at 50% 10%, #1a1a1a 0%, #000000 100%) !important;
        background-attachment: fixed !important;
        background-size: cover !important;
        color: #e0e0e0;
    }

    /* --- 2. XỬ LÝ THANH CHAT (KHẮC PHỤC LỖI MÀU NỀN) --- */
    
    /* Target lớp bao ngoài cùng dưới đáy */
    div[data-testid="stBottom"] {
        background-color: transparent !important;
        background-image: none !important; /* Xóa gradient mặc định nếu có */
        border: none !important;
        box-shadow: none !important;
    }

    /* Target lớp con trực tiếp bên trong (thường là thủ phạm gây ra vệt màu) */
    div[data-testid="stBottom"] > div {
        background-color: transparent !important;
        background-image: none !important;
    }

    /* Tùy chỉnh ô nhập liệu (Viên thuốc) */
    div[data-testid="stChatInput"] {
        background-color: rgba(20, 20, 20, 0.6) !important; /* Đen mờ 60% */
        border: 1px solid rgba(255, 255, 255, 0.15) !important; /* Viền mỏng */
        border-radius: 30px !important; /* Bo tròn */
        backdrop-filter: blur(10px); /* Hiệu ứng kính mờ */
        padding: 5px;
    }

    /* Màu chữ khi gõ */
    div[data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        caret-color: #ffffff !important;
    }
    
    /* Hiệu ứng khi focus vào ô nhập */
    div[data-testid="stChatInput"]:focus-within {
        background-color: rgba(0, 0, 0, 0.8) !important;
        border-color: #ffffff !important;
        box-shadow: 0 0 15px rgba(255, 255, 255, 0.15) !important;
    }

    /* --- 3. CÁC THÀNH PHẦN KHÁC --- */
    
    /* Sidebar đen tuyền */
    [data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #222;
    }

    /* Font chữ tiêu đề */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Helvetica Neue', sans-serif;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Input fields (Text input, Select box...) */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stRadio {
        background-color: #0a0a0a !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
    }

    /* Buttons */
    .stButton button {
        background: linear-gradient(180deg, #333 0%, #000 100%);
        color: white;
        border: 1px solid #555;
        border-radius: 8px;
        text-transform: uppercase;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton button:hover {
        border-color: #fff;
        box-shadow: 0 0 10px rgba(255,255,255,0.2);
    }

    /* Chat Bubbles (Tin nhắn) */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
    }
    .stChatMessage .stChatMessageAvatar {
        background-color: #333 !important;
    }

    /* Ẩn Header mặc định */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Khởi tạo Database --- 
def init_db():
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()

    # 1. Bảng user 
    c.execute('''
         CREATE TABLE IF NOT EXISTS users (
             username TEXT PRIMARY KEY,
             password TEXT
        )
    ''')

    # 2. Bảng History 
    c.execute('''
         CREATE TABLE IF NOT EXISTS history (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT,
             session_id TEXT,
             timestamp TEXT,
             role TEXT,
             content TEXT,
             FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()

def make_hash(password):
    """Mã hóa password bằng SHA256"""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Kiểm tra có khớp mkhau không"""
    if make_hash(password) == hashed_text:
        return True
    return False

def add_user(username, password): 
    """Tạo user mới"""
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()
    hashed_pw = make_hash(password)
    try: 
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False #Trùng username
    finally:
        conn.close()
    
def login_user(username, password): 
    """Xác thực đăng nhập"""
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    data = c.fetchall()
    conn.close()
    if data: 
        if check_hashes(password, data[0][0]):
            return True
    return False

# --- Các hàm lấy lịch sử của đoạn chat --- 
def save_message_to_db(username, session_id, role, content): 
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO history (username, session_id, timestamp, role, content) VALUES (?, ?, ?, ?, ?)', 
              (username, session_id, timestamp, role, content))
    conn.commit()
    conn.close()

def get_user_sessions(username):
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        SELECT session_id, MIN(timestamp) as start_time
        FROM history
        WHERE username = ?
        GROUP BY session_id
        ORDER BY start_time DESC
    ''', (username,))
    data = c.fetchall()
    conn.close()
    return data

def load_history_by_session(session_id): 
    conn = sqlite3.connect('interview_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT role, content FROM history WHERE session_id=? ORDER BY id', (session_id,))
    data = c.fetchall()
    conn.close()
    return data

# --- Khởi tạo Database ---
init_db()

# --- Khởi tạo STATE ---
if "username" not in st.session_state:
    st.session_state.username = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False
if "feedback_mode" not in st.session_state:
    st.session_state.feedback_mode = False

# --- Màn hình Đăng nhập
def login_page(): 
    st.title("Đăng nhập tài khoản")
    tab1, tab2 = st.tabs(['Đăng Nhập', 'Đăng Ký'])
    
    with tab1: 
        username = st.text_input("Tên đăng nhập", key="login_user")
        password = st.text_input("Mật khẩu", type="password", key ="login_pass")
        if st.button("Đăng Nhập"):
            if login_user(username, password):
                st.session_state.username = username
                st.success(f"Chúc mừng {username} quay trở lại!")
                st.rerun()
            else: 
                st.error("Tên đăng nhập hoặc mật khẩu không chính xác")
    
    with tab2:
        new_user = st.text_input("Tên đăng nhập mới", key="reg_user")
        new_pass = st.text_input("Mật khẩu mới", key = "reg_pass")
        if new_user and new_pass:
            if add_user(new_user, new_pass):
                st.success("Tạo tài khoản thành công! Vui lòng chuyển sang tab Đăng nhập")
            else:
                st.warning("Tên đăng nhập đã tồn tại")
        else: 
            st.warning("Vui lòng nhập đủ thông tin đăng kí")
    
# --- Logic Phỏng Vấn --- 

def init_chat(api_key, job_position, experience_level, mode): 
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash') 

        # Xây dựng System Prompt dựa trên chế độ
        base_instruction = f"""
        Bạn là một nhà tuyển dụng chuyên nghiệp, sắc sảo cho vị trí {job_position} cấp độ {experience_level}.
        Luôn giao tiếp bằng Tiếng Việt.
        """
        
        if mode == "Luyện tập (Practice)":
            instruction = base_instruction + """
            Nhiệm vụ:
            1. Đặt câu hỏi phỏng vấn phù hợp.
            2. Chờ ứng viên trả lời.
            3. NGAY LẬP TỨC đánh giá câu trả lời: chấm điểm (thang 10), chỉ ra điểm tốt/xấu, và đưa ra câu trả lời mẫu tối ưu hơn.
            4. Sau đó đặt câu hỏi tiếp theo.
            Bắt đầu bằng cách chào nhưng không cần nói bạn là ai, chỉ cần biết bạn là nhà tuyển dụng và yêu cầu ứng viên giới thiệu bản thân.
            """
        else: # Mock Test
            instruction = base_instruction + """
            Nhiệm vụ:
            1. Đóng vai người phỏng vấn nghiêm túc.
            2. Đặt câu hỏi lần lượt.
            3. KHÔNG đưa ra nhận xét hay đánh giá ngay. Chỉ ghi nhận câu trả lời và hỏi câu tiếp theo (hoặc đào sâu vào câu trả lời nếu cần).
            4. Giữ thái độ chuyên nghiệp, khách quan.
            Bắt đầu bằng cách chào nhưng không cần nói bạn là ai, chỉ cần biết bạn là nhà tuyển dụng và yêu cầu ứng viên giới thiệu bản thân.
            """
        
        st.session_state.chat_session = model.start_chat(history=[
            {"role": "user", "parts": [instruction]}
        ])

        response = st.session_state.chat_session.send_message("Bắt Đầu Đi.")

        # Lưu vào state
        st.session_state.messages = [{"role": "assistant", "content": response.text}]
        # Lưu vào database
        save_message_to_db(st.session_state.username, st.session_state.session_id, "assistant", response.text)

        st.session_state.interview_active = True
        st.session_state.feedback_mode = False
        return True
    except Exception as e:
        st.error(f"Lỗi {e}")
        return False

def generate_final_feedback(): 
    if not st.session_state.chat_session: return 
    with st.spinner("Đang tổng kết..."):
        prompt = """
        Buổi phỏng vấn đã kết thúc. Hãy đóng vai trò là hội đồng tuyển dụng và đưa ra đánh giá tổng thể:
        1. Điểm số chung (thang 10).
        2. Phân tích chi tiết từng câu trả lời của tôi trong suốt buổi phỏng vấn: điểm mạnh, điểm yếu.
        3. Cung cấp phiên bản trả lời tốt hơn cho những câu tôi làm chưa tốt.
        4. Kết luận: Tôi có phù hợp với vị trí này không?
        Trình bày định dạng Markdown rõ ràng, đẹp mắt.
        """
        try:
            response = st.session_state.chat_session.send_message(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            save_message_to_db(st.session_state.username, st.session_state.session_id, "assistant", response.text)
            st.session_state.feedback_mode = True
        except Exception as e:
            st.error(f"Lỗi: {e}")
        
# --- Giao Diện Chính --- 
if not st.session_state.username: 
    login_page()
else: 
    with st.sidebar:
        st.write(f"Xin chào, **{st.session_state.username}**!")
        if st.button("Đăng xuất"): 
            st.session_state.username = None
            st.session_state.interview_active = False
            st.rerun()
        st.title("Cấu hình")
        api_key = os.getenv("GEMINI_API_KEY") or st.text_input("API Key", type="password")

        job_position = st.text_input("Vị trí ứng tuyển", "AI Engineer")
        experience_level = st.selectbox("Cấp bậc", ["Fresher/Intern", "Junior", "Senior", "Manager", "No Specific Level"])
        mode = st.radio(
            "Chế độ",
            ["Luyện tập (Practice)", "Phỏng vấn thử (Mock Test)"],
            captions=["Nhận xét sau từng câu trả lời", "Phỏng vấn liên tục, nhận xét cuối cùng"]
        )
        if st.button("🚀 Bắt đầu mới", type="primary", disabled=not api_key):
            st.session_state.session_id = str(uuid.uuid4())
            if init_chat(api_key, job_position, experience_level, mode):
                st.rerun()
            
        # --- Lịch Sử Sidebar --- 
        st.markdown("---")
        st.subheader("Lịch sử của bạn")
        sessions = get_user_sessions(st.session_state.username)
        if sessions:
            with st.expander("Xem lại các buổi cũ"): 
                for sess_id, start_time in sessions: 
                    if st.button(f"📅 {start_time[:-3]}", key=sess_id):
                        # Load lại tin nhắn cũ
                        old_msgs = load_history_by_session(sess_id)
                        # Chuyển định dạng db sang st.messages
                        st.session_state.messages = []
                        for r, c in old_msgs:
                            role_key = "user" if r == "user" else "assistant"
                            st.session_state.messages.append({"role": role_key, "content": c})
                        st.session_state.interview_active = False
                        st.session_state.feedback_mode = True
                        st.rerun()
    # Khung chat chính
    st.title("🤖 Phòng Phỏng Vấn Ảo")
    st.caption(f"Đang phỏng vấn vị trí: **{job_position}** | Chế độ: **{mode}**")

    # Hiển thị tin nhắn
    for message in st.session_state.messages: 
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Nhập số liệu (Chỉ hiện khi đang active)
    if st.session_state.interview_active and not st.session_state.feedback_mode: 
        if prompt := st.chat_input("Nhập câu trả lời của bạn..."):
            # 1. User
            st.session_state.messages.append({"role": "user", "content": prompt})
            save_message_to_db(st.session_state.username, st.session_state.session_id, "user", prompt)
            with st.chat_message("user"):
                st.markdown(prompt)
        
            # 2. Bot
            if st.session_state.chat_session: 
                with st.chat_message("assistant"): 
                    with st.spinner("Nhà Tuyển Dụng đang suy nghĩ..."):
                        try: 
                            response = st.session_state.chat_session.send_message(prompt)
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            save_message_to_db(st.session_state.username, st.session_state.session_id, "assistant", response.text)
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
    if mode == "Phỏng vấn thử (Mock Test)" and st.session_state.interview_active and not st.session_state.feedback_mode:
        if len(st.session_state.messages) > 2:
            if st.button("🏁 Kết thúc & Chấm điểm"):
                generate_final_feedback()
                st.rerun()

