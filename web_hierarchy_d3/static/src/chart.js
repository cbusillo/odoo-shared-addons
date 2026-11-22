import { _t } from "@web/core/l10n/translation";
import { imageUrl } from "@web/core/utils/urls";

import { LAYOUT_ROOT } from "./forest";

const SVG_NS = "http://www.w3.org/2000/svg";
const CARD_WIDTH = 196;
const CARD_HEIGHT = 68;
const MIN_ZOOM = 0.005;
const MAX_ZOOM = 2.5;
const COLORS = {
    paper: "#ffffff",
    text: "#1e2d3d",
    muted: "#485e73",
    border: "#b5c5d4",
    accent: "#176b75",
    highlight: "#e4f7f6",
    departments: ["#176b75", "#4854a3", "#93456f", "#516b31", "#94521e"],
};

function svgElement(tag, attrs, text) {
    const element = document.createElementNS(SVG_NS, tag);
    for (const [name, value] of Object.entries(attrs)) {
        element.setAttribute(name, value);
    }
    if (text) {
        element.textContent = text;
    }
    return element;
}

function textElement(text, x, y, width, attrs) {
    const svg = svgElement("svg", { x, y, width, height: 20, overflow: "hidden" });
    svg.append(svgElement("text", { x: 0, y: 15, ...attrs }, text));
    return svg;
}

function cardContent(node, options) {
    const { display_name: name } = node.data.record;
    const subtitle = node.data.record[options.subtitle];
    const color = node.data.record[options.color];
    const x = options.avatarField ? 55 : 13;
    const width = CARD_WIDTH - x - 10;
    const highlighted = node.data._highlighted;
    const card = svgElement("g", {
        class: "o_hierarchy_d3_card",
        "data-record-id": node.data.id,
        role: "button",
        tabindex: 0,
        "aria-label": name,
    });
    card.append(
        svgElement("title", {}, subtitle ? `${name} — ${subtitle}` : name),
        svgElement("rect", {
            class: "o_hierarchy_d3_card_border",
            width: CARD_WIDTH,
            height: CARD_HEIGHT,
            rx: 8,
            fill: highlighted ? COLORS.highlight : COLORS.paper,
            stroke: highlighted ? COLORS.accent : COLORS.border,
            "stroke-width": highlighted ? 2.5 : 1,
        }),
        textElement(name, x, subtitle ? 15 : 24, width, {
            "font-size": 14,
            "font-weight": 650,
            fill: COLORS.text,
        }),
    );
    if (subtitle) {
        card.append(textElement(subtitle, x, 36, width, { "font-size": 12, fill: COLORS.muted }));
    }
    if (Number.isInteger(color) && color > 0) {
        card.append(
            svgElement("rect", {
                x: 1,
                y: 13,
                width: 3,
                height: 42,
                rx: 1.5,
                fill: COLORS.departments[color % COLORS.departments.length],
            }),
        );
    }
    if (options.avatarField) {
        card.append(
            svgElement("image", {
                x: 10,
                y: 15,
                width: 38,
                height: 38,
                href: imageUrl(options.resModel, node.data.id, options.avatarField, {
                    width: 96,
                    height: 96,
                }),
            }),
        );
    }
    return card;
}

function drawCard(group, node, options) {
    group.querySelector(".o_hierarchy_d3_card")?.remove();
    if (node.id === LAYOUT_ROOT) {
        group.setAttribute("display", "none");
        return;
    }
    const card = cardContent(node, options);
    card.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            options.openRecord(node.data.id, event.ctrlKey || event.metaKey);
        }
    };
    card.onclick = (event) => {
        options.openRecord(node.data.id, event.ctrlKey || event.metaKey);
    };
    card.onauxclick = (event) => {
        if (event.button === 1) {
            event.preventDefault();
            options.openRecord(node.data.id, true);
        }
    };
    group.insertBefore(card, group.querySelector(".node-button-g"));

    const toggle = group.querySelector(".node-button-g");
    if (node.children || node._children) {
        const label = node.children
            ? _t("Collapse %s", node.data.record.display_name)
            : _t("Expand %s", node.data.record.display_name);
        toggle.setAttribute("role", "button");
        toggle.setAttribute("tabindex", 0);
        toggle.setAttribute("aria-expanded", Boolean(node.children));
        toggle.setAttribute("aria-label", label);
    }
}

function drawToggle({ node }) {
    const graphic = svgElement("svg", { width: 36, height: 36, "aria-hidden": "true" });
    graphic.append(
        svgElement("circle", { cx: 18, cy: 18, r: 11, fill: COLORS.paper, stroke: COLORS.accent }),
        svgElement("path", {
            d: node.children ? "M13 18h10" : "M13 18h10m-5 -5v10",
            fill: "none",
            stroke: COLORS.accent,
            "stroke-width": 1.5,
        }),
    );
    return graphic.outerHTML;
}

export function createChart(library, container, data, options) {
    const chart = new library.OrgChart()
        .container(container)
        .data(data)
        .nodeWidth((node) => (node.id === LAYOUT_ROOT ? 0 : CARD_WIDTH))
        .nodeHeight((node) => (node.id === LAYOUT_ROOT ? 0 : CARD_HEIGHT))
        .nodeButtonWidth(() => 36)
        .nodeButtonHeight(() => 36)
        .nodeButtonX(() => -18)
        .nodeButtonY(() => -18)
        .siblingsMargin(() => 24)
        .neighbourMargin(() => 30)
        .childrenMargin(() => 42)
        .minPagingVisibleNodes(() => data.length)
        .initialExpandLevel(data.length)
        .scaleExtent([MIN_ZOOM, MAX_ZOOM])
        .compact(false)
        .setActiveNodeCentered(false)
        .duration(0)
        .defaultFont("system-ui, sans-serif")
        .nodeContent(() => "")
        .buttonContent(drawToggle)
        .nodeUpdate(function (node) {
            drawCard(this, node, options);
        })
        .linkUpdate(function (node) {
            this.setAttribute("display", node.parent.id === LAYOUT_ROOT ? "none" : "inline");
            this.setAttribute("stroke", COLORS.border);
            this.setAttribute("stroke-width", 1.5);
        })
        .render();

    function setView(box, scale) {
        const { centerG, svg, svgWidth, svgHeight, zoomBehavior } = chart.getChartState();
        centerG.interrupt().attr("transform", null);
        svg.interrupt().call(
            zoomBehavior.transform,
            library.zoomIdentity
                .translate(svgWidth / 2, svgHeight / 2)
                .scale(scale)
                .translate(-box.x - box.width / 2, -box.y - box.height / 2),
        );
    }

    function fit() {
        const { root, svgWidth, svgHeight } = chart.getChartState();
        const nodes = root.descendants().slice(1);
        const left = Math.min(...nodes.map(({ x }) => x)) - CARD_WIDTH / 2;
        const right = Math.max(...nodes.map(({ x }) => x)) + CARD_WIDTH / 2;
        const top = Math.min(...nodes.map(({ y }) => y));
        const bottom = Math.max(...nodes.map(({ y }) => y)) + CARD_HEIGHT;
        const box = { x: left, y: top, width: right - left, height: bottom - top };
        const scale = Math.min(svgWidth / (box.width + 32), svgHeight / (box.height + 32), 1);
        setView(box, Math.max(scale, MIN_ZOOM));
    }

    return {
        fit,
        resize({ width, height }) {
            chart.svgWidth(width).svgHeight(height);
            chart.getChartState().svg.attr("width", width).attr("height", height);
            fit();
        },
        zoom(factor) {
            const { svg, zoomBehavior } = chart.getChartState();
            svg.interrupt().call(zoomBehavior.scaleBy, factor);
        },
        find(id) {
            chart.clearHighlighting().setHighlighted(id).render();
            const { root, svg, lastTransform } = chart.getChartState();
            const { x, y } = root.descendants().find(({ data }) => data.id === id);
            setView(
                { x: x - CARD_WIDTH / 2, y, width: CARD_WIDTH, height: CARD_HEIGHT },
                Math.max(lastTransform.k, 1),
            );
            svg.select(`[data-record-id="${id}"]`).node()?.focus({ preventScroll: true });
        },
        get state() {
            return chart.getChartState();
        },
        destroy() {
            const { svg } = chart.getChartState();
            svg.interrupt().selectAll("*").interrupt();
            chart.clear();
            svg.remove();
        },
    };
}
