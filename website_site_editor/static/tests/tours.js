import {
    clickOnEditAndWaitEditMode,
    clickOnSave,
    insertSnippet,
    registerWebsitePreviewTour,
} from "@website/js/tours/tour_utils";

registerWebsitePreviewTour("site_editor_text", {}, () => [
    ...clickOnEditAndWaitEditMode(),
    {trigger: ":iframe .o_site_editor_body p", run: "editor Golden fern"},
    ...clickOnSave(),
    {trigger: ":iframe .o_site_editor_body p:contains(Golden fern)"},
]);

registerWebsitePreviewTour("site_editor_block", {}, () => [
    ...clickOnEditAndWaitEditMode(),
    {trigger: "button[data-name=blocks]", run: "click"},
    ...insertSnippet({id: "s_text_block", name: "Text", groupName: "Text"}),
    ...clickOnSave(),
    {trigger: ":iframe .o_site_editor_body section.s_text_block"},
]);

registerWebsitePreviewTour("site_editor_unassigned", {}, () => [
    {trigger: ":iframe #garden-heading"},
    {trigger: ":iframe html[data-site-editor-access=unassigned] #garden-heading"},
    {trigger: ".o_menu_systray:not(:has(.o_edit_website_container button))"},
]);

registerWebsitePreviewTour("site_editor_arrange", {}, () => [
    ...clickOnEditAndWaitEditMode(),
    {trigger: ":iframe .o_site_editor_body .garden-two", run: "click"},
    {trigger: ".o_overlay_options button[title='Move up']", run: "click"},
    {trigger: ":iframe .o_site_editor_body .garden-two + .garden-one"},
    {trigger: ":iframe .o_site_editor_body .garden-three", run: "click"},
    {trigger: ".o_overlay_options .oe_snippet_remove", run: "click"},
    ...clickOnSave(),
    {trigger: ":iframe .o_site_editor_body:not(:has(.garden-three)) .garden-two + .garden-one"},
]);

registerWebsitePreviewTour("site_editor_navigation", {}, () => [
    {trigger: ":iframe .o_site_editor_body"},
    {trigger: '.o_navbar button[data-menu-xmlid="website.menu_site"]', run: "click"},
    {trigger: '.o_popover a[data-menu-xmlid="website.menu_edit_menu"]', run: "click"},
    {trigger: ".modal .oe_menu_editor .js_edit_menu", run: "click"},
    {trigger: ".modal:has(#url_input) input:first", run: "edit Garden paths"},
    {trigger: ".modal:has(#url_input) button.btn-primary:contains(Continue)", run: "click"},
    {trigger: ".modal:has(.oe_menu_editor) button.btn-primary:contains(Save)", run: "click"},
    {trigger: ":iframe .top_menu a:contains(Garden paths)"},
]);

registerWebsitePreviewTour("site_editor_page_url", {}, () => [
    {trigger: ":iframe .o_site_editor_body"},
    {trigger: '.o_navbar button[data-menu-xmlid="website.menu_site"]', run: "click"},
    {trigger: '.o_popover a[data-menu-xmlid="website_site_editor.menu_pages"]', run: "click"},
    {trigger: ".o_data_row .o_field_cell[name=url]:contains(/garden-notebook)", run: "click"},
    {trigger: ".o_selected_row .o_field_widget[name=url] input", run: "edit /fern-notebook"},
    {trigger: ".o_list_button_save", run: "click"},
    {trigger: ".o_data_row:not(.o_selected_row) .o_field_cell[name=url]:contains(/fern-notebook)"},
]);

registerWebsitePreviewTour("site_editor_settings", {}, () => [
    {trigger: ":iframe .o_site_editor_body"},
    {trigger: '.o_navbar button[data-menu-xmlid="website.menu_site"]', run: "click"},
    {trigger: '.o_popover a[data-menu-xmlid="website_site_editor.menu_settings"]', run: "click"},
    {trigger: ".o_data_row .o_field_cell[name=homepage_url]", run: "click"},
    {trigger: ".o_selected_row .o_field_widget[name=homepage_url] input", run: "edit /garden-notebook"},
    {trigger: ".o_list_button_save", run: "click"},
    {trigger: ".o_data_row:not(.o_selected_row) .o_field_cell[name=homepage_url]:contains(/garden-notebook)"},
]);
