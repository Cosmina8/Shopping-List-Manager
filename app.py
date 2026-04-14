import os
import csv
import sqlite3
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-in-production"  # pentru proiect e OK

# DB helpers
# -------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        qty REAL,
        unit TEXT,
        category TEXT,
        price REAL,
        purchased INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(list_id) REFERENCES lists(id)
    )
    """)

    cur.execute("PRAGMA table_info(items)")
    columns = [row[1] for row in cur.fetchall()]
    if "price" not in columns:
        cur.execute("ALTER TABLE items ADD COLUMN price REAL")

    conn.commit()
    conn.close()


# rulează init la start
init_db()

# Auth helpers

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def current_user_id():
    return session.get("user_id")



# Routes

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Completează username și parolă.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, datetime.utcnow().isoformat())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Username deja existent. Alege altul.")
            return redirect(url_for("register"))

        conn.close()
        flash("Cont creat cu succes. Te poți loga.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Username sau parolă greșite.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT lists.id, lists.name, lists.created_at, COUNT(items.id) AS item_count
        FROM lists
        LEFT JOIN items ON items.list_id = lists.id
        WHERE lists.user_id = ?
        GROUP BY lists.id
        ORDER BY lists.id DESC
        """,
        (current_user_id(),)
    )

    lists = cur.fetchall()
    conn.close()

    pretty_lists = []
    for l in lists:
        created = l["created_at"]
        try:
            dt = datetime.fromisoformat(created.replace("Z", ""))
            created_pretty = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            created_pretty = created

        pretty_lists.append({
            "id": l["id"],
            "name": l["name"],
            "created_at": created_pretty,
            "item_count": l["item_count"]
        })

    return render_template("dashboard.html", lists=pretty_lists)


@app.route("/lists/create", methods=["POST"])

@login_required
def create_list():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Numele listei este obligatoriu.")
        return redirect(url_for("dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO lists(user_id, name, created_at) VALUES (?, ?, ?)",
        (current_user_id(), name, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/lists/<int:list_id>/delete", methods=["POST"])
@login_required
def delete_list(list_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM lists WHERE id = ? AND user_id = ?",
        (list_id, current_user_id())
    )
    lst = cur.fetchone()

    if not lst:
        conn.close()
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    cur.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
    cur.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    conn.commit()
    conn.close()

    flash("Lista a fost ștearsă.")
    return redirect(url_for("dashboard"))


@app.route("/lists/<int:list_id>/edit", methods=["GET", "POST"])
@login_required
def edit_list(list_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM lists WHERE id = ? AND user_id = ?", (list_id, current_user_id()))
    lst = cur.fetchone()
    if not lst:
        conn.close()
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Numele listei este obligatoriu.")
            conn.close()
            return redirect(url_for("edit_list", list_id=list_id))

        cur.execute("UPDATE lists SET name = ? WHERE id = ?", (name, list_id))
        conn.commit()
        conn.close()

        flash("Lista a fost redenumită.")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit_list.html", lst=lst)


@app.route("/lists/<int:list_id>")
@login_required
def view_list(list_id: int):
    conn = get_db()
    cur = conn.cursor()

    # verificare ownership
    cur.execute("SELECT * FROM lists WHERE id = ? AND user_id = ?", (list_id, current_user_id()))
    lst = cur.fetchone()
    if not lst:
        conn.close()
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    only_pending = request.args.get("only_pending") == "1"
    category = request.args.get("category", "").strip()

    query = "SELECT * FROM items WHERE list_id = ?"
    params = [list_id]

    if only_pending:
        query += " AND purchased = 0"
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY purchased ASC, category ASC, name ASC"

    cur.execute(query, tuple(params))
    items = cur.fetchall()

    cur.execute("SELECT DISTINCT category FROM items WHERE list_id = ? AND category IS NOT NULL AND category != '' ORDER BY category", (list_id,))
    categories = [row["category"] for row in cur.fetchall()]

    total_cost = 0.0
    category_subtotals = {}
    for it in items:
        item_qty = it["qty"] if it["qty"] is not None else 0
        item_price = it["price"] if it["price"] is not None else 0
        cost = item_qty * item_price
        total_cost += cost
        category_name = it["category"] or "Altele"
        category_subtotals[category_name] = category_subtotals.get(category_name, 0) + cost

    conn.close()
    return render_template(
        "list.html",
        lst=lst,
        items=items,
        categories=categories,
        only_pending=only_pending,
        selected_category=category,
        total_cost=total_cost,
        category_subtotals=category_subtotals,
    )


@app.route("/lists/<int:list_id>/add", methods=["POST"])
@login_required
def add_item(list_id: int):
    name = request.form.get("name", "").strip()
    qty_raw = request.form.get("qty", "").strip()
    unit = request.form.get("unit", "").strip()
    category = request.form.get("category", "").strip()
    price_raw = request.form.get("price", "").strip()

    if not name:
        flash("Numele produsului este obligatoriu.")
        return redirect(url_for("view_list", list_id=list_id))

    qty = None
    if qty_raw:
        try:
            qty = float(qty_raw.replace(",", "."))
        except ValueError:
            flash("Cantitatea trebuie să fie număr (ex: 2 sau 1.5).")
            return redirect(url_for("view_list", list_id=list_id))

    price = None
    if price_raw:
        try:
            price = float(price_raw.replace(",", "."))
        except ValueError:
            flash("Prețul trebuie să fie număr (ex: 4.50).")
            return redirect(url_for("view_list", list_id=list_id))

    conn = get_db()
    cur = conn.cursor()

    # ownership list
    cur.execute("SELECT id FROM lists WHERE id = ? AND user_id = ?", (list_id, current_user_id()))
    if not cur.fetchone():
        conn.close()
        flash("Nu ai acces la lista asta.")
        return redirect(url_for("dashboard"))

    # check if item with same name exists
    cur.execute("SELECT id FROM items WHERE list_id = ? AND LOWER(name) = LOWER(?) LIMIT 1", (list_id, name))
    existing = cur.fetchone()
    conn.close()

    if existing:
        # store pending item in session
        session['pending_item'] = {
            'list_id': list_id,
            'name': name,
            'qty': qty,
            'unit': unit,
            'category': category,
            'price': price
        }
        return redirect(url_for('add_confirm', list_id=list_id))
    else:
        # add normally
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO items(list_id, name, qty, unit, category, price, purchased, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (list_id, name, qty, unit, category, price, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return redirect(url_for("view_list", list_id=list_id))


@app.route("/lists/<int:list_id>/add_confirm", methods=["GET", "POST"])
@login_required
def add_confirm(list_id: int):
    if 'pending_item' not in session:
        return redirect(url_for('view_list', list_id=list_id))

    pending = session['pending_item']
    if pending['list_id'] != list_id:
        return redirect(url_for('view_list', list_id=list_id))

    conn = get_db()
    cur = conn.cursor()

    # check ownership
    cur.execute("SELECT id FROM lists WHERE id = ? AND user_id = ?", (list_id, current_user_id()))
    if not cur.fetchone():
        conn.close()
        return redirect(url_for('dashboard'))

    # get existing items with same name
    cur.execute("SELECT * FROM items WHERE list_id = ? AND LOWER(name) = LOWER(?) ORDER BY id", (list_id, pending['name']))
    existing_items = cur.fetchall()
    conn.close()

    if request.method == "POST":
        action = request.form.get('action')
        if action == 'update':
            # update the first existing item
            if existing_items:
                item_id = existing_items[0]['id']
                conn = get_db()
                cur = conn.cursor()
                cur.execute("UPDATE items SET qty = ?, unit = ?, category = ?, price = ? WHERE id = ?", (pending['qty'], pending['unit'], pending['category'], pending['price'], item_id))
                conn.commit()
                conn.close()
        elif action == 'combine':
            # combine with the first existing if possible
            if existing_items:
                existing = existing_items[0]
                if (pending['qty'] is not None and existing['qty'] is not None and
                    pending['unit'] == existing['unit'] and pending['category'] == existing['category']):
                    new_qty = float(existing['qty']) + float(pending['qty'])
                    new_price = pending['price'] if pending['price'] is not None else existing['price']
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("UPDATE items SET qty = ?, price = ? WHERE id = ?", (new_qty, new_price, existing['id']))
                    conn.commit()
                    conn.close()
                else:
                    # can't combine, add new
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO items(list_id, name, qty, unit, category, price, purchased, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)", (list_id, pending['name'], pending['qty'], pending['unit'], pending['category'], pending['price'], datetime.utcnow().isoformat()))
                    conn.commit()
                    conn.close()
        elif action == 'add_new':
            # add new anyway
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO items(list_id, name, qty, unit, category, price, purchased, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)", (list_id, pending['name'], pending['qty'], pending['unit'], pending['category'], pending['price'], datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()

        del session['pending_item']
        return redirect(url_for('view_list', list_id=list_id))

    return render_template('add_confirm.html', pending=pending, existing_items=existing_items, list_id=list_id)


@app.route("/items/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_item(item_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT items.id, items.purchased, items.list_id
        FROM items
        JOIN lists ON lists.id = items.list_id
        WHERE items.id = ? AND lists.user_id = ?
    """, (item_id, current_user_id()))
    row = cur.fetchone()

    if not row:
        conn.close()
        flash("Item inexistent sau fără acces.")
        return redirect(url_for("dashboard"))

    new_val = 0 if row["purchased"] == 1 else 1
    cur.execute("UPDATE items SET purchased = ? WHERE id = ?", (new_val, item_id))
    conn.commit()

    list_id = row["list_id"]
    conn.close()
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT items.list_id
        FROM items
        JOIN lists ON lists.id = items.list_id
        WHERE items.id = ? AND lists.user_id = ?
    """, (item_id, current_user_id()))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Item inexistent sau fără acces.")
        return redirect(url_for("dashboard"))

    list_id = row["list_id"]
    cur.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT items.*, lists.user_id
        FROM items
        JOIN lists ON lists.id = items.list_id
        WHERE items.id = ?
    """, (item_id,))
    item = cur.fetchone()

    if not item or item["user_id"] != current_user_id():
        conn.close()
        flash("Produs inexistent sau fără acces.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        qty_raw = request.form.get("qty", "").strip()
        unit = request.form.get("unit", "").strip()
        category = request.form.get("category", "").strip()
        price_raw = request.form.get("price", "").strip()

        if not name:
            flash("Numele produsului este obligatoriu.")
            conn.close()
            return redirect(url_for("edit_item", item_id=item_id))

        qty = None
        if qty_raw:
            try:
                qty = float(qty_raw.replace(",", "."))
            except ValueError:
                flash("Cantitatea trebuie să fie număr.")
                conn.close()
                return redirect(url_for("edit_item", item_id=item_id))

        price = None
        if price_raw:
            try:
                price = float(price_raw.replace(",", "."))
            except ValueError:
                flash("Prețul trebuie să fie număr.")
                conn.close()
                return redirect(url_for("edit_item", item_id=item_id))

        cur.execute("""
            UPDATE items
            SET name = ?, qty = ?, unit = ?, category = ?, price = ?
            WHERE id = ?
        """, (name, qty, unit, category, price, item_id))

        conn.commit()
        list_id = item["list_id"]
        conn.close()

        flash("Produs actualizat.")
        return redirect(url_for("view_list", list_id=list_id))

    list_id = item["list_id"]
    conn.close()
    return render_template("edit_item.html", item=item, list_id=list_id)


@app.route("/lists/<int:list_id>/export.csv")
@login_required
def export_list_csv(list_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM lists WHERE id = ? AND user_id = ?", (list_id, current_user_id()))
    lst = cur.fetchone()
    if not lst:
        conn.close()
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT * FROM items WHERE list_id = ? ORDER BY category ASC, name ASC", (list_id,))
    items = cur.fetchall()
    conn.close()

    export_path = os.path.join(BASE_DIR, f"export_list_{list_id}.csv")
    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "qty", "unit", "category", "price", "purchased"])
        for it in items:
            writer.writerow([it["name"], it["qty"], it["unit"], it["category"], it["price"], it["purchased"]])

    return send_file(export_path, as_attachment=True, download_name=f"{lst['name']}.csv")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)