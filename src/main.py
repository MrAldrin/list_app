from nicegui import ui

items = []

def add_to_list():
    val = new_item.value
    if val:
        items.append(val)
        with list_container:
            row = ui.row().classes('w-full items-center')
            with row:
                checkbox=ui.checkbox()
                label=ui.label(val)
                checkbox.on_value_change(lambda e: label.classes(
                    replace='line-through text-gray-400 no-underline' if e.value else ''
                ))
                ui.space()
                ui.button(icon='delete', on_click=row.delete).props('flat')
        new_item.value=""

# A simple layout for the list app
with ui.card().classes("w-full max-w-sm mx-auto mt-10"):
    ui.label("Shopping List App").classes("text-2xl font-bold")
    ui.label("Welcome to the mobile-first list app prototype.")

    # Input field for new items
    new_item = ui.input(label="Add item", placeholder="e.g. Milk")

    # Button to add item
    ui.button("Add", on_click=add_to_list)

    list_container = ui.column().classes('w-full')

# ui.run() starts the web server
ui.run()
