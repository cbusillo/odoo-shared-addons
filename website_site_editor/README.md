# Assigned Website Editor

An administrator can let an internal user maintain selected websites. The user edits a prepared body with the standard Website builder, manages ordinary navigation links with Menu Editor, and uses Site → Assigned pages for URLs and indexing or Site → Assigned websites for the site name and homepage.

## Prepare a page

Use a website-specific page. In its administrator-owned QWeb template, put this call inside the page's wrap where the editable region belongs.

```xml
<t t-call="website_site_editor.page_body"/>
```

Select **Enable assigned body editing** and seed **Editable page body** in the website page form with the region's existing content. Keep dynamic forms, header, footer, and template expressions in the surrounding template. Check the rendered page before assigning an editor. Each page stores its own translated, sanitized HTML. This preparation is explicit for each existing page. The addon does not convert an existing layout during installation.

## Assign the editor

Install **Assigned Website Editor**. On the internal user's access-rights form choose **Assigned Website Editor** as the Website privilege. Use an account without Settings administration, Editor and Designer, or other independent content administration rights. On each permitted website form, add the user to **Assigned website editors**. Removing the user from the last site removes their assigned-site editing access. An ordinary Settings administrator retains native website administration.

The site editor can change text and standard blocks inside the prepared region, URLs and indexing of site-specific pages, ordinary navigation entries, the website's name and homepage. Template code, custom code, shared pages, themes and global settings remain administrator-owned. Website visitors use Odoo's normal publication and visibility rules.

On other websites, assigned editors can read ordinary navigation and links to published pages visible to their account. Draft and password-protected page links stay within the assigned site's editing workflow. Menu group restrictions still apply.
