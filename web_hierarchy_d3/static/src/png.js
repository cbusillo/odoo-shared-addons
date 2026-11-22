const PNG_MAX_SIDE = 4096;

async function inlineImage(image) {
    try {
        const response = await fetch(image.getAttribute("href"), { redirect: "error" });
        const blob = await response.blob();
        if (
            !response.ok ||
            !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(blob.type)
        ) {
            image.remove();
            return;
        }
        const reader = new FileReader();
        const dataUrl = await new Promise((resolve, reject) => {
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(blob);
        });
        image.setAttribute("href", dataUrl);
    } catch {
        image.remove();
    }
}

export async function exportPng({ svg, centerG, nodesWrapper }) {
    const box = nodesWrapper.node().getBBox();
    const width = Math.ceil(box.width + 32);
    const height = Math.ceil(box.height + 32);
    const scale = Math.min(2, PNG_MAX_SIDE / Math.max(width, height));
    const original = svg.node();
    const copy = original.cloneNode(false);
    copy.append(centerG.node().cloneNode(true));
    copy.firstElementChild.removeAttribute("transform");
    copy.setAttribute("width", width);
    copy.setAttribute("height", height);
    copy.setAttribute("viewBox", `${box.x - 16} ${box.y - 16} ${width} ${height}`);
    copy.querySelectorAll(".node-button-g, foreignObject, [display='none']").forEach((node) =>
        node.remove(),
    );
    await Promise.all([...copy.querySelectorAll("image")].map(inlineImage));

    const source = new XMLSerializer().serializeToString(copy);
    const url = URL.createObjectURL(new Blob([source], { type: "image/svg+xml;charset=utf-8" }));
    try {
        const image = new Image();
        image.src = url;
        await image.decode();
        const canvas = document.createElement("canvas");
        canvas.width = Math.ceil(width * scale);
        canvas.height = Math.ceil(height * scale);
        const context = canvas.getContext("2d");
        context.fillStyle = "#f3f6f9";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/png");
    } finally {
        URL.revokeObjectURL(url);
    }
}
