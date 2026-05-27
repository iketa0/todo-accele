"""
Google Sheets API クライアント

タスクの読み込み・追加・更新・削除を担当
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd


SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

SHEET_NAME = 'tasks'  # シート名


def get_client(service_account_info):
    """サービスアカウント情報から gspread クライアントを作成
    
    Args:
        service_account_info: dict (JSON の中身)
    
    Returns:
        gspread.Client
    """
    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_worksheet(client, spreadsheet_id):
    """スプレッドシートからワークシートを取得"""
    sh = client.open_by_key(spreadsheet_id)
    return sh.worksheet(SHEET_NAME)


def fetch_all_tasks(worksheet):
    """全タスクを DataFrame で取得
    
    Returns:
        pd.DataFrame: id, task, assignee, deadline, status, created_at
    """
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=['id', 'task', 'assignee', 'deadline', 'status', 'created_at'])
    df = pd.DataFrame(records)
    # 型変換
    if 'id' in df.columns:
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    return df


def add_task(worksheet, task, assignee, deadline):
    """タスクを追加
    
    Args:
        worksheet: gspread Worksheet
        task: タスク内容（文字列）
        assignee: 担当者（"社長" or "kazuki"）
        deadline: 期限（YYYY-MM-DD形式の文字列、または空文字列）
    
    Returns:
        新規タスクの id
    """
    # 既存タスクから最大IDを取得
    df = fetch_all_tasks(worksheet)
    if df.empty or 'id' not in df.columns:
        new_id = 1
    else:
        new_id = int(df['id'].max()) + 1
    
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    row = [
        new_id,
        task,
        assignee,
        deadline if deadline else '',
        '未完了',
        now_str,
    ]
    worksheet.append_row(row, value_input_option='USER_ENTERED')
    return new_id


def update_task_status(worksheet, task_id, new_status):
    """タスクのステータスを更新
    
    Args:
        worksheet: gspread Worksheet
        task_id: 更新するタスクのID
        new_status: "完了" or "未完了"
    """
    all_values = worksheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return False
    
    header = all_values[0]
    
    try:
        id_col = header.index('id')
        status_col = header.index('status')
    except ValueError:
        return False
    
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[id_col]) == str(task_id):
            cell_address = gspread.utils.rowcol_to_a1(i, status_col + 1)
            worksheet.update(cell_address, [[new_status]])
            return True
    return False


def delete_task(worksheet, task_id):
    """タスクを削除（行ごと削除）"""
    all_values = worksheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return False
    
    header = all_values[0]
    try:
        id_col = header.index('id')
    except ValueError:
        return False
    
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[id_col]) == str(task_id):
            worksheet.delete_rows(i)
            return True
    return False


def update_task(worksheet, task_id, task=None, assignee=None, deadline=None):
    """タスクの内容を更新（部分更新可）
    
    Args:
        worksheet: gspread Worksheet
        task_id: 更新するタスクのID
        task: 新しいタスク内容（None なら更新しない）
        assignee: 新しい担当者（None なら更新しない）
        deadline: 新しい期限（None なら更新しない）
    """
    all_values = worksheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return False
    
    header = all_values[0]
    try:
        id_col = header.index('id')
    except ValueError:
        return False
    
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[id_col]) == str(task_id):
            updates = []
            if task is not None and 'task' in header:
                col_idx = header.index('task') + 1
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(i, col_idx),
                    'values': [[task]],
                })
            if assignee is not None and 'assignee' in header:
                col_idx = header.index('assignee') + 1
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(i, col_idx),
                    'values': [[assignee]],
                })
            if deadline is not None and 'deadline' in header:
                col_idx = header.index('deadline') + 1
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(i, col_idx),
                    'values': [[deadline]],
                })
            if updates:
                worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            return True
    return False
