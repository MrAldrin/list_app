import os
import sqlite3

from nicegui import ui, app

db_path = os.environ.get("DB_PATH", "list.db")
db = sqlite3.connect(db_path, check_same_thread=False)
cursor = db.cursor()

cursor.execute(
    "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, done BOOLEAN)"
)

history_names = []
items = []
refresh_callbacks = set()


def sync_data():
    # Reload shared list state from SQLite into in-memory structures for fast UI rendering.
    global items, history_names
    cursor.execute(
        "SELECT id, name, done FROM items ORDER BY done ASC, name COLLATE NOCASE ASC"
    )
    # Convert the database rows (0/1) back into Python dictionaries (True/False)
    rows = cursor.fetchall()
    items = [{"id": r[0], "name": r[1], "done": bool(r[2])} for r in rows]
    history_names = sorted(list(set(item["name"] for item in items)))


def broadcast_updates():
    # Push a fresh list view to every connected browser client.
    sync_data()
    # This iterates through every open browser tab
    for client in app.clients():
        with client:
            item_list.refresh()


@ui.refreshable
def item_list(switch):
    # Render the list rows and wire per-row actions (toggle done, delete).
    for item in items:
        if switch.value and item["done"]:
            continue
        row = ui.row().classes("w-full items-center no-wrap")
        with row:
            # 1. Use the 'done' value from our data
            checkbox = ui.checkbox(value=item["done"])

            # 2. Add the styling immediately if it's already done
            label_style = "line-through text-gray-400" if item["done"] else ""
            ui.label(item["name"]).classes(label_style)

            # 3. Update data AND redraw when clicked
            def toggle(e, it=item):
                # Mark one item done/undone in DB, then broadcast the updated list.
                # Update the database based on the item's unique ID
                cursor.execute(
                    "UPDATE items SET done = ? WHERE id = ?", (e.value, it["id"])
                )
                db.commit()
                broadcast_updates()

            checkbox.on_value_change(toggle)
            ui.space()

            # 4. Remove from data AND redraw when deleted
            def delete(it=item):
                # Delete one item from DB, then broadcast the updated list.
                cursor.execute("DELETE FROM items WHERE id = ?", (it["id"],))
                db.commit()
                ui.notify(f"Deleted {it['name']}", color="negative")
                broadcast_updates()

            ui.button(icon="delete", on_click=delete).props("flat")


def add_to_list(target_input, val=None):
    # Add a new item (or restore an old one), then clear this user's input and refresh all clients.
    item_name = val if val else target_input.value
    if not item_name:
        return

    # Check the database for this name
    cursor.execute(
        "SELECT id, done FROM items WHERE name = ? COLLATE NOCASE", (item_name,)
    )
    existing = cursor.fetchone()

    if existing:
        item_id, is_done = existing
        if is_done:
            # It was checked off -> Restore it
            cursor.execute("UPDATE items SET done = 0 WHERE id = ?", (item_id,))
            db.commit()
            ui.notify(f"Restored {item_name}!", color="info")
        else:
            # It is already on the list -> Warn user
            ui.notify(f"'{item_name}' is already on the list", color="warning")
    else:
        # It's brand new -> Add it
        cursor.execute(
            "INSERT INTO items (name, done) VALUES (?, ?)", (item_name, False)
        )
        db.commit()
        ui.notify(f"Added {item_name}", color="positive")

    # Reset UI and refresh data
    target_input.value = None
    target_input.update()
    broadcast_updates()


@ui.page("/")
def index():
    # Build the main page: input controls plus the shared list.
    with ui.card().classes("w-full max-w-sm mx-auto mt-10"):
        ui.label("Shopping List App").classes("text-2xl font-bold")
        ui.label("Welcome to the mobile-first list app prototype.")
        hide_switch = ui.switch("Hide Completed", on_change=item_list.refresh)
        # Input field for new items
        search_input = ui.select(
            options=[],
            with_input=True,
            new_value_mode="add",
            label="Add or Search items",
        ).classes("w-full")

        search_input.props("fill-input=false")

        def on_filter(e):
            # Limit dropdown suggestions to at most 3 matches and only after typing starts.
            typed = ((e.args[0] if e.args else "") or "").strip().lower()

            if len(typed) < 1:
                # show nothing until at least 1 character typed
                search_input.options = []
            else:
                # max 3 matches
                matches = [name for name in history_names if typed in name.lower()]
                search_input.options = matches[:3]

            search_input.update()

        search_input.on("filter", on_filter)

        search_input.on_value_change(
            lambda e: add_to_list(target_input=search_input, val=e.value)
        )

        # Button to add item
        ui.button("Add", on_click=lambda: add_to_list(search_input))

        item_list(switch=hide_switch)


# Initiate the data from file
sync_data()


port = int(os.environ.get("PORT", 8080))

# ui.run() starts the web server
ui.run(host="0.0.0.0", port=port, reload=True)
