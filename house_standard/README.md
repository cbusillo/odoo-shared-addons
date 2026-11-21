# House Standard

Installing this addon gives a product the house backend standard that the
shared Odoo 20 base image provides: MuK's LGPL-3 Community backend theme,
`muk_web_theme`, with its `muk_web_*` dependencies; OCA's AGPL-3
`document_page` wiki pages, with `document_knowledge`; plus these defaults.

- Contacts open as cards first.
- Customer signup defaults to invitation-only at the database level and on
  installed websites. The first upgrade that applies each default logs any
  change from public signup. The Odoo.com Accounts button is hidden by default.
  If the first upgrade finds users linked to that provider, it preserves the
  provider setting and logs the number of linked users. Authentik, other
  configured providers and passkeys keep their existing behavior. Products
  can opt in to public signup or the Odoo.com button, and later upgrades
  preserve those choices.
- The message panel sits under the form. At install every internal user is
  set to Bottom, and new users start there; each person can switch to Side in
  My Preferences (MuK's Chatter Position).
- Users land on an app grid (the `Home` client action, path `/odoo/house-home`). At
  install it becomes the Home Action of every internal user who has none, and
  new users start with it; an admin can change a user's Home Action.
  The desktop apps button and the mobile menu's All Apps button open this same
  grid. The grid and sidebar show the apps available to the signed-in user.
- A lighter look from this addon's stylesheet: a white top bar and app
  sidebar and Odoo's plum accent. They override MuK's colors, so MuK's color
  settings do not change them. Writing them as MuK settings would store them
  as asset attachments, which Odoo's own JavaScript test suite cannot read.
- The search box shows Odoo's own dropdown arrow, which Odoo 20 otherwise shows
  only on touch screens.

The theme and wiki modules ship in the base image (cbusillo/odoo-docker), not
here. A product adopts the standard by pinning an image pair that carries them and
installing `house_standard`. Add a default here when every product should get
it; keep product-specific choices in the product.
