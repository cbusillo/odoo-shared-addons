export const LAYOUT_ROOT = "layout-root";

export function buildForest(records, parentField) {
    const ids = new Set(records.map(({ id }) => id));
    const nodes = new Map(
        records.map((record) => {
            const parentId = record[parentField];
            return [
                record.id,
                {
                    id: record.id,
                    parentId: ids.has(parentId) ? parentId : LAYOUT_ROOT,
                    record,
                },
            ];
        }),
    );
    const visited = new Set([LAYOUT_ROOT]);
    let hasCycles = false;
    for (const node of nodes.values()) {
        let current = node;
        const path = new Set();
        while (!visited.has(current.id)) {
            path.add(current.id);
            if (path.has(current.parentId)) {
                current.parentId = LAYOUT_ROOT;
                hasCycles = true;
            }
            if (visited.has(current.parentId)) {
                break;
            }
            current = nodes.get(current.parentId);
        }
        for (const id of path) {
            visited.add(id);
        }
    }
    return { nodes: [{ id: LAYOUT_ROOT }, ...nodes.values()], hasCycles };
}
