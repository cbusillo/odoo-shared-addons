import { Domain } from "@web/core/domain";
import { orderByToString } from "@web/search/utils/order_by";
import { registry } from "@web/core/registry";
import { HierarchyArchParser } from "@web_hierarchy/hierarchy_arch_parser";
import { HierarchyModel } from "@web_hierarchy/hierarchy_model";
import { hierarchyView } from "@web_hierarchy/hierarchy_view";

import { HierarchyD3Renderer } from "./hierarchy_d3_renderer";

const RECORD_LIMIT = 200;
const DETAIL_TYPES = { subtitle: "char", color: "integer" };
const VISIBLE_MODIFIERS = new Set([null, "False", "0"]);

class HierarchyD3ArchParser extends HierarchyArchParser {
    parse(xmlDoc, models, modelName) {
        const archInfo = super.parse(xmlDoc, models, modelName);
        const { fields } = models[modelName];
        const chartFields = {};
        const fieldNodes = {};
        for (const [key, field] of Object.entries(archInfo.fieldNodes)) {
            const visible =
                VISIBLE_MODIFIERS.has(field.invisible) &&
                VISIBLE_MODIFIERS.has(field.column_invisible);
            if (visible && field.name === "name" && field.type === "char") {
                fieldNodes[key] = field;
            }
            const detail = field.options.hierarchy_d3;
            if (
                !Object.hasOwn(DETAIL_TYPES, detail) ||
                DETAIL_TYPES[detail] !== field.type ||
                !visible ||
                chartFields[detail]
            ) {
                continue;
            }
            chartFields[detail] = field.name;
            fieldNodes[key] = field;
        }
        const avatarField =
            fields[archInfo.avatarField]?.type === "binary" ? archInfo.avatarField : null;
        return { ...archInfo, avatarField, chartFields, fieldNodes };
    }
}

class HierarchyD3Model extends HierarchyModel {
    async _loadData(config) {
        const useName = this.activeFields.name && this.fields.name.type === "char";
        const nameField = useName ? "name" : "display_name";
        const specification = { [nameField]: {}, [this.parentFieldName]: {} };
        for (const field of this.activeFieldNames) {
            if (["char", "integer"].includes(this.fields[field].type)) {
                specification[field] = {};
            }
        }
        const order = [...config.orderBy];
        if (!order.some(({ name }) => name === "id")) {
            order.push({ name: "id", asc: true });
        }
        const domain = new Domain(config.domain).toList();
        const { records } = await this.orm.webSearchRead(this.resModel, domain, {
            specification,
            context: config.context,
            order: orderByToString(order),
            limit: RECORD_LIMIT + 1,
            count_limit: RECORD_LIMIT + 1,
        });
        return records.map((record) => ({
            ...record,
            display_name: record[nameField] || "",
        }));
    }

    _createRoot(config, result) {
        const records = result.slice(0, RECORD_LIMIT);
        return {
            records,
            resIds: records.map(({ id }) => id),
            truncated: result.length > RECORD_LIMIT,
        };
    }
}

export const hierarchyD3View = {
    ...hierarchyView,
    ArchParser: HierarchyD3ArchParser,
    Model: HierarchyD3Model,
    Renderer: HierarchyD3Renderer,
};

registry.category("views").add("hierarchy_d3", hierarchyD3View);
