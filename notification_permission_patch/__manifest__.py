{
    "name": "Notification Permission Patch",
    "version": "19.0.0.1",
    "category": "Technical",
    "summary": "Keep browser notification subscriptions in sync with permission changes",
    "description": "Browser notification permission observer for the Odoo web client.",
    "author": "Shiny Computers",
    "maintainers": ["cbusillo"],
    "depends": [
        "mail",
        "web",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "notification_permission_patch/static/src/js/notification_permission_patch.js",
        ],
        "web.assets_unit_tests": [
            "notification_permission_patch/static/tests/*.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}

