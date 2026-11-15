# House Standard

Installing this addon gives a product the house backend standard that the
shared Odoo 20 base image provides. Today that is MuK's LGPL-3 Community
backend theme, `muk_web_theme`, with its `muk_web_*` dependencies.

The theme modules ship in the base image (cbusillo/odoo-docker), not here. A
product adopts the standard by pinning an image pair that carries them and
installing `house_standard`. Add a dependency here when every product should
get it; keep product-specific choices in the product.
