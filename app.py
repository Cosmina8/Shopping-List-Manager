import os
import csv
from functools import wraps
from datetime import datetime

from firebase_config import db

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-in-production"  # pentru proiect e OK


# Helpers
# -------------------------
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def current_user_id():
    return session.get("user_id")


def now_iso():
    return datetime.utcnow().isoformat()


def doc_to_dict(doc):
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def get_user_by_username(username: str):
    docs = db.collection("users").where("username", "==", username).limit(1).stream()
    for doc in docs:
        return doc_to_dict(doc)
    return None


def get_user_by_id(user_id: str):
    doc = db.collection("users").document(user_id).get()
    return doc_to_dict(doc)


def get_list_for_user(list_id: str, user_id: str):
    doc = db.collection("lists").document(list_id).get()
    lst = doc_to_dict(doc)
    if not lst:
        return None
    if lst["user_id"] != user_id:
        return None
    return lst


def get_items_for_list(list_id: str):
    docs = db.collection("items").where("list_id", "==", list_id).stream()
    return [doc_to_dict(doc) for doc in docs]


def get_item_with_owner_check(item_id: str, user_id: str):
    item_doc = db.collection("items").document(item_id).get()
    item = doc_to_dict(item_doc)
    if not item:
        return None, None

    lst = get_list_for_user(item["list_id"], user_id)
    if not lst:
        return None, None

    return item, lst


# Routes
# -------------------------

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

        existing_user = get_user_by_username(username)
        if existing_user:
            flash("Username deja existent. Alege altul.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        user_ref = db.collection("users").document()
        user_ref.set({
            "username": username,
            "password_hash": password_hash,
            "created_at": now_iso()
        })

        flash("Cont creat cu succes. Te poți loga.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

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
    docs = db.collection("lists").where("user_id", "==", current_user_id()).stream()
    lists = [doc_to_dict(doc) for doc in docs]

    pretty_lists = []
    for l in lists:
        created = l["created_at"]

        try:
            dt = datetime.fromisoformat(created.replace("Z", ""))
            created_pretty = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            created_pretty = created

        item_count = len(get_items_for_list(l["id"]))

        pretty_lists.append({
            "id": l["id"],
            "name": l["name"],
            "created_at": created_pretty,
            "item_count": item_count
        })

    pretty_lists.sort(key=lambda x: x["created_at"], reverse=True)

    return render_template("dashboard.html", lists=pretty_lists)


@app.route("/lists/create", methods=["POST"])
@login_required
def create_list():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Numele listei este obligatoriu.")
        return redirect(url_for("dashboard"))

    list_ref = db.collection("lists").document()
    list_ref.set({
        "user_id": current_user_id(),
        "name": name,
        "created_at": now_iso()
    })

    return redirect(url_for("dashboard"))


@app.route("/lists/<list_id>/delete", methods=["POST"])
@login_required
def delete_list(list_id: str):
    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    items = get_items_for_list(list_id)
    for item in items:
        db.collection("items").document(item["id"]).delete()

    db.collection("lists").document(list_id).delete()

    flash("Lista a fost ștearsă.")
    return redirect(url_for("dashboard"))


@app.route("/lists/<list_id>/edit", methods=["GET", "POST"])
@login_required
def edit_list(list_id: str):
    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Numele listei este obligatoriu.")
            return redirect(url_for("edit_list", list_id=list_id))

        db.collection("lists").document(list_id).update({
            "name": name
        })

        flash("Lista a fost redenumită.")
        return redirect(url_for("dashboard"))

    return render_template("edit_list.html", lst=lst)


@app.route("/lists/<list_id>")
@login_required
def view_list(list_id: str):
    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    only_pending = request.args.get("only_pending") == "1"
    category = request.args.get("category", "").strip()

    items = get_items_for_list(list_id)

    if only_pending:
        items = [it for it in items if not it.get("purchased", False)]

    if category:
        items = [it for it in items if (it.get("category") or "") == category]

    items.sort(key=lambda it: (
        it.get("purchased", False),
        (it.get("category") or "").lower(),
        (it.get("name") or "").lower()
    ))

    all_items = get_items_for_list(list_id)
    categories = sorted({
        it.get("category")
        for it in all_items
        if it.get("category")
    })

    total_cost = 0.0
    category_subtotals = {}
    for it in items:
        item_qty = it["qty"] if it.get("qty") is not None else 0
        item_price = it["price"] if it.get("price") is not None else 0
        cost = item_qty * item_price
        total_cost += cost
        category_name = it.get("category") or "Altele"
        category_subtotals[category_name] = category_subtotals.get(category_name, 0) + cost

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


@app.route("/lists/<list_id>/add", methods=["POST"])
@login_required
def add_item(list_id: str):
    name = request.form.get("name", "").strip()
    qty_raw = request.form.get("qty", "").strip()
    unit = request.form.get("unit", "").strip()
    category = request.form.get("category", "").strip()
    price_raw = request.form.get("price", "").strip()

    if not name:
        flash("Numele produsului este obligatoriu.")
        return redirect(url_for("view_list", list_id=list_id))

    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        flash("Nu ai acces la lista asta.")
        return redirect(url_for("dashboard"))

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

    existing = None
    existing_items = get_items_for_list(list_id)
    for item in existing_items:
        if item["name"].lower() == name.lower():
            existing = item
            break

    if existing:
        session["pending_item"] = {
            "list_id": list_id,
            "name": name,
            "qty": qty,
            "unit": unit,
            "category": category,
            "price": price
        }
        return redirect(url_for("add_confirm", list_id=list_id))
    else:
        item_ref = db.collection("items").document()
        item_ref.set({
            "list_id": list_id,
            "name": name,
            "qty": qty,
            "unit": unit,
            "category": category,
            "price": price,
            "purchased": False,
            "created_at": now_iso()
        })
        return redirect(url_for("view_list", list_id=list_id))


@app.route("/lists/<list_id>/add_confirm", methods=["GET", "POST"])
@login_required
def add_confirm(list_id: str):
    if "pending_item" not in session:
        return redirect(url_for("view_list", list_id=list_id))

    pending = session["pending_item"]
    if pending["list_id"] != list_id:
        return redirect(url_for("view_list", list_id=list_id))

    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        return redirect(url_for("dashboard"))

    existing_items = []
    for item in get_items_for_list(list_id):
        if item["name"].lower() == pending["name"].lower():
            existing_items.append(item)

    existing_items.sort(key=lambda x: x["id"])

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            if existing_items:
                item_id = existing_items[0]["id"]
                db.collection("items").document(item_id).update({
                    "qty": pending["qty"],
                    "unit": pending["unit"],
                    "category": pending["category"],
                    "price": pending["price"]
                })

        elif action == "combine":
            if existing_items:
                existing = existing_items[0]
                if (
                    pending["qty"] is not None
                    and existing.get("qty") is not None
                    and pending["unit"] == existing.get("unit")
                    and pending["category"] == existing.get("category")
                ):
                    new_qty = float(existing["qty"]) + float(pending["qty"])
                    new_price = pending["price"] if pending["price"] is not None else existing.get("price")

                    db.collection("items").document(existing["id"]).update({
                        "qty": new_qty,
                        "price": new_price
                    })
                else:
                    item_ref = db.collection("items").document()
                    item_ref.set({
                        "list_id": list_id,
                        "name": pending["name"],
                        "qty": pending["qty"],
                        "unit": pending["unit"],
                        "category": pending["category"],
                        "price": pending["price"],
                        "purchased": False,
                        "created_at": now_iso()
                    })

        elif action == "add_new":
            item_ref = db.collection("items").document()
            item_ref.set({
                "list_id": list_id,
                "name": pending["name"],
                "qty": pending["qty"],
                "unit": pending["unit"],
                "category": pending["category"],
                "price": pending["price"],
                "purchased": False,
                "created_at": now_iso()
            })

        del session["pending_item"]
        return redirect(url_for("view_list", list_id=list_id))

    return render_template("add_confirm.html", pending=pending, existing_items=existing_items, list_id=list_id)


@app.route("/items/<item_id>/toggle", methods=["POST"])
@login_required
def toggle_item(item_id: str):
    item, lst = get_item_with_owner_check(item_id, current_user_id())
    if not item or not lst:
        flash("Item inexistent sau fără acces.")
        return redirect(url_for("dashboard"))

    new_val = not item.get("purchased", False)
    db.collection("items").document(item_id).update({
        "purchased": new_val
    })

    return redirect(url_for("view_list", list_id=item["list_id"]))


@app.route("/items/<item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: str):
    item, lst = get_item_with_owner_check(item_id, current_user_id())
    if not item or not lst:
        flash("Item inexistent sau fără acces.")
        return redirect(url_for("dashboard"))

    db.collection("items").document(item_id).delete()
    return redirect(url_for("view_list", list_id=item["list_id"]))


@app.route("/items/<item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id: str):
    item, lst = get_item_with_owner_check(item_id, current_user_id())
    if not item or not lst:
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
            return redirect(url_for("edit_item", item_id=item_id))

        qty = None
        if qty_raw:
            try:
                qty = float(qty_raw.replace(",", "."))
            except ValueError:
                flash("Cantitatea trebuie să fie număr.")
                return redirect(url_for("edit_item", item_id=item_id))

        price = None
        if price_raw:
            try:
                price = float(price_raw.replace(",", "."))
            except ValueError:
                flash("Prețul trebuie să fie număr.")
                return redirect(url_for("edit_item", item_id=item_id))

        db.collection("items").document(item_id).update({
            "name": name,
            "qty": qty,
            "unit": unit,
            "category": category,
            "price": price
        })

        flash("Produs actualizat.")
        return redirect(url_for("view_list", list_id=item["list_id"]))

    return render_template("edit_item.html", item=item, list_id=item["list_id"])


@app.route("/lists/<list_id>/export.csv")
@login_required
def export_list_csv(list_id: str):
    lst = get_list_for_user(list_id, current_user_id())
    if not lst:
        flash("Lista nu există sau nu ai acces.")
        return redirect(url_for("dashboard"))

    items = get_items_for_list(list_id)
    items.sort(key=lambda it: (
        (it.get("category") or "").lower(),
        (it.get("name") or "").lower()
    ))

    export_path = os.path.join(BASE_DIR, f"export_list_{list_id}.csv")
    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "qty", "unit", "category", "price", "purchased"])
        for it in items:
            writer.writerow([
                it.get("name"),
                it.get("qty"),
                it.get("unit"),
                it.get("category"),
                it.get("price"),
                it.get("purchased")
            ])

    return send_file(export_path, as_attachment=True, download_name=f"{lst['name']}.csv")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)