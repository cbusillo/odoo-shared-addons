# Consent-first GA4 for Odoo websites

Install `website_consent_analytics` as a dependency of the consuming addon.
Set `consent_first_ga4 = True` on the selected `website` record. The field
defaults to false. On an opted-in website the addon suppresses Odoo's eager
Google tag even when collection is disabled. Other websites continue to use
their native layout. Remove any previous Google loader and its layout override
in the adopting change so the shared loader has sole ownership.

The existing settings owner supplies the native website domain, GA4 measurement
ID, cookie bar and third-party blocking. Only `PLATFORM_INSTANCE=prod` or
`production` with all four settings can collect. All other lanes receive a
local preview marker without the ID or origin, including restored copies.
Devkit continues to clear copied native settings at startup.

Start the integration from the consumer's frontend module with a map of
allowlisted request paths to fixed canonical paths and public titles. An alias
may map to the same canonical path. Unlisted pages never initialize the tag.

```js
import { startConsentAnalytics } from "@website_consent_analytics/analytics";

startConsentAnalytics({
    pages: new Map([["/services", { path: "/services", title: "Services" }]]),
    eventForLink(link) {
        if (link.matches("a.service-enquiry")) {
            return { name: "enquiry_action", action: "enquire" };
        }
    },
});
```

Use fixed event names and action labels. Keep URLs, visitor text and form
contents out of every mapped value. The loader sends a single consented
`page_view`, fixes the referrer to the configured website root and keeps
advertising consent and Google signals disabled. Odoo's saved optional-cookie
choice and native cookie bar control subsequent collection. Choosing essentials
sets the GA opt-out flag immediately. Reaccepting on the same page resumes
events with the same tag. Previously set GA cookies may remain until expiry.

For a local preview check, pass an optional `preview(state)` callback when
the consumer's check URL is requested. It receives `{ accepted }` for the
initial choice and changes, and `{ accepted, name, action }` for counted
events. The consumer renders these notifications and its policy copy.
Recognized links are simulated while checking. Preview creates no tag or
Google command queue. Production ignores the callback. Before activation, the consumer verifies that enhanced measurement,
connected tags and user-provided data collection cannot add unreviewed events
or private values. The page and event maps control only commands from this
addon. The consumer owns provider settings and release qualification.
