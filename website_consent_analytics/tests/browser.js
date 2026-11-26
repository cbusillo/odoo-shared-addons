(async () => {
    const { startConsentAnalytics } = odoo.loader.modules.get("@website_consent_analytics/analytics");
    const observed = [];
    const pages = new Map();
    const options = {
        pages,
        eventForLink: (link) => link.matches(".fixture-action") && { name: "selection", action: "phone" },
        preview: (state) => observed.push(state),
    };
    const assert = (condition, reason) => { if (!condition) throw new Error(reason); };
    const scripts = () => document.querySelectorAll("script[src*='googletagmanager.com']");
    const quiet = () => !scripts().length && !window.dataLayer && !window.fixtureTagLoads;
    const events = () => local ? observed.filter((state) => state.name) :
        Array.from(window.dataLayer || []).filter(([kind]) => kind === "event");
    const wait = () => new Promise((resolve) => setTimeout(resolve, 700));
    async function choose(button) {
        const modal = document.querySelector("#website_cookies_bar .modal");
        if (!modal.classList.contains("show")) {
            document.querySelector(".o_cookies_bar_toggle").click();
            await wait();
        }
        assert(modal.classList.contains("show"), "Native choices did not open");
        document.querySelector("#cookies-consent-" + button).click();
        await wait();
    }
    assert(!document.querySelector("#tracking_code, #tracking_code_config"), "Native eager tag present");
    startConsentAnalytics(options);
    await choose("all");
    assert(quiet() && !observed.length, "Unlisted page collected");
    await choose("essential");
    pages.set("/cookie-policy", { path: "/public", title: "Public page" });
    if (local) {
        startConsentAnalytics({ pages });
        assert(quiet(), "Preview without local check collected");
    }
    startConsentAnalytics(options);
    startConsentAnalytics(options);
    const link = document.createElement("a");
    link.href = "tel:00000";
    link.className = "fixture-action";
    link.textContent = "never-send";
    link.addEventListener("click", (event) => event.preventDefault());
    document.body.appendChild(link);
    link.click();
    assert(quiet() && !events().length, "Collection with essentials only");
    await choose("all");
    link.click();
    assert(events().length === 2, "Expected one page view and one action");
    if (local) {
        assert(quiet() && observed.at(-1).action === "phone", "Preview sent traffic or lost its action");
    } else {
        assert(window.fixtureTagLoads === 1 && scripts().length === 1, "Expected one intercepted tag");
        const [[, page, params], [, name, action]] = events();
        const origin = JSON.parse(document.querySelector("meta[name='consent-first-ga4']").content).origin;
        assert(page === "page_view" && params.page_location === origin + "/public" &&
            params.page_referrer === origin + "/" && params.page_title === "Public page" &&
            params.ignore_referrer && !params.send_page_view, "Unexpected page data");
        assert(name === "selection" && action.action === "phone", "Missing fixed event labels");
        assert(!JSON.stringify(window.dataLayer).match(/never-send|fragment|00000/), "Private value in commands");
        assert(window.dataLayer.filter(([kind]) => kind === "consent").every(([, , values]) =>
            ["ad_storage", "ad_user_data", "ad_personalization"].every((key) => values[key] === "denied")),
            "Advertising consent granted");
    }
    await choose("essential");
    link.click();
    assert(events().length === 2, "Collected after withdrawal");
    if (!local) {
        const key = JSON.parse(document.querySelector("meta[name='consent-first-ga4']").content).measurementId;
        assert(window["ga-disable-" + key] === true, "Loaded tag still enabled");
    }
    await choose("all");
    link.click();
    assert(events().length === 3 && (local ? quiet() : window.fixtureTagLoads === 1), "Duplicate on re-consent");
    console.log("test successful");
})();
