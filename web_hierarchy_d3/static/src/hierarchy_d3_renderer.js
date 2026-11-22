import { Component, onMounted, onPatched, onWillUnmount, signal, t, useProps } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

import { createChart } from "./chart";
import { buildForest } from "./forest";
import { exportPng } from "./png";

const LIBRARY_URL = "/web_hierarchy_d3/static/lib/org-chart.min.js";

export class HierarchyD3Renderer extends Component {
    static template = "web_hierarchy_d3.HierarchyD3Renderer";

    props = useProps({
        model: t.object(),
        openRecord: t.function(),
        archInfo: t.object(),
    });

    canvas = signal.ref();
    query = signal("");
    showMatches = signal(false);
    hasCycles = signal(false);
    exportPending = signal(false);
    chartUnavailable = signal(false);

    setup() {
        this.notification = useService("notification");
        onMounted(() => {
            this.resizeObserver = new ResizeObserver(([entry]) => {
                const { width, height } = entry.contentRect;
                if (width && height) {
                    this.chart?.resize({ width, height });
                }
            });
            this.resizeObserver.observe(this.canvas());
            this.syncChart();
        });
        onPatched(() => this.syncChart());
        onWillUnmount(() => {
            this.resizeObserver.disconnect();
            this.chart?.destroy();
        });
    }

    get matches() {
        const query = this.query().trim().toLocaleLowerCase();
        if (!query) {
            return [];
        }
        return this.props.model.root.records
            .filter(({ display_name }) => display_name.toLocaleLowerCase().includes(query))
            .slice(0, 10);
    }

    async syncChart() {
        const { model, archInfo } = this.props;
        const root = model.root;
        if (this.renderedRoot === root) {
            return;
        }
        this.renderedRoot = root;
        this.chart?.destroy();
        this.chart = null;
        this.query.set("");
        this.showMatches.set(false);
        this.hasCycles.set(false);
        if (!root.records.length) {
            return;
        }
        try {
            await loadJS(LIBRARY_URL);
            const container = this.canvas();
            if (!container || this.renderedRoot !== root) {
                return;
            }
            const forest = buildForest(root.records, model.parentFieldName);
            this.chart = createChart(window.OdooHierarchyD3, container, forest.nodes, {
                ...archInfo.chartFields,
                avatarField: archInfo.avatarField,
                resModel: model.resModel,
                openRecord: (resId, newWindow) => this.props.openRecord({ resId }, newWindow),
            });
            this.chartUnavailable.set(false);
            this.hasCycles.set(forest.hasCycles);
            this.chart.resize({ width: container.clientWidth, height: container.clientHeight });
        } catch (error) {
            if (this.canvas() && this.renderedRoot === root) {
                this.chartUnavailable.set(true);
                console.error(error);
            }
        }
    }

    onInput(event) {
        this.query.set(event.target.value);
        this.showMatches.set(Boolean(this.query().trim()));
    }

    onFindKeydown(event) {
        if (event.key === "Escape") {
            this.showMatches.set(false);
        } else if (event.key === "Enter" && this.matches.length) {
            event.preventDefault();
            this.find(this.matches[0]);
        }
    }

    find(record) {
        this.query.set(record.display_name);
        this.showMatches.set(false);
        this.chart?.find(record.id);
    }

    async download() {
        if (!this.chart || this.exportPending()) {
            return;
        }
        this.exportPending.set(true);
        const chart = this.chart;
        try {
            const url = await exportPng(chart.state);
            if (this.canvas() && this.chart === chart) {
                const link = document.createElement("a");
                link.download = "hierarchy.png";
                link.href = url;
                link.click();
            }
        } catch {
            this.notification.add(_t("The chart could not be exported."), { type: "danger" });
        } finally {
            this.exportPending.set(false);
        }
    }
}
