# House Standard

Installing this addon gives a product the house backend standard that the
shared Odoo 20 base image provides: MuK's LGPL-3 Community backend theme,
`muk_web_theme`, with its `muk_web_*` dependencies, plus these defaults.

- Contacts open as cards first.
- The message panel sits under the form. At install every internal user is
  set to Bottom, and new users start there; each person can switch to Side in
  My Preferences (MuK's Chatter Position).
- Users land on an app grid (the `Home` client action, path `/odoo/home`). At
  install it becomes the Home Action of every internal user who has none, and
  new users start with it; an admin can change a user's Home Action.
- A lighter look: a white top bar and app sidebar and Odoo's plum accent. The
  accent and sidebar colors are MuK color settings written once at install, so
  an admin can change them under Settings; the white top bar is this addon's
  stylesheet.
- The search box shows Odoo's own dropdown arrow, which Odoo 20 otherwise shows
  only on touch screens.

The theme modules ship in the base image (cbusillo/odoo-docker), not here. A
product adopts the standard by pinning an image pair that carries them and
installing `house_standard`. Add a default here when every product should get
it; keep product-specific choices in the product.
