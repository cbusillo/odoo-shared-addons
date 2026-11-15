{
    "name": "House Standard",
    "version": "20.0.1.1.0",
    "summary": "Install the house backend look and defaults every product shares",
    "category": "Hidden",
    "author": "Chris Busillo (Shiny Computers)",
    "maintainers": ["cbusillo"],
    "license": "LGPL-3",
    "depends": ["contacts", "muk_web_theme"],
    "data": [
        "data/app_grid_action.xml",
        "data/contacts_action.xml",
        "data/house_defaults.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            (
                "after",
                "web/static/src/scss/primary_variables.scss",
                "house_standard/static/src/scss/primary_variables.scss",
            ),
        ],
        "web.assets_backend": [
            "house_standard/static/src/app_grid/*",
            "house_standard/static/src/search/*",
            "house_standard/static/src/scss/house_standard.scss",
        ],
    },
    "post_init_hook": "apply_house_defaults_to_existing_users",
    "installable": True,
    "application": False,
}
