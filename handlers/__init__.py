from .start import start_handler, contact_handler, key_input_handler
from .callbacks import callback_handler
from .menu import menu_handlers
from .notify_time import custom_notify_time_handler
from .admin_push import admin_push_handler

def setup_handlers(app):
    app.add_handler(start_handler)
    app.add_handler(contact_handler)
    app.add_handler(callback_handler)
    for h in menu_handlers:
        app.add_handler(h)
    app.add_handler(admin_push_handler)
    app.add_handler(custom_notify_time_handler)
    app.add_handler(key_input_handler)
