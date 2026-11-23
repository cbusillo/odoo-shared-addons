{
    "name": "D3 Hierarchy View",
    "summary": "An interactive, opt-in chart for Odoo hierarchy views",
    "version": "20.0.1.0.0",
    "category": "Web",
    "license": "LGPL-3",
    "author": "Shiny Computers",
    "website": "https://github.com/cbusillo/odoo-shared-addons",
    "depends": ["web_hierarchy"],
    "assets": {
        "web.assets_backend_lazy": ["web_hierarchy_d3/static/src/**/*"],
    },
    "installable": True,
}
