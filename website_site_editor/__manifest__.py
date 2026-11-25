{
    "name": "Assigned Website Editor",
    "summary": "Edit prepared page bodies, navigation and settings on assigned websites",
    "version": "20.0.1.0.0",
    "category": "Website",
    "license": "LGPL-3",
    "author": "Shiny Computers",
    "depends": ["website"],
    "data": ["security/group.xml", "security/ir.access.csv", "views/editor.xml"],
    "assets": {
        "web.assets_backend": ["website_site_editor/static/src/editor.js"],
        "web.assets_tests": ["website_site_editor/static/tests/tours.js"],
    },
}
