async function checkHierarchy(test, ids) {
    const select = (selector) => document.querySelector(selector);
    const card = (id) => select(`.o_hierarchy_d3_card[data-record-id="${id}"]`);
    const allCards = () => [...document.querySelectorAll(".o_hierarchy_d3_card")];
    const transform = () => select(".o_hierarchy_d3_canvas g.chart").getAttribute("transform");
    const toggle = (id) => card(id)?.parentElement.querySelector(".node-button-g");
    const click = (element) => element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const assert = (condition, message) => {
        if (!condition) {
            throw new Error(message);
        }
    };

    async function waitFor(predicate, message) {
        for (let attempt = 0; attempt < 200; attempt++) {
            if (predicate()) {
                return;
            }
            await new Promise((resolve) => requestAnimationFrame(resolve));
        }
        throw new Error(message);
    }

    await waitFor(() => allCards().length, "The opted-in native action did not render the chart");
    if (test === "limit") {
        assert(allCards().length === 200, "The tree exceeded its record limit");
        assert(card(ids.first) && !card(ids.last), "The record ID tie-breaker changed");
        assert(
            select(".o_hierarchy_d3_limit")?.textContent.includes("200"),
            "The chart hid truncation",
        );
        console.log("test successful");
        return;
    }

    assert(allCards().length === 4, "The filtered forest should contain four records");
    assert(card(ids.root) && card(ids.second) && card(ids.detached), "A visible root is missing");
    assert(
        !card(ids.protected) && !card(ids.excluded) && !card(ids.inactive),
        "An excluded record was charted",
    );
    assert(
        !select(".o_hierarchy_d3_canvas").textContent.includes("Restricted synthetic tag"),
        "The hidden parent leaked through a chart label",
    );
    assert(
        document.querySelectorAll('.o_hierarchy_d3_canvas path.link[display="inline"]').length ===
            1,
        "The chart linked separate roots",
    );
    click(toggle(ids.root));
    await waitFor(() => !card(ids.child), "Collapse did not hide the child");
    click(toggle(ids.root));
    await waitFor(() => card(ids.child), "Expand did not restore the child");
    click(toggle(ids.root));
    await waitFor(() => !card(ids.child), "The child stayed expanded");

    const find = select('input[aria-label="Find in chart"]');
    find.value = "Limes";
    find.dispatchEvent(new Event("input", { bubbles: true }));
    await waitFor(
        () => select(".o_hierarchy_d3_matches button"),
        "Find did not return a hidden child",
    );
    click(select(".o_hierarchy_d3_matches button"));
    await waitFor(
        () => card(ids.child)?.querySelector('rect[stroke-width="2.5"]'),
        "Find did not reveal and highlight the match",
    );

    click(select('button[aria-label="Fit chart"]'));
    const fitted = transform();
    click(select('button[aria-label="Zoom in"]'));
    assert(transform() !== fitted, "Zoom did not change the chart transform");
    click(select('button[aria-label="Fit chart"]'));
    assert(transform() === fitted, "Fit did not restore the chart bounds");

    click(select(".o_searchview_dropdown_toggler"));
    const filter = () =>
        [...document.querySelectorAll(".o_filter_menu .o_menu_item")].find(
            (item) => item.textContent.trim() === "Only limes",
        );
    await waitFor(filter, "The native search filter is missing");
    click(filter());
    await waitFor(
        () => allCards().length === 1 && card(ids.child),
        "The native search filter did not narrow the chart",
    );

    click(card(ids.child));
    await waitFor(
        () =>
            select('.o_form_view [name="name"] input')?.value === "Limes" ||
            select('.o_form_view [name="name"]')?.textContent.trim() === "Limes",
        "The native action did not open the selected tag",
    );
    console.log("test successful");
}
