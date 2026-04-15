from nicegui import ui

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
                label = ui.label(item["name"]).classes(label_style)

                # 3. Update data AND redraw when clicked
                def toggle(e, it=item):
                    it["done"] = e.value
                    render_list()

                checkbox.on_value_change(toggle)

                ui.space()

                # 4. Remove from data AND redraw when deleted
                def delete(it=item):
                    items.remove(it)
                    render_list()

                ui.button(icon="delete", on_click=delete).props("flat")


def add_to_list():
    val = new_item.value
    if val:
        items.append({"name": val, "done": False})
        new_item.value = ""
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

# ui.run() starts the web server
ui.run()
