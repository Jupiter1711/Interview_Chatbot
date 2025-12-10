import streamlit as st
import google.generativeai as genai
import time
import os
from dotenv import load_dotenv

# --- CẤU HÌNH ---
# Load biến môi trường từ file .env (nếu có)
load_dotenv()

st.set_page_config(
    page_title="AI Interview Coach",
    page_icon="👔",
    layout="wide"
)

# --- CSS TÙY CHỈNH ĐỂ GIAO DIỆN ĐẸP HƠN ---
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 20px;
        font-weight: bold;
    }
    .sidebar-content {
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- KHỞI TẠO SESSION STATE (BỘ NHỚ TẠM) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False
if "feedback_mode" not in st.session_state:
    st.session_state.feedback_mode = False # True nếu đang đợi feedback tổng cuối cùng

# --- SIDEBAR: CẤU HÌNH ---
with st.sidebar:
    st.title("⚙️ Cấu hình Phỏng vấn")
    
    # Xử lý API Key an toàn hơn
    # Ưu tiên lấy từ biến môi trường (file .env)
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        st.success("✅ Đã nạp API Key từ .env")
    else:
        # Nếu không tìm thấy trong .env thì mới hiện ô nhập liệu
        api_key = st.text_input("Nhập Gemini API Key", type="password", help="Lấy key tại aistudio.google.com")
        if not api_key:
            st.warning("⚠️ Chưa có API Key. Vui lòng nhập hoặc thêm vào file .env")
    
    # Cấu hình Gemini nếu đã có key
    if api_key:
        genai.configure(api_key=api_key)
    
    st.markdown("---")
    
    job_position = st.text_input("Vị trí ứng tuyển", "Lập trình viên Python")
    experience_level = st.selectbox("Cấp độ", ["Fresher/Intern", "Junior", "Middle", "Senior"])
    
    mode = st.radio(
        "Chế độ",
        ["Luyện tập (Practice)", "Phỏng vấn thử (Mock Test)"],
        captions=["Nhận xét sau từng câu trả lời", "Phỏng vấn liên tục, nhận xét cuối cùng"]
    )
    
    # Nút bắt đầu chỉ hiện khi đã có API Key
    start_btn = st.button("🚀 Bắt đầu Phỏng vấn", type="primary", disabled=not api_key)
    
    st.markdown("---")
    st.markdown("### Hướng dẫn:")
    st.markdown("- **Luyện tập:** Bot sẽ chấm điểm và sửa lỗi ngay lập tức.")
    st.markdown("- **Phỏng vấn thử:** Bot sẽ phỏng vấn như thật. Bấm 'Kết thúc' để xem kết quả.")

# --- HÀM XỬ LÝ LOGIC ---

def init_chat():
    """Khởi tạo phiên chat mới với Gemini"""
    if not api_key:
        st.error("Vui lòng cung cấp API Key để bắt đầu!")
        return False
        
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') # Sử dụng model mới và nhanh hơn
        
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
            Bắt đầu bằng cách chào và yêu cầu ứng viên giới thiệu bản thân.
            """
        else: # Mock Test
            instruction = base_instruction + """
            Nhiệm vụ:
            1. Đóng vai người phỏng vấn nghiêm túc.
            2. Đặt câu hỏi lần lượt.
            3. KHÔNG đưa ra nhận xét hay đánh giá ngay. Chỉ ghi nhận câu trả lời và hỏi câu tiếp theo (hoặc đào sâu vào câu trả lời nếu cần).
            4. Giữ thái độ chuyên nghiệp, khách quan.
            Bắt đầu bằng cách chào và yêu cầu ứng viên giới thiệu bản thân.
            """
            
        st.session_state.chat_session = model.start_chat(history=[
            {"role": "user", "parts": [instruction]}
        ])
        
        # Lấy lời chào đầu tiên từ Bot
        response = st.session_state.chat_session.send_message("Hãy bắt đầu buổi phỏng vấn.")
        st.session_state.messages = [{"role": "assistant", "content": response.text}]
        st.session_state.interview_active = True
        st.session_state.feedback_mode = False
        return True
        
    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
        return False

def generate_final_feedback():
    """Tạo báo cáo đánh giá cuối cùng cho chế độ Mock Test"""
    if not st.session_state.chat_session:
        return
        
    with st.spinner("Đang tổng hợp kết quả phỏng vấn..."):
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
            st.session_state.feedback_mode = True # Đánh dấu đã xong
        except Exception as e:
            st.error(f"Lỗi khi tạo đánh giá: {e}")

# --- GIAO DIỆN CHÍNH ---

st.title("🤖 Phòng Phỏng Vấn Ảo")
st.caption(f"Đang phỏng vấn vị trí: **{job_position}** | Chế độ: **{mode}**")

# Xử lý nút Bắt đầu
if start_btn:
    if init_chat():
        st.rerun()

# Hiển thị lịch sử chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Khu vực nhập liệu (chỉ hiện khi phỏng vấn đang diễn ra và chưa có kết quả cuối)
if st.session_state.interview_active and not st.session_state.feedback_mode:
    if prompt := st.chat_input("Nhập câu trả lời của bạn..."):
        # 1. Hiển thị câu trả lời của người dùng
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Gửi cho Bot xử lý
        if st.session_state.chat_session:
            with st.chat_message("assistant"):
                with st.spinner("Nhà tuyển dụng đang suy nghĩ..."):
                    try:
                        response = st.session_state.chat_session.send_message(prompt)
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Đã xảy ra lỗi: {e}")

# Nút kết thúc (Chỉ dành cho chế độ Mock Test)
if mode == "Phỏng vấn thử (Mock Test)" and st.session_state.interview_active and not st.session_state.feedback_mode:
    if len(st.session_state.messages) > 2: # Chỉ hiện khi đã có vài câu trao đổi
        if st.button("🏁 Kết thúc & Xem Đánh giá"):
            generate_final_feedback()
            st.rerun()

# Nút Reset (luôn hiện nếu đang active)
if st.session_state.interview_active:
    if st.button("🔄 Phỏng vấn lại từ đầu"):
        st.session_state.messages = []
        st.session_state.interview_active = False
        st.rerun()

# --- FOOTER ---
if not api_key:
    st.info("👈 Vui lòng cấu hình API Key bên thanh bên trái để bắt đầu.")