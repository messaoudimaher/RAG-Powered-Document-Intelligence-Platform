import os
import streamlit as st
import httpx
import pandas as pd
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="CogniFlow Operations Desk",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Read environment variables
API_BASE_URL = os.environ.get("BACKEND_API_URL", os.environ.get("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")).rstrip("/")

# ----------------------------------------------------
# STYLING & GRAPHICS
# ----------------------------------------------------
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .main-title {
        font-family: 'Outfit', 'Inter', sans-serif;
        color: #f0f2f6;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
        background: -webkit-linear-gradient(45deg, #3b82f6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-title {
        font-family: 'Inter', sans-serif;
        color: #9ca3af;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .badge-high {
        background-color: #065f46;
        color: #34d399;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-medium {
        background-color: #92400e;
        color: #fbbf24;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-low {
        background-color: #7f1d1d;
        color: #fca5a5;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .metric-card {
        background-color: #1f2937;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #374151;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# STATE MANAGEMENT
# ----------------------------------------------------
if "auth_token" not in st.session_state:
    st.session_state.auth_token = ""
if "username" not in st.session_state:
    st.session_state.username = ""

# Headers generator
def get_headers():
    headers = {}
    if st.session_state.auth_token:
        headers["Authorization"] = f"Bearer {st.session_state.auth_token}"
    return headers

# ----------------------------------------------------
# SIDEBAR: DIAGNOSTICS & AUTH
# ----------------------------------------------------
with st.sidebar:
    st.markdown("### 🔒 Authentication")
    
    if st.session_state.auth_token:
        st.success(f"Logged in as: **{st.session_state.username}**")
        if st.button("Logout", use_container_width=True):
            st.session_state.auth_token = ""
            st.session_state.username = ""
            st.rerun()
    else:
        auth_mode = st.radio("Access Mode", ["Sign In", "Create Account"])
        username = st.text_input("Username", key="auth_username")
        password = st.text_input("Password", type="password", key="auth_password")
        
        if auth_mode == "Sign In":
            if st.button("Login", type="primary", use_container_width=True):
                if not username or not password:
                    st.warning("Please provide username and password.")
                else:
                    try:
                        with httpx.Client() as client:
                            resp = client.post(
                                f"{API_BASE_URL}/api/auth/login",
                                json={"username": username, "password": password}
                            )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.auth_token = data.get("access_token")
                            st.session_state.username = data.get("username")
                            st.success("Successfully logged in!")
                            st.rerun()
                        else:
                            st.error(f"Login failed: {resp.json().get('detail', 'Invalid credentials.')}")
                    except Exception as e:
                        st.error(f"Failed to communicate with auth server: {e}")
        else:
            if st.button("Register", type="primary", use_container_width=True):
                if not username or not password:
                    st.warning("Please provide username and password.")
                else:
                    try:
                        with httpx.Client() as client:
                            resp = client.post(
                                f"{API_BASE_URL}/api/auth/register",
                                json={"username": username, "password": password}
                            )
                        if resp.status_code == 201:
                            st.success("Registered successfully! You can now log in.")
                        else:
                            st.error(f"Registration failed: {resp.json().get('detail', 'Username exists or is invalid.')}")
                    except Exception as e:
                        st.error(f"Failed to communicate with auth server: {e}")
    
    st.markdown("---")
    st.markdown("### 🖥️ Diagnostics & Metrics")
    
    # Check Server Health
    health_ok = False
    diagnostics = {}
    
    if st.session_state.auth_token:
        try:
            with httpx.Client() as client:
                diag_resp = client.get(f"{API_BASE_URL}/api/diagnostics", headers=get_headers(), timeout=5.0)
                if diag_resp.status_code == 200:
                    health_ok = True
                    diagnostics = diag_resp.json()
                elif diag_resp.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    st.session_state.auth_token = ""
                    st.session_state.username = ""
                    st.rerun()
                else:
                    st.warning(f"Server responded with status code: {diag_resp.status_code}")
        except Exception as e:
            st.error(f"Cannot connect to FastAPI backend: {e}")
            st.caption(f"Configured API URL: {API_BASE_URL}")
    else:
        st.info("Please log in to view system diagnostics.")
        
    if health_ok and diagnostics:
        # Health status indicator
        status_color = "🟢 Healthy" if diagnostics.get("status") == "healthy" else "🟡 Degraded"
        st.markdown(f"**System Status:** {status_color}")
        
        # Details
        uptime_sec = diagnostics.get("uptime_seconds", 0)
        uptime_str = str(datetime.utcfromtimestamp(uptime_sec).strftime('%Hh %Mm %Ss')) if uptime_sec < 86400 else f"{int(uptime_sec // 86400)}d {int((uptime_sec % 86400) // 3600)}h"
        
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">SYSTEM UPTIME</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: #f3f4f6;">{uptime_str}</div>
            </div>
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">PUBLIC COLLECTION</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #60a5fa;">{diagnostics.get('public_count', 0)} <span style="font-size: 0.8rem; font-weight: normal; color: #9ca3af;">chunks</span></div>
            </div>
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">PAPERS COLLECTION</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #2dd4bf;">{diagnostics.get('papers_count', 0)} <span style="font-size: 0.8rem; font-weight: normal; color: #9ca3af;">chunks</span></div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Connections
        st.markdown(f"🤖 **Ollama Connection:** {'🟢 Connected' if diagnostics.get('ollama_connected') else '🔴 Offline'}")
        st.markdown(f"🗄️ **ChromaDB SQLite:** {'🟢 Mounted' if diagnostics.get('chroma_connected') else '🔴 Error'}")
        st.caption(f"Git Commit SHA: `{diagnostics.get('git_sha', 'dev')}`")
        st.caption("CogniFlow Engine v1.0.0")
    else:
        st.markdown("**System Status:** 🔴 Offline")
        st.caption("Check if FastAPI server is running and API URL is correct.")

# ----------------------------------------------------
# MAIN HEADER
# ----------------------------------------------------
st.markdown('<div class="main-title">CogniFlow Intelligence Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Local-first grounded Q&A and vector document operations cockpit</div>', unsafe_allow_html=True)

if not st.session_state.auth_token:
    st.warning("🔒 **Security Gate: Authentication Required**")
    st.info("Please sign in or create a user account in the sidebar authentication panel to access your isolated document workspace.")
    st.stop()

# Create layout tabs
tab_query, tab_ingest, tab_library = st.tabs(["🔍 RAG Query Workspace", "📥 Document Ingest Panel", "📚 Source File Library"])

# ----------------------------------------------------
# TAB 1: QUERY WORKSPACE
# ----------------------------------------------------
with tab_query:
    col_opts, col_results = st.columns([1, 2])
    
    with col_opts:
        st.markdown("### ⚙️ Search Configuration")
        target_collection = st.selectbox(
            "Collection Selection",
            options=["public", "papers"],
            format_func=lambda x: "🌐 Bulk Text (public)" if x == "public" else "📄 PDFs & DOCX (papers)",
            help="Select the vector database search space."
        )
        
        search_strategy = st.selectbox(
            "Retrieval Strategy",
            options=["baseline", "hyde", "multi_query", "flare"],
            format_func=lambda x: {
                "baseline": "Vector Similarity (Baseline)",
                "hyde": "Hypothetical Embedding (HyDE)",
                "multi_query": "Multi-Query + Rank Fusion (RRF)",
                "flare": "Active Claim Lookahead (FLARE)"
            }[x],
            help="Choose the algorithm used to fetch and synthesize context."
        )
        
        chunk_limit = st.slider(
            "Max Citations Limit",
            min_value=1,
            max_value=15,
            value=5,
            help="Maximum number of context chunks retrieved to synthesize the answer."
        )
        
        enable_rerank = st.checkbox(
            "Enable BGE Re-ranking",
            value=False,
            disabled=(search_strategy == "flare"),
            help="Performs a secondary neural cross-encoder re-ranking pass on the retrieved document chunks."
        )
        
        st.info(
            "💡 **Strategies:**\n"
            "- **HyDE** generates a mock answer first to match real doc layouts.\n"
            "- **Multi-Query** searches 3 variations and merges ranks with Reciprocal Rank Fusion.\n"
            "- **FLARE** dynamically queries missing details during generation."
        )

    with col_results:
        st.markdown("### 💬 Ask the Corpus")
        user_query = st.text_area(
            "Query / Question", 
            placeholder="Type your question here (e.g. 'What is Reciprocal Rank Fusion?')...",
            height=100
        )
        
        if st.button("Generate Answer", type="primary", use_container_width=True):
            if not user_query.strip():
                st.warning("Please enter a query question.")
            else:
                with st.spinner("Executing retrieval and synthesis..."):
                    try:
                        payload = {
                            "collection_type": target_collection,
                            "query": user_query,
                            "strategy": search_strategy,
                            "limit": chunk_limit,
                            "rerank": enable_rerank and search_strategy != "flare"
                        }
                        
                        with httpx.Client() as client:
                            resp = client.post(
                                f"{API_BASE_URL}/api/query", 
                                headers=get_headers(), 
                                json=payload,
                                timeout=60.0
                            )
                            
                        if resp.status_code == 200:
                            data = resp.json()
                            answer = data.get("answer", "")
                            citations = data.get("citations", [])
                            confidence = data.get("overall_confidence", "Low")
                            
                            # Render Confidence Indicator
                            badge_class = f"badge-{confidence.lower()}"
                            st.markdown(f"#### Grounded Answer (Confidence: <span class='{badge_class}'>{confidence}</span>)", unsafe_allow_html=True)
                            st.write(answer)
                            
                            # Render Source Citations
                            st.markdown("### 📌 Source Citations")
                            if not citations:
                                st.caption("No relevant source citations fetched above threshold.")
                            else:
                                for idx, cite in enumerate(citations):
                                    source_title = cite.get("title") or cite.get("source")
                                    dist = cite.get("distance", 0)
                                    cite_conf = cite.get("confidence", "Low")
                                    cite_badge = f"badge-{cite_conf.lower()}"
                                    
                                    with st.expander(f"[{idx+1}] {source_title} (Distance: {dist:.4f} | Confidence: {cite_conf})"):
                                        st.caption(f"**Source Document:** `{cite.get('source')}` | **Chunk:** {cite.get('chunk_idx', 0) + 1}/{cite.get('total_chunks', 1)}")
                                        st.markdown(f"*{cite.get('text')}*")
                        else:
                            st.error(f"Error {resp.status_code}: {resp.json().get('detail', 'Query failed.')}")
                    except Exception as e:
                        st.error(f"Failed to submit query: {e}")

# ----------------------------------------------------
# TAB 2: INGEST PANEL
# ----------------------------------------------------
with tab_ingest:
    col_ingest_opts, col_ingest_action = st.columns([1, 2])
    
    with col_ingest_opts:
        st.markdown("### ⚙️ Ingestion Settings")
        ingest_collection = st.selectbox(
            "Target Ingest Index",
            options=["public", "papers"],
            format_func=lambda x: "🌐 Bulk Text (public)" if x == "public" else "📄 PDFs & DOCX (papers)",
            help="Choose the index to store the vectorized chunks."
        )
        st.caption("Max file upload size is set by system configuration (default 15MB).")
        
    with col_ingest_action:
        st.markdown("### 📤 Document Upload")
        ingest_mode = st.radio("Choose Ingestion Source", ["File Upload (PDF, DOCX, TXT)", "arXiv Research ID"])
        
        if ingest_mode == "File Upload (PDF, DOCX, TXT)":
            uploaded_file = st.file_uploader("Drag & Drop File", type=["pdf", "docx", "txt", "md"])
            if st.button("Process & Vectorize File", type="primary", use_container_width=True):
                if not uploaded_file:
                    st.warning("Please upload a file first.")
                else:
                    with st.spinner(f"Ingesting '{uploaded_file.name}'... Please wait."):
                        try:
                            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                            data = {"collection_type": ingest_collection}
                            
                            with httpx.Client() as client:
                                resp = client.post(
                                    f"{API_BASE_URL}/api/ingest",
                                    headers=get_headers(),
                                    data=data,
                                    files=files,
                                    timeout=120.0
                                )
                                
                            if resp.status_code == 200:
                                res_data = resp.json()
                                task_id = res_data.get("task_id")
                                
                                import time
                                status_placeholder = st.empty()
                                progress_bar = st.progress(0.1)
                                
                                while True:
                                    with httpx.Client() as client:
                                        status_resp = client.get(
                                            f"{API_BASE_URL}/api/ingest/status/{task_id}",
                                            headers=get_headers()
                                        )
                                    if status_resp.status_code == 200:
                                        status_data = status_resp.json()
                                        task_status = status_data.get("status")
                                        
                                        if task_status in ["PENDING", "RECEIVED"]:
                                            status_placeholder.info("Stage: Task in queue...")
                                            progress_bar.progress(0.2)
                                        elif task_status == "STARTED":
                                            status_placeholder.info("Stage: Parsing and embedding chunks...")
                                            progress_bar.progress(0.6)
                                        elif task_status == "SUCCESS":
                                            progress_bar.progress(1.0)
                                            result = status_data.get("result") or {}
                                            status_placeholder.success(f"Successfully processed document! Vectorized into {result.get('chunks_count', 0)} chunks.")
                                            st.balloons()
                                            break
                                        elif task_status == "FAILURE":
                                            progress_bar.empty()
                                            status_placeholder.error(f"Ingestion failed: {status_data.get('error')}")
                                            break
                                    else:
                                        progress_bar.empty()
                                        status_placeholder.error(f"Failed to query task status ({status_resp.status_code})")
                                        break
                                    time.sleep(1.5)
                            else:
                                st.error(f"Ingestion failed ({resp.status_code}): {resp.json().get('detail', 'Unknown error.')}")
                        except Exception as e:
                            st.error(f"Failed to ingest file: {e}")
                            
        elif ingest_mode == "arXiv Research ID":
            arxiv_id = st.text_input("arXiv Paper ID", placeholder="e.g. 2305.16300 or 1706.03762")
            if st.button("Download & Index arXiv Paper", type="primary", use_container_width=True):
                if not arxiv_id.strip():
                    st.warning("Please enter a valid arXiv ID.")
                else:
                    with st.spinner(f"Downloading and indexing arXiv paper '{arxiv_id}'..."):
                        try:
                            payload = {
                                "arxiv_id": arxiv_id.strip(),
                                "collection_type": ingest_collection
                            }
                            
                            with httpx.Client() as client:
                                resp = client.post(
                                    f"{API_BASE_URL}/api/ingest/arxiv",
                                    headers=get_headers(),
                                    json=payload,
                                    timeout=180.0
                                )
                                
                            if resp.status_code == 200:
                                res_data = resp.json()
                                task_id = res_data.get("task_id")
                                
                                import time
                                status_placeholder = st.empty()
                                progress_bar = st.progress(0.1)
                                
                                while True:
                                    with httpx.Client() as client:
                                        status_resp = client.get(
                                            f"{API_BASE_URL}/api/ingest/status/{task_id}",
                                            headers=get_headers()
                                        )
                                    if status_resp.status_code == 200:
                                        status_data = status_resp.json()
                                        task_status = status_data.get("status")
                                        
                                        if task_status in ["PENDING", "RECEIVED"]:
                                            status_placeholder.info("Stage: Downloading publication from arXiv...")
                                            progress_bar.progress(0.3)
                                        elif task_status == "STARTED":
                                            status_placeholder.info("Stage: Generating chunk vector embeddings...")
                                            progress_bar.progress(0.7)
                                        elif task_status == "SUCCESS":
                                            progress_bar.progress(1.0)
                                            result = status_data.get("result") or {}
                                            status_placeholder.success(f"Indexed arXiv Paper: '{result.get('title')}' into papers collection ({result.get('chunks_count', 0)} chunks).")
                                            st.balloons()
                                            break
                                        elif task_status == "FAILURE":
                                            progress_bar.empty()
                                            status_placeholder.error(f"arXiv indexing failed: {status_data.get('error')}")
                                            break
                                    else:
                                        progress_bar.empty()
                                        status_placeholder.error(f"Failed to query task status ({status_resp.status_code})")
                                        break
                                    time.sleep(1.5)
                            else:
                                st.error(f"arXiv indexing failed ({resp.status_code}): {resp.json().get('detail', 'Unknown error.')}")
                        except Exception as e:
                            st.error(f"Failed to fetch arXiv paper: {e}")

# ----------------------------------------------------
# TAB 3: SOURCE FILE LIBRARY
# ----------------------------------------------------
with tab_library:
    st.markdown("### 📚 Ingested Documents Registry")
    lib_collection = st.selectbox(
        "Library View Collection",
        options=["public", "papers"],
        format_func=lambda x: "🌐 Bulk Text (public)" if x == "public" else "📄 PDFs & DOCX (papers)"
    )
    
    # Fetch document list
    docs = []
    fetch_ok = False
    try:
        with httpx.Client() as client:
            resp = client.get(
                f"{API_BASE_URL}/api/documents?collection_type={lib_collection}", 
                headers=get_headers(), 
                timeout=10.0
            )
            if resp.status_code == 200:
                docs = resp.json()
                fetch_ok = True
            else:
                st.error(f"Failed to fetch library ({resp.status_code}): {resp.json().get('detail')}")
    except Exception as e:
        st.error(f"Error querying library: {e}")
        
    if fetch_ok:
        if not docs:
            st.info("No documents have been indexed in this collection yet.")
        else:
            # Map into DataFrame
            df = pd.DataFrame(docs)
            df.columns = ["Source Filename", "Document Title", "Chunk Count", "File Format", "Date Indexed"]
            
            # Format date string for readability
            try:
                df["Date Indexed"] = df["Date Indexed"].apply(lambda x: datetime.fromisoformat(x).strftime("%Y-%m-%d %H:%M:%S") if x != "unknown" else x)
            except Exception:
                pass
                
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("### 🗑️ Delete Document Index")
            doc_to_delete = st.selectbox(
                "Select Document to Remove",
                options=[d["source"] for d in docs],
                format_func=lambda x: next((d["title"] for d in docs if d["source"] == x), x)
            )
            
            if st.button("Permanently Remove Document", type="secondary", use_container_width=True):
                with st.spinner(f"Deleting document '{doc_to_delete}'..."):
                    try:
                        with httpx.Client() as client:
                            del_resp = client.request(
                                "DELETE",
                                f"{API_BASE_URL}/api/documents?collection_type={lib_collection}&source={doc_to_delete}",
                                headers=get_headers(),
                                timeout=10.0
                            )
                        if del_resp.status_code == 200:
                            st.success(f"Successfully deleted '{doc_to_delete}' from vector store.")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete ({del_resp.status_code}): {del_resp.json().get('detail')}")
                    except Exception as e:
                        st.error(f"Failed to delete document: {e}")
