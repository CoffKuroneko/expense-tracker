
from flask import Flask, request, redirect, url_for
import sqlite3
from datetime import date
from html import escape

app = Flask(__name__)
DB = "kakeibo.db"


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

        if amount > 0:
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

    average = total / days if days > 0 else 0

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
            <option>食費</option>
            <option>日用品</option>
            <option>医療費</option>
            <option>交通費</option>
            <option>娯楽費</option>
            <option>衣服費</option>
            <option>その他</option>
        </select>

        <input type="number" name="amount"
               min="1" required placeholder="金額">
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

    <h2>今月の集計</h2>
    <p>累計：{total:,}円</p>
    <p>1日平均：{average:,.0f}円</p>
    </body>
    </html>
    """


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False, port=5002)
