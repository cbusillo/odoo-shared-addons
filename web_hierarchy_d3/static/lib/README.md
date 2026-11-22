# Vendored org chart

This bundle wraps the unmodified MIT-licensed
[d3-org-chart source at cb1f376656bc83360a4fea6872597fd427fcd775](https://github.com/bumbeishvili/org-chart/tree/cb1f376656bc83360a4fea6872597fd427fcd775)
with the exact D3 dependencies in the npm lockfile. It exports `OrgChart` and
D3’s `zoomIdentity` through a private global loaded on first chart use.
`NOTICE` carries the bundled packages’ license texts.

To reproduce the browser asset, copy this directory’s two npm metadata files into
a scratch directory and run the following there.

```sh
npm ci --ignore-scripts
curl -fsSLo d3-org-chart.js https://raw.githubusercontent.com/bumbeishvili/org-chart/cb1f376656bc83360a4fea6872597fd427fcd775/src/d3-org-chart.js
printf '%s\n' 'export { OrgChart } from "./d3-org-chart.js";' 'export { zoomIdentity } from "d3-zoom";' > entry.js
npm exec --yes --package esbuild@0.25.12 -- esbuild entry.js --bundle --minify --format=iife --global-name=OdooHierarchyD3 --legal-comments=none --supported:template-literal=false '--banner:js=/*! d3-org-chart and D3 dependencies. See NOTICE for licenses. */' --outfile=org-chart.min.js
```

The layout engine calls D3 `stratify()`. The addon supplies an invisible
layout root when drawing the forest. It is never exposed as a card or record.
