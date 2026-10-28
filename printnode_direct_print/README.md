# Personal printer routing

Each person chooses one printer for each physical paper size in **My printers**
in the user menu. **Find printers** explicitly refreshes the list of discovered
printers; opening settings does not contact PrintNode. Saved choices remain
visible when a printer is removed or disconnected. Settings administrators can
help through **Settings → Personal printers**. Other people cannot read or change
someone's defaults.

Sizes come from native `report.paperformat` records, including named formats
such as Letter. The picker deduplicates equal sizes. Orientation does not create
another preference: sorted dimensions rounded to tenths of a millimeter form
the key. Custom native dimensions use the precision Odoo supports. Raw-label
addons declare their stock as a normal paperformat XML data record. Users never
type dimensions. To print somewhere else for a while, edit My printers and
restore the choice afterward; there is no temporary switch.

The selected paperformat is a native relation, so a referenced declaration cannot
be deleted. The stored physical key changes when the person chooses a size;
editing a report's declaration to another size requires choosing that new stock
in My printers rather than silently moving the old default.

## Integration

This branch targets **Odoo 20**. Consumers on Odoo 19 need a qualified compatible
pin or reviewed backport; installing shared main on 19 is not supported.

An administrator's existing deployment configuration supplies the
`printnode.api_key` system parameter. This addon does not own provisioning,
credentials, runtime configuration, or tenant release decisions. Never include
a key in source, tests, browser actions or evidence.

Opt a native QWeb PDF report into automatic printing with
`printnode_direct=True`. Its report action adds only the routing flag and report
ID. The native report handler preserves selected IDs, validated wizard data,
company context and the native close/onClose behavior. Reports without the flag
keep Odoo's ordinary download behavior. A failed direct print raises visibly;
it does not fall back to a download or open a printer dialog.

Server buttons and genuine save hooks use the same report entry point:

```python
report._prepare_report_print(record_ids, quantity=2)
```

The public `report.printnode_print(res_ids, data)` allows one copy and accepts
neither a printer nor a user ID. Before rendering it checks internal human
actor, report opt-in/type/groups, record access, current allowed companies and
report data. Rendering drops sudo and preserves record authorization. Context
active IDs/model are rebuilt from the authorized records. Nonempty wizard data
is refused by default: a tenant report overrides `_printnode_validate_data`
to validate its own exact options and any IDs in them, then returns that data.
This hook must not trust a caller's IDs, model or embedded context.

For tenant-rendered bytes and raw ZPL, authorized private Python code uses:

```python
env["printnode.routing"]._prepare_print(
    payload,
    stock_paperformat,
    content_type="raw",
    title="Product labels",
)
```

This private API does not render or authorize business records; the tenant
caller must do that as the signed-in person. It takes no actor or printer
argument. `sudo()` keeps the initiating uid; `with_user()` changes it. Cron,
public/portal and OdooBot actors are refused. Integrations must not impersonate
a person to print. Company switching does not change a person's destination.

Every path resolves through `_resolve_printer(paperformat)` using the environment
user and physical size. That is the only routing extension point. Later
location behavior can extend it without changing callers or preference keys.

## Submission and results

Preflight requires the chosen printer and computer to be online. PDF jobs select
the closest live driver paper within `PAPER_TOLERANCE_TENTHS_MM` on each sorted
dimension, preferring exact matches, and send `fit_to_page=False`. There is no
hard-coded driver paper name or extra rotation option. Raw jobs skip PDF media
capabilities/options; their template owns geometry and embedded quantities.
PDF bytes cannot use raw transport. PDF copies use one job's `qty`; raw quantity
is always one, so embedded ZPL counts are not multiplied.

The synchronous result is `{"state": "prepared", "printer": "…"}`. It means
only that submission is prepared for after a successful database commit. It
never means sent or printed. Do not post a success toast or chatter message
from that return value. Configuration/rendering errors raise before commit in
a genuine save-and-print transaction. A save followed by a separate print RPC
has already saved: that caller must describe a print failure as a saved record
whose print failed, rather than as a failed save.

The native postcommit callback holds one in-memory batch with frozen payloads,
printers and quantities. Full rollback/retry clearing discards that attempt.
An opaque native bus row marks each prepared job. The callback reads surviving
marks in a fresh cursor, deletes them, and dispatches only those jobs. Savepoint
rollback, including import dry runs, removes its marks automatically. Marks
store no document, printer or title; unused marks use native bus cleanup.
HTTP onchange calls are refused; tenant private callers must
print only from saved-record actions or save hooks, never from onchange.
No callback retains the transaction's cursor. Submission uses bounded requests,
one total batch budget and short `expireAfter` delivery expiry. There is no
automatic retry. The `printnode-community` 0.3.0 API has `qty` but no request
timeout or expiry parameter; the small transport here uses PrintNode's
[documented REST contract](https://www.printnode.com/en/docs/api/curl#creating-print-jobs)
directly, without that client's extra discovery and job-read round trips.

Only a positive returned PrintNode job ID produces **Sent** in a native user
notification; that is provider acceptance, not proof of physical output. A
rejection or an exhausted budget reports known unsent jobs. Timeout, malformed
acceptance or unexpected delivery errors report unconfirmed jobs and tell the
person to check the printer before intentionally printing again. One summary
preserves mixed results. Submission and notification exceptions are logged and
contained so later native callbacks still run. Notification work uses a fresh
cursor with a statement timeout.

A process dying after commit can lose its in-memory batch or confirmation. An
absent Sent confirmation is unconfirmed, requiring an intentional check and
reprint. There is no unattended exactly-once guarantee, durable queue, history,
stored payload, cron dispatcher or recovery service.

## Adoption checks

Tenant adoption must replace earlier success-looking chatter/toasts, preserve
label content/quantities and trigger conditions, and test the real workflow on
its compatible Odoo version. Verify loaded stock, orientation, client PDF
engine/driver settings, barcode scanning and physical results separately.
Mocks and PDFs do not establish hardware or Client acceptance.
