from nicegui import ui
import sqlite3

db = sqlite3.connect("list.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute(
    "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, done BOOLEAN)"
)


def sync_data():
    global items
    cursor.execute("SELECT id, name, done FROM items")
    # Convert the database rows (0/1) back into Python dictionaries (True/False)
    items = [
        {"id": row[0], "name": row[1], "done": bool(row[2])}
        for row in cursor.fetchall()
    ]


items = []


def render_list():
    list_container.clear()
    for item in items:
        if hide_switch.value and item["done"]:
            continue
        with list_container:
            row = ui.row().classes("w-full items-center no-wrap")
            with row:
                # 1. Use the 'done' value from our data
                checkbox = ui.checkbox(value=item["done"])

                # 2. Add the styling immediately if it's already done
                label_style = "line-through text-gray-400" if item["done"] else ""
                ui.label(item["name"]).classes(label_style)

                # 3. Update data AND redraw when clicked
                def toggle(e, it=item):
                    # Update the database based on the item's unique ID
                    cursor.execute(
                        "UPDATE items SET done = ? WHERE id = ?", (e.value, it["id"])
                    )
                    db.commit()
                    sync_data()
                    render_list()

                checkbox.on_value_change(toggle)

                ui.space()

                # 4. Remove from data AND redraw when deleted
                def delete(it=item):
                    cursor.execute("DELETE FROM items WHERE id = ?", (it["id"],))
                    db.commit()
                    sync_data()
                    render_list()

                ui.button(icon="delete", on_click=delete).props("flat")


def add_to_list():
    val = new_item.value
    if val:
        # 1. Write to the database file
        cursor.execute("INSERT INTO items (name, done) VALUES (?, ?)", (val, False))
        db.commit()

        # 2. Reset the UI
        new_item.value = ""

        # 3. Refresh our memory and the screen
        sync_data()
        render_list()


# A simple layout for the list app
with ui.card().classes("w-full max-w-sm mx-auto mt-10"):
    ui.label("Shopping List App").classes("text-2xl font-bold")
    ui.label("Welcome to the mobile-first list app prototype.")
    hide_switch = ui.switch("Hide Completed", on_change=render_list)
    # Input field for new items
    new_item = ui.input(label="Add item", placeholder="e.g. Milk")
    new_item.on("keydown.enter", add_to_list)

    # Button to add item
    ui.button("Add", on_click=add_to_list)

    list_container = ui.column().classes("w-full")

# Initiate the data from file
sync_data()
render_list()

# ui.run() starts the web server
ui.run()
