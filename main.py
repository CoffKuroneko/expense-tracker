
from flask import Flask, request, redirect, url_for
import sqlite3
from datetime import date
from html import escape

app = Flask(__name__)
DB = "kakeibo.db"

CATEGORIES = [
    "食費",
    "日用品",
    "医療費",
    "交通費",
    "娯楽費",
    "衣服費",
    "その他",
    "No Spend Day"
]


def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount INTEGER NOT NULL,
                memo TEXT NOT NULL DEFAULT ''
            )
        """)

        # 既存DBに備考列がなければ追加
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(expenses)")
        ]

        if "memo" not in columns:
            conn.execute(
                "ALTER TABLE expenses "
                "ADD COLUMN memo TEXT NOT NULL DEFAULT ''"
            )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )

    return redirect(
        url_for(
            "index",
            month=request.args.get(
                "month", date.today().strftime("%Y-%m")
            )
        )
    )


@app.route("/", methods=["GET", "POST"])
def index():
    month = request.args.get(
        "month", date.today().strftime("%Y-%m")
    )
    year, month_num = map(int, month.split("-"))

    # 前月
    if month_num == 1:
        prev_month = f"{year - 1}-12"
    else:
        prev_month = f"{year}-{month_num - 1:02d}"

    # 翌月
    if month_num == 12:
        next_month = f"{year + 1}-01"
    else:
        next_month = f"{year}-{month_num + 1:02d}"

    if request.method == "POST":
        day = request.form["date"]
        category = request.form["category"]
        amount = int(request.form["amount"])
        memo = request.form.get("memo", "").strip()

        if amount >= 0:
            with sqlite3.connect(DB) as conn:
                conn.execute(
                    """
                    INSERT INTO expenses
                        (date, category, amount, memo)
                    VALUES (?, ?, ?, ?)
                    """,
                    (day, category, amount, memo)
                )

            return redirect(f"/?month={day[:7]}")

    with sqlite3.connect(DB) as conn:
        expenses = conn.execute(
            """
            SELECT id, date, category, amount, memo
            FROM expenses
            WHERE substr(date, 1, 7) = ?
            ORDER BY date DESC, id DESC
            """,
            (month,)
        ).fetchall()

        total, days = conn.execute(
            """
            SELECT
                COALESCE(SUM(amount), 0),
                COUNT(DISTINCT date)
            FROM expenses
            WHERE substr(date, 1, 7) = ?
            """,
            (month,)
        ).fetchone()

        # 項目別の月間集計
        category_totals = dict(conn.execute(
            """
            SELECT category, SUM(amount)
            FROM expenses
            WHERE substr(date, 1, 7) = ?
            GROUP BY category
            """,
            (month,)
        ).fetchall())

        # 日別集計
        daily_totals = conn.execute(
            """
            SELECT date, SUM(amount)
            FROM expenses
            WHERE substr(date, 1, 7) = ?
            GROUP BY date
            ORDER BY date DESC
            """,
            (month,)
        ).fetchall()

    average = total / days if days > 0 else 0

    # グラフに表示する項目
    graph_categories = [
        category for category in CATEGORIES
        if category != "No Spend Day"
    ]

    # 過去に登録した項目も表示
    for category in category_totals:
        if (
            category != "No Spend Day"
            and category not in graph_categories
        ):
            graph_categories.append(category)

    # グラフの最大値
    max_amount = max(
        (
            category_totals.get(category, 0)
            for category in graph_categories
        ),
        default=0
    )

    # 項目別グラフの生成
    graph_rows = ""

    for category in graph_categories:
        amount = category_totals.get(category, 0)

        width = (
            amount / max_amount * 100
            if max_amount > 0 else 0
        )

        graph_rows += f"""
        <div class="graph-item">
            <div class="graph-label">
                <span>{escape(category)}</span>
                <span>{amount:,}円</span>
            </div>
            <div class="graph-track">
                <div class="graph-bar"
                     style="width: {width:.2f}%;">
                </div>
            </div>
        </div>
        """

    
    # 日別グラフの最大値
    daily_max = max(
        (amount for day, amount in daily_totals),
        default=0
    )

    # 日別グラフの生成
    daily_graph_rows = ""

    for day, amount in daily_totals:

        width = (
            amount / daily_max * 100
            if daily_max > 0 else 0
        )

        color = (
            "#4caf50" if amount <= 1000
            else "#c4a48b"
        )

        amount_label = (
            "No Spend Day"
            if amount == 0
            else f"{amount:,}円"
        )

        daily_graph_rows += f"""
        <div class="graph-item">
            <div class="graph-label">
                <span>{escape(day)}</span>
                <span style="color: {color};">
                    {amount_label}
                </span>
            </div>
            <div class="graph-track">
                <div class="graph-bar"
                     style="width: {width:.2f}%;
                            background-color: {color};">
                </div>
            </div>
        </div>
        """

    if not daily_graph_rows:
        daily_graph_rows = "<p>登録データがありません。</p>"

    # 項目選択肢
    options = "".join(
        f"<option>{escape(category)}</option>"
        for category in CATEGORIES
    )

    rows = "".join(
        f"""
        <tr>
            <td>{escape(day)}</td>
            <td>{escape(category)}</td>
            <td>{amount:,}円</td>
            <td>{escape(memo)}</td>
            <td>
                <form action="{url_for('delete_expense', expense_id=expense_id, month=month)}"
                      method="POST"
                      onsubmit="return confirm('この支出を削除しますか？');">
                    <button type="submit">削除</button>
                </form>
            </td>
        </tr>
        """
        for expense_id, day, category, amount, memo in expenses
    )

    return f"""
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>家計簿</title>

        <style>
            .graph {{
                max-width: 500px;
                padding: 15px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }}

            .graph-item {{
                margin-bottom: 15px;
            }}

            .graph-label {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 5px;
                gap: 10px;
            }}

            .graph-track {{
                width: 100%;
                height: 18px;
                background-color: #eeeeee;
                border-radius: 4px;
                overflow: hidden;
            }}

            .graph-bar {{
                height: 100%;
                background-color: #4caf50;
                border-radius: 4px;
            }}
        </style>
    </head>

    <body>
    <h1>家計簿</h1>

    <label>表示月：</label>
    <div style="display: flex; align-items: center;
                gap: 10px; margin-bottom: 20px;">
        <a href="/?month={prev_month}">
            <button type="button">◀ 前月</button>
        </a>

        <form method="GET" action="/" style="margin: 0;">
            <input type="month" name="month" value="{month}">
            <button type="submit">表示</button>
        </form>

        <a href="/?month={next_month}">
            <button type="button">翌月 ▶</button>
        </a>
    </div>

    <form method="POST">
        <input type="date" name="date"
               value="{date.today()}" required>

        <select name="category">
            {options}
        </select>

        <input type="number" name="amount"
               min="0" required placeholder="金額">
        <br><br>

        <input type="text" name="memo"
               placeholder="備考（任意）">
        <br><br>

        <button type="submit">登録</button>
    </form>

    <h2>支出履歴</h2>
    <table border="1" cellpadding="8">
        <tr>
            <th>日付</th>
            <th>項目</th>
            <th>金額</th>
            <th>備考</th>
            <th>操作</th>
        </tr>
        {rows}
    </table>

    <h2>{year}年{month_num}月の集計</h2>
    <p>累計：{total:,}円</p>
    <p>1日平均：{average:,.0f}円</p>

    <h2>項目別集計</h2>
    <div class="graph">
        {graph_rows}
    </div>

    <h2>日別集計</h2>

    <details>
        <summary style="cursor: pointer; padding: 10px 0;">
            日別支出を表示（{days}日分）
        </summary>

        <div class="graph">
            <p>1日の支出目安：1,000円</p>
            {daily_graph_rows}
        </div>
    </details>

    </body>
    </html>
    """


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False, port=5002)
