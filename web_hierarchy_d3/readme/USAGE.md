Install `web_hierarchy_d3` and set `js_class="hierarchy_d3"` on a
`<hierarchy>` view. Keep the existing action, search view and
`hierarchy-box` template. The chart uses the configured self-parent field,
optional binary `avatar_field`, and the declared visible Char field `name`
or the model’s display name. The existing
hierarchy template remains available to the native hierarchy renderer.

To show a subtitle or colored stripe, declare the corresponding visible field
directly under `<hierarchy>` and set the chart option. This example uses
fields available on both Odoo employee models.

```xml
<hierarchy js_class="hierarchy_d3" child_field="child_ids" avatar_field="image_128">
    <field name="name"/>
    <field name="job_title" options="{'hierarchy_d3': 'subtitle'}"/>
    <field name="department_color" options="{'hierarchy_d3': 'color'}"/>
    <templates>
        <t t-name="hierarchy-box"><field name="name"/></t>
    </templates>
</hierarchy>
```

The subtitle uses a Char field and the stripe uses an Integer field. The chart
lays out the loaded records by their parent links. A record-focused action
highlights its record when it appears in the chart. The layout and expand
controls are read-only. Use the native form to edit a record.

Odoo’s search applies the action domain, current filters and record rules when
loading the chart. The chart shows up to 200 matches in the view’s configured
order, with record ID as the tie-breaker. With no configured order, it uses
record ID. If more matches exist, it asks you to narrow Odoo’s search.
A record with a parent outside the result appears as a root. Find in chart
searches within the loaded records and reveals a selected result.

PNG contains the currently expanded branches, regardless of pan and zoom.
If the expanded chart is too large for a readable PNG, collapse branches or
narrow the Odoo search and export again.
