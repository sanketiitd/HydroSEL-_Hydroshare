import os
import uuid
import mimetypes
import hashlib
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# =========================================
# CONFIG
# =========================================
DB_PATH = "hydro_storage.db"
STORAGE_DIR = "storage"

# =========================================
# APP CONFIG
# =========================================
st.set_page_config(
    page_title="HydroLab Portal",
    layout="wide",
    page_icon="🌊"
)

# =========================================
# ENSURE STORAGE DIRECTORY
# =========================================
os.makedirs(STORAGE_DIR, exist_ok=True)

# =========================================
# DATABASE
# =========================================
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        created_at TEXT
    )
    """)

    # PROJECTS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        owner_id INTEGER,
        supervisor TEXT,
        year INTEGER,
        tags TEXT,
        status TEXT,
        visibility TEXT,
        created_at TEXT
    )
    """)

    # RESOURCES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        project_id INTEGER,
        title TEXT,
        abstract TEXT,
        keywords TEXT,
        file_path TEXT,
        file_name TEXT,
        file_type TEXT,
        visibility TEXT,
        timestamp TEXT
    )
    """)

    # PERMISSIONS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        resource_id INTEGER,
        user_id INTEGER
    )
    """)

    # CREATE DEFAULT ADMIN
    cur.execute("SELECT * FROM users WHERE username='admin'")
    admin = cur.fetchone()

    if not admin:
        cur.execute("""
        INSERT INTO users (username, password, role, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            "admin",
            hash_password("admin123"),
            "admin",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    return conn


conn = init_db()

# =========================================
# SESSION STATE
# =========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None

if "role" not in st.session_state:
    st.session_state.role = None

# =========================================
# AUTH
# =========================================
def login_screen():
    st.title("🌊 HydroLab Portal")
    st.subheader("Research Repository & Collaboration System")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        submit = st.form_submit_button("Login")

        if submit:
            cur = conn.cursor()

            cur.execute("""
            SELECT * FROM users
            WHERE username=?
            """, (username,))

            user = cur.fetchone()

            if user:
                hashed = hash_password(password)

                if hashed == user["password"]:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user["id"]
                    st.session_state.username = user["username"]
                    st.session_state.role = user["role"]

                    st.rerun()

                else:
                    st.error("Incorrect password")

            else:
                st.error("User not found")


# =========================================
# GET RESOURCES
# =========================================
def get_accessible_resources():

    cur = conn.cursor()

    if st.session_state.role == "admin":

        cur.execute("""
        SELECT
            r.id,
            r.owner_id,
            r.project_id,
            r.title,
            r.abstract,
            r.keywords,
            r.file_path,
            r.file_name,
            r.file_type,
            r.visibility,
            r.timestamp,
            u.username AS owner_name,
            p.title AS project_title
        FROM resources r
        LEFT JOIN users u ON r.owner_id = u.id
        LEFT JOIN projects p ON r.project_id = p.id
        ORDER BY r.timestamp DESC
        """)

    else:

        cur.execute("""
        SELECT
            r.id,
            r.owner_id,
            r.project_id,
            r.title,
            r.abstract,
            r.keywords,
            r.file_path,
            r.file_name,
            r.file_type,
            r.visibility,
            r.timestamp,
            u.username AS owner_name,
            p.title AS project_title
        FROM resources r
        LEFT JOIN users u ON r.owner_id = u.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE
            r.visibility='Public'
            OR r.owner_id=?
            OR (
                r.visibility='Custom Private'
                AND r.id IN (
                    SELECT resource_id
                    FROM permissions
                    WHERE user_id=?
                )
            )
        ORDER BY r.timestamp DESC
        """, (
            st.session_state.user_id,
            st.session_state.user_id
        ))

    rows = cur.fetchall()

    columns = [
        "id",
        "owner_id",
        "project_id",
        "title",
        "abstract",
        "keywords",
        "file_path",
        "file_name",
        "file_type",
        "visibility",
        "timestamp",
        "owner_name",
        "project_title"
    ]

    return pd.DataFrame(rows, columns=columns)


# =========================================
# DASHBOARD
# =========================================
def show_dashboard():

    st.title("📊 Dashboard")

    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM projects")
    total_projects = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM resources")
    total_resources = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM resources
    WHERE visibility='Public'
    """)
    public_resources = cur.fetchone()[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Users", total_users)
    c2.metric("Projects", total_projects)
    c3.metric("Resources", total_resources)
    c4.metric("Public Resources", public_resources)

    st.markdown("---")

    st.subheader("Recent Uploads")

    df = get_accessible_resources()

    if not df.empty:

        recent = df[
            [
                "id",
                "title",
                "project_title",
                "owner_name",
                "visibility",
                "timestamp"
            ]
        ].head(10)

        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No uploads yet")


# =========================================
# CREATE PROJECT
# =========================================
def show_projects():

    st.title("📁 Projects")

    tab1, tab2 = st.tabs(["Browse Projects", "Create Project"])

    # =====================================
    # BROWSE PROJECTS
    # =====================================
    with tab1:

        cur = conn.cursor()

        if st.session_state.role == "admin":

            cur.execute("""
            SELECT
                p.*,
                u.username as owner_name
            FROM projects p
            LEFT JOIN users u
            ON p.owner_id = u.id
            ORDER BY p.created_at DESC
            """)

        else:

            cur.execute("""
            SELECT
                p.*,
                u.username as owner_name
            FROM projects p
            LEFT JOIN users u
            ON p.owner_id = u.id
            WHERE
                p.visibility='Public'
                OR p.owner_id=?
            ORDER BY p.created_at DESC
            """, (st.session_state.user_id,))

        rows = cur.fetchall()

        if rows:

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No projects available")

    # =====================================
    # CREATE PROJECT
    # =====================================
    with tab2:

        with st.form("create_project_form"):

            title = st.text_input("Project Title")

            description = st.text_area("Description")

            supervisor = st.text_input("Supervisor")

            year = st.number_input(
                "Year",
                min_value=2000,
                max_value=2100,
                value=datetime.now().year
            )

            tags = st.text_input("Tags")

            status = st.selectbox(
                "Status",
                ["Ongoing", "Completed", "Published"]
            )

            visibility = st.selectbox(
                "Visibility",
                ["Private", "Public"]
            )

            submit = st.form_submit_button("Create Project")

            if submit:

                cur = conn.cursor()

                cur.execute("""
                INSERT INTO projects (
                    title,
                    description,
                    owner_id,
                    supervisor,
                    year,
                    tags,
                    status,
                    visibility,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    description,
                    st.session_state.user_id,
                    supervisor,
                    year,
                    tags,
                    status,
                    visibility,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

                conn.commit()

                st.success("Project created successfully")


# =========================================
# FILE PREVIEW
# =========================================
def preview_file(path, filename):

    ext = os.path.splitext(filename)[1].lower()

    if ext == ".csv":

        try:
            df = pd.read_csv(path)

            st.dataframe(
                df.head(50),
                use_container_width=True
            )

        except:
            st.warning("Cannot preview CSV")

    elif ext in [".png", ".jpg", ".jpeg"]:

        st.image(path, use_container_width=True)

    elif ext in [".txt", ".py", ".md", ".json"]:

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            st.code(text)

        except:
            st.warning("Cannot preview text file")

    else:
        st.info("Preview not available")


### UPLOAD RESOURCE ###


def show_upload():

    st.title("📤 Upload Resource")

    cur = conn.cursor()

    cur.execute("""
    SELECT id, title
    FROM projects
    WHERE
        visibility='Public'
        OR owner_id=?
    """, (st.session_state.user_id,))

    project_rows = cur.fetchall()

    project_options = {
        "No Project": None
    }

    for row in project_rows:
        project_options[f"{row['id']} - {row['title']}"] = row["id"]

    # =====================================
    # VISIBILITY OUTSIDE FORM
    # =====================================
    visibility = st.selectbox(
        "Visibility",
        ["Private", "Public", "Custom Private"]
    )

    # =====================================
    # CUSTOM PRIVATE USER SELECTION
    # =====================================
    selected_users = []

    if visibility == "Custom Private":

        cur.execute("""
        SELECT id, username
        FROM users
        WHERE id != ?
        """, (st.session_state.user_id,))

        users = cur.fetchall()

        user_map = {
            row["username"]: row["id"]
            for row in users
        }

        selected_usernames = st.multiselect(
            "Select Users Who Can Access This File",
            list(user_map.keys())
        )

        selected_users = [
            user_map[name]
            for name in selected_usernames
        ]

    # =====================================
    # FORM
    # =====================================
    with st.form("upload_form"):

        title = st.text_input("Resource Title")

        abstract = st.text_area("Abstract / Description")

        keywords = st.text_input("Keywords")

        selected_project = st.selectbox(
            "Attach to Project",
            list(project_options.keys())
        )

        uploaded_file = st.file_uploader("Select File")

        submit = st.form_submit_button("Upload")

        if submit:

            if uploaded_file is None:
                st.error("Please upload a file")
                return

            filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"

            save_path = os.path.join(STORAGE_DIR, filename)

            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            ext = os.path.splitext(uploaded_file.name)[1]

            project_id = project_options[selected_project]

            cur.execute("""
            INSERT INTO resources (
                owner_id,
                project_id,
                title,
                abstract,
                keywords,
                file_path,
                file_name,
                file_type,
                visibility,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                st.session_state.user_id,
                project_id,
                title,
                abstract,
                keywords,
                save_path,
                uploaded_file.name,
                ext,
                visibility,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            resource_id = cur.lastrowid

            # =====================================
            # SAVE CUSTOM PRIVATE PERMISSIONS
            # =====================================
            if visibility == "Custom Private":

                for uid in selected_users:

                    cur.execute("""
                    INSERT INTO permissions (
                        resource_id,
                        user_id
                    )
                    VALUES (?, ?)
                    """, (
                        resource_id,
                        uid
                    ))

            conn.commit()

            st.success("Resource uploaded successfully")

# =========================================
# EXPLORER
# =========================================
def show_explorer():

    st.title("📂 Data Explorer")

    df = get_accessible_resources()

    if df.empty:
        st.info("No resources available")
        return

    search = st.text_input("Search")

    if search:

        search = search.lower()

        df = df[
            df.astype(str)
            .apply(lambda x: x.str.lower())
            .apply(lambda row: row.str.contains(search).any(), axis=1)
        ]

    st.dataframe(
        df[
            [
                "id",
                "title",
                "project_title",
                "owner_name",
                "file_name",
                "visibility",
                "timestamp"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    selected_id = st.selectbox(
        "Select Resource",
        df["id"].tolist()
    )

    resource = df[df["id"] == selected_id].iloc[0]

    st.subheader(resource["title"])

    st.write("### Metadata")

    st.write("Owner:", resource["owner_name"])
    st.write("Project:", resource["project_title"])
    st.write("Keywords:", resource["keywords"])
    st.write("Visibility:", resource["visibility"])
    st.write("Uploaded:", resource["timestamp"])

    st.write("### Abstract")
    st.write(resource["abstract"])

    st.write("### Preview")

    preview_file(
        resource["file_path"],
        resource["file_name"]
    )

    st.write("### Download")

    with open(resource["file_path"], "rb") as f:

        st.download_button(
            label="Download File",
            data=f.read(),
            file_name=resource["file_name"],
            mime=mimetypes.guess_type(resource["file_name"])[0]
        )


# =========================================
# MY LIBRARY
# =========================================
def show_my_library():

    st.title("📚 My Library")

    cur = conn.cursor()

    cur.execute("""
    SELECT
        r.*,
        p.title as project_title
    FROM resources r
    LEFT JOIN projects p
    ON r.project_id = p.id
    WHERE r.owner_id=?
    ORDER BY r.timestamp DESC
    """, (st.session_state.user_id,))

    rows = cur.fetchall()

    if rows:

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No uploads yet")


# =========================================
# ADMIN PANEL
# =========================================
def show_admin():

    st.title("🛠 Admin Console")

    tab1, tab2 = st.tabs([
        "Create User",
        "All Users"
    ])

    # =====================================
    # CREATE USER
    # =====================================
    with tab1:

        with st.form("create_user_form"):

            username = st.text_input("Username")

            password = st.text_input(
                "Password",
                type="password"
            )

            role = st.selectbox(
                "Role",
                ["user", "admin"]
            )

            submit = st.form_submit_button("Create User")

            if submit:

                cur = conn.cursor()

                try:

                    cur.execute("""
                    INSERT INTO users (
                        username,
                        password,
                        role,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """, (
                        username,
                        hash_password(password),
                        role,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                    conn.commit()

                    st.success("User created successfully")

                except:
                    st.error("Username already exists")

    # =====================================
    # VIEW USERS
    # =====================================
    with tab2:

        cur = conn.cursor()

        cur.execute("""
        SELECT
            id,
            username,
            role,
            created_at
        FROM users
        """)

        rows = cur.fetchall()

        if rows:

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )


# =========================================
# SIDEBAR
# =========================================
def sidebar_navigation():

    st.sidebar.title(f"👋 {st.session_state.username}")

    menu = [
        "Dashboard",
        "Projects",
        "Upload Resource",
        "Data Explorer",
        "My Library"
    ]

    if st.session_state.role == "admin":
        menu.append("Admin Console")

    choice = st.sidebar.radio(
        "Navigation",
        menu
    )

    st.sidebar.markdown("---")

    if st.sidebar.button("Logout"):

        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None

        st.rerun()

    if choice == "Dashboard":
        show_dashboard()

    elif choice == "Projects":
        show_projects()

    elif choice == "Upload Resource":
        show_upload()

    elif choice == "Data Explorer":
        show_explorer()

    elif choice == "My Library":
        show_my_library()

    elif choice == "Admin Console":
        show_admin()


# =========================================
# MAIN
# =========================================
def main():

    if not st.session_state.logged_in:
        login_screen()

    else:
        sidebar_navigation()


# =========================================
# RUN
# =========================================
if __name__ == "__main__":
    main()