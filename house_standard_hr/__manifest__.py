{
    "name": "House Standard for Employees",
    "version": "20.0.1.0.0",
    "summary": "Apply the house style to the native employee hierarchy",
    "category": "Hidden",
    "author": "Chris Busillo (Shiny Computers)",
    "maintainers": ["cbusillo"],
    "license": "LGPL-3",
    "depends": ["house_standard", "hr"],
    "auto_install": True,
    "data": ["views/hr_employee_hierarchy_views.xml"],
    "assets": {
        "web.assets_backend_lazy": ["house_standard_hr/static/src/scss/employee_hierarchy.scss"],
    },
}
