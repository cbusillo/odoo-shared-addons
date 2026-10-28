{
    "name": "Personal Printer Routing",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["web", "bus"],
    "external_dependencies": {"python": ["requests"]},
    "data": ["security/ir.access.csv", "views/printer_views.xml"],
    "assets": {
        "web.assets_backend": ["printnode_direct_print/static/src/printing.js"],
        "web.assets_unit_tests": ["printnode_direct_print/static/tests/printing.test.js"],
    },
    "installable": True,
}
