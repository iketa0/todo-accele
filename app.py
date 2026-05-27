"""
アクセルプラス やることリスト (Todo アプリ) v4.0

シンプルUI:
- タイトルなし
- 右下に常時固定のFAB（青い丸ボタン、Dropbox風）
- FABを押すとモーダルで追加フォーム表示
- リロードなしでスムーズに開く（HTMLボタン → Streamlitボタン自動クリック）
"""
import streamlit as st
from datetime import datetime, date, timedelta
import sheets_client as sc


APP_VERSION = "v4.0"
APP_VERSION_DATE = "2026-05-27"

ASSIGNEES = ["社長", "kazuki"]
ASSIGNEE_COLORS = {
    "社長": "#1E88E5",   # 青
    "kazuki": "#43A047",  # 緑
}


st.set_page_config(
    page_title="やることリスト",
    page_icon="📋",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ===== Google Sheets 接続 =====
@st.cache_resource
def get_worksheet():
    """ワークシートをキャッシュして取得"""
    service_account_info = dict(st.secrets["gcp_service_account"])
    spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    client = sc.get_client(service_account_info)
    return sc.get_worksheet(client, spreadsheet_id)


try:
    worksheet = get_worksheet()
except Exception as e:
    st.error("⚠️ Google Sheets に接続できません")
    st.code(str(e))
    st.info("Streamlit Secrets の設定を確認してください")
    st.stop()


# ===== セッションステート =====
if 'filter_assignee' not in st.session_state:
    st.session_state.filter_assignee = "全員"
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None


# ===== モーダル：タスク追加 =====
@st.dialog("新しいタスク")
def add_task_dialog():
    new_task = st.text_input(
        "タスク内容",
        placeholder="例: ○○の書類を提出",
    )
    
    new_assignee = st.radio(
        "担当",
        ASSIGNEES,
        horizontal=True,
    )
    
    has_deadline = st.checkbox("期限を設定する", value=False)
    
    if has_deadline:
        new_deadline = st.date_input(
            "期限",
            value=date.today() + timedelta(days=7),
            min_value=date.today() - timedelta(days=30),
            max_value=date.today() + timedelta(days=365),
        )
    else:
        new_deadline = None
    
    if st.button("✅ 追加", type="primary", use_container_width=True):
        if not new_task.strip():
            st.warning("タスク内容を入力してください")
        else:
            deadline_str = new_deadline.strftime('%Y-%m-%d') if new_deadline else ''
            sc.add_task(worksheet, new_task.strip(), new_assignee, deadline_str)
            st.rerun()


# ===== スタイル =====
st.markdown("""
<style>
/* メインコンテナのパディング */
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 120px;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 720px;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.task-card {
    background-color: #1c1f26;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    border-left: 4px solid #555;
}
.task-card.urgent { border-left-color: #FF4B4B; }
.task-card.soon { border-left-color: #FF9800; }
.task-card.thisweek { border-left-color: #FFEB3B; }
.task-card.normal { border-left-color: #607D8B; }

.assignee-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
    color: white;
    margin-right: 8px;
}

.deadline-text {
    font-size: 0.85rem;
    color: #B0BEC5;
}
.deadline-text.urgent {
    color: #FF4B4B;
    font-weight: bold;
}
.deadline-text.soon {
    color: #FF9800;
    font-weight: bold;
}

.section-header {
    font-size: 1.05rem;
    font-weight: bold;
    margin-top: 14px;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #333;
}

.stButton button {
    width: 100%;
    border-radius: 8px;
    font-weight: bold;
}

.stCheckbox > label {
    font-size: 1rem !important;
}
</style>
""", unsafe_allow_html=True)


# ===== フィルタ =====
filter_options = ["全員", "社長", "kazuki"]
filter_choice = st.radio(
    "表示する担当者",
    filter_options,
    horizontal=True,
    label_visibility="collapsed",
    index=filter_options.index(st.session_state.filter_assignee),
)
if filter_choice != st.session_state.filter_assignee:
    st.session_state.filter_assignee = filter_choice
    st.rerun()


# ===== タスク取得 =====
df = sc.fetch_all_tasks(worksheet)

if not df.empty and st.session_state.filter_assignee != "全員":
    df = df[df['assignee'] == st.session_state.filter_assignee]

if not df.empty:
    df_open = df[df['status'] != '完了'].copy()
    df_done = df[df['status'] == '完了'].copy()
else:
    df_open = df
    df_done = df


# ===== 緊急度分類 =====
def categorize(deadline_str):
    if not deadline_str or deadline_str == '':
        return ('none', None)
    try:
        d = datetime.strptime(str(deadline_str), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return ('none', None)
    
    diff = (d - date.today()).days
    if diff < 0:
        return ('overdue', diff)
    elif diff <= 3:
        return ('urgent', diff)
    elif diff <= 7:
        return ('soon', diff)
    elif diff <= 14:
        return ('thisweek', diff)
    else:
        return ('normal', diff)


buckets = {
    'overdue': [],
    'urgent': [],
    'soon': [],
    'thisweek': [],
    'normal': [],
    'none': [],
}

if not df_open.empty:
    for _, row in df_open.iterrows():
        cat, diff = categorize(row['deadline'])
        buckets[cat].append((row, diff))

for key in buckets:
    if key != 'none':
        buckets[key].sort(key=lambda x: x[1] if x[1] is not None else 9999)


# ===== タスクカードの描画 =====
def render_task_card(row, category, diff):
    task_id = int(row['id'])
    task = row['task']
    assignee = row['assignee']
    deadline = row['deadline']
    
    badge_color = ASSIGNEE_COLORS.get(assignee, "#666")
    
    if not deadline or deadline == '':
        deadline_html = '<span class="deadline-text">期限なし</span>'
    elif category == 'overdue':
        deadline_html = f'<span class="deadline-text urgent">⏰ {deadline} ({-diff}日超過)</span>'
    elif category == 'urgent':
        if diff == 0:
            deadline_html = '<span class="deadline-text urgent">⏰ 今日まで</span>'
        else:
            deadline_html = f'<span class="deadline-text urgent">⏰ {deadline} (あと{diff}日)</span>'
    elif category == 'soon':
        deadline_html = f'<span class="deadline-text soon">📅 {deadline} (あと{diff}日)</span>'
    else:
        deadline_html = f'<span class="deadline-text">📅 {deadline}</span>'
    
    css_class = {
        'overdue': 'urgent',
        'urgent': 'urgent',
        'soon': 'soon',
        'thisweek': 'thisweek',
        'normal': 'normal',
        'none': 'normal',
    }[category]
    
    if st.session_state.editing_id == task_id:
        with st.container(border=True):
            st.markdown(f'<span class="assignee-badge" style="background-color: {badge_color};">{assignee}</span>', unsafe_allow_html=True)
            
            edit_task = st.text_input("タスク", value=task, key=f"edit_task_{task_id}")
            edit_assignee = st.radio(
                "担当",
                ASSIGNEES,
                horizontal=True,
                index=ASSIGNEES.index(assignee) if assignee in ASSIGNEES else 0,
                key=f"edit_assignee_{task_id}",
            )
            edit_has_deadline = st.checkbox(
                "期限を設定する",
                value=bool(deadline),
                key=f"edit_has_deadline_{task_id}",
            )
            if edit_has_deadline:
                try:
                    current_deadline = datetime.strptime(str(deadline), '%Y-%m-%d').date() if deadline else date.today()
                except (ValueError, TypeError):
                    current_deadline = date.today()
                edit_deadline = st.date_input(
                    "期限",
                    value=current_deadline,
                    key=f"edit_deadline_{task_id}",
                )
            else:
                edit_deadline = None
            
            col_x, col_y, col_z = st.columns(3)
            with col_x:
                if st.button("💾 保存", key=f"save_{task_id}", type="primary", use_container_width=True):
                    deadline_str = edit_deadline.strftime('%Y-%m-%d') if edit_deadline else ''
                    sc.update_task(
                        worksheet,
                        task_id,
                        task=edit_task.strip(),
                        assignee=edit_assignee,
                        deadline=deadline_str,
                    )
                    st.session_state.editing_id = None
                    st.rerun()
            with col_y:
                if st.button("🗑️ 削除", key=f"delete_{task_id}", use_container_width=True):
                    sc.delete_task(worksheet, task_id)
                    st.session_state.editing_id = None
                    st.rerun()
            with col_z:
                if st.button("❌ 戻る", key=f"cancel_{task_id}", use_container_width=True):
                    st.session_state.editing_id = None
                    st.rerun()
    else:
        col1, col2, col3 = st.columns([1, 6, 2])
        with col1:
            if st.checkbox(
                "完了",
                value=False,
                key=f"check_{task_id}",
                label_visibility="collapsed",
            ):
                sc.update_task_status(worksheet, task_id, '完了')
                st.rerun()
        with col2:
            st.markdown(
                f'<div class="task-card {css_class}">'
                f'<span class="assignee-badge" style="background-color: {badge_color};">{assignee}</span>'
                f'<span style="font-size: 1rem;">{task}</span><br>'
                f'{deadline_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col3:
            if st.button("✏️", key=f"edit_{task_id}", help="編集", use_container_width=True):
                st.session_state.editing_id = task_id
                st.rerun()


# ===== 緊急度別に表示 =====
section_definitions = [
    ('overdue', '🔴 期限超過'),
    ('urgent', '🔴 緊急(3日以内)'),
    ('soon', '🟠 1週間以内'),
    ('thisweek', '🟡 2週間以内'),
    ('normal', '⚪ それ以降'),
    ('none', '◽ 期限なし'),
]

total_open = sum(len(buckets[k]) for k in buckets)

if df.empty:
    st.info("まだタスクがありません。右下の「＋」ボタンから追加してください。")
elif total_open == 0:
    st.success("🎉 未完了タスクはありません！")
else:
    for key, label in section_definitions:
        items = buckets[key]
        if not items:
            continue
        st.markdown(f'<div class="section-header">{label} ({len(items)}件)</div>', unsafe_allow_html=True)
        for row, diff in items:
            render_task_card(row, key, diff)


# ===== 完了済みタスク =====
if not df_done.empty:
    st.markdown("---")
    with st.expander(f"✅ 完了済み ({len(df_done)}件)", expanded=False):
        for _, row in df_done.iterrows():
            task_id = int(row['id'])
            task = row['task']
            assignee = row['assignee']
            badge_color = ASSIGNEE_COLORS.get(assignee, "#666")
            
            col1, col2, col3 = st.columns([1, 6, 2])
            with col1:
                if st.checkbox(
                    "戻す",
                    value=True,
                    key=f"check_done_{task_id}",
                    label_visibility="collapsed",
                ):
                    pass
                else:
                    sc.update_task_status(worksheet, task_id, '未完了')
                    st.rerun()
            with col2:
                st.markdown(
                    f'<div style="opacity: 0.6;">'
                    f'<span class="assignee-badge" style="background-color: {badge_color};">{assignee}</span>'
                    f'<span style="text-decoration: line-through;">{task}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col3:
                if st.button("🗑️", key=f"delete_done_{task_id}", help="完全に削除", use_container_width=True):
                    sc.delete_task(worksheet, task_id)
                    st.rerun()


# ===== 右下固定 FAB =====
# Streamlit 1.36+ は key を持つウィジェットの親 div に `.st-key-<key>` クラスを付ける。
# それを CSS で `position: fixed` で右下に固定し、丸い青ボタンに整形する。
# st.dialog はネイティブの click → rerun フローで安定して開く。
st.markdown("""
<style>
div.st-key-fab_add {
    position: fixed;
    bottom: 80px;
    right: 24px;
    width: auto;
    z-index: 99999;
}

div.st-key-fab_add button {
    width: 60px;
    height: 60px;
    min-height: 60px;
    border-radius: 50%;
    background-color: #1976D2;
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.2);
    cursor: pointer;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
    -webkit-tap-highlight-color: transparent;
}

div.st-key-fab_add button:hover {
    background-color: #1E88E5;
    color: white;
    border: none;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.3);
    transform: scale(1.05);
}

div.st-key-fab_add button:active,
div.st-key-fab_add button:focus {
    background-color: #1565C0;
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

div.st-key-fab_add button p,
div.st-key-fab_add button div {
    font-size: 32px;
    font-weight: 300;
    line-height: 1;
    margin: 0;
}

@media (max-width: 640px) {
    div.st-key-fab_add {
        bottom: 45px;
        right: 16px;
    }
    div.st-key-fab_add button {
        width: 56px;
        height: 56px;
        min-height: 56px;
    }
    div.st-key-fab_add button p,
    div.st-key-fab_add button div {
        font-size: 28px;
    }
}
</style>
""", unsafe_allow_html=True)

if st.button("＋", key="fab_add", help="新しいタスクを追加"):
    add_task_dialog()
