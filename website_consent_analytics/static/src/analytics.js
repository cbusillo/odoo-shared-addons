import { cookie } from "@web/core/browser/cookie";

function savedConsent() {
    try {
        return JSON.parse(decodeURIComponent(cookie.get("website_cookies_bar") || "{}"))?.optional === true;
    } catch {
        return false;
    }
}

function consent(analytics) {
    return {
        analytics_storage: analytics,
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
    };
}

function command() {
    window.dataLayer.push(arguments);
}

let started = false;

export function startConsentAnalytics({ pages, eventForLink, preview }) {
    const marker = document.querySelector('meta[name="consent-first-ga4"]');
    const page = pages.get(window.location.pathname.replace(/\/$/, "") || "/");
    if (started || !marker || !page) {
        return;
    }
    const { mode, measurementId, origin } = JSON.parse(marker.content);
    const local = mode === "preview";
    if (local ? !preview : mode !== "production") {
        return;
    }
    started = true;
    let accepted = false;
    let pageSent = false;
    const settings = {
        page_location: origin + page.path,
        page_title: page.title,
        page_referrer: origin + "/",
        ignore_referrer: true,
        send_page_view: false,
        allow_google_signals: false,
        allow_ad_personalization_signals: false,
    };
    function emit(name, action) {
        if (!accepted) {
            return;
        }
        if (local) {
            preview({ accepted, name, action });
        } else {
            command("event", name, { ...settings, ...(action && { action }), send_to: measurementId });
        }
    }
    function choose(allow) {
        accepted = allow;
        if (local) {
            preview({ accepted });
        } else {
            window[`ga-disable-${measurementId}`] = !allow;
            if (allow && !pageSent) {
                window.dataLayer ??= [];
                command("consent", "default", consent("denied"));
                command("consent", "update", consent("granted"));
                command("js", new Date());
                command("config", measurementId, settings);
                const script = document.createElement("script");
                script.async = true;
                script.referrerPolicy = "no-referrer";
                script.setAttribute("src", `https://www.googletagmanager.com/gtag/js?id=${measurementId}`);
                document.head.appendChild(script);
            } else if (pageSent) {
                command("consent", "update", consent(allow ? "granted" : "denied"));
            }
        }
        if (allow && !pageSent) {
            pageSent = true;
            emit("page_view");
        }
    }
    document.addEventListener("optionalCookiesAccepted", () => choose(true));
    document.addEventListener("optionalCookiesDenied", () => choose(false));
    document.addEventListener("click", (event) => {
        const link = event.target.closest?.("a[href]");
        if (!link || !eventForLink || link.getAttribute("href").startsWith("#")) {
            return;
        }
        const selected = eventForLink(link);
        if (selected) {
            if (local) {
                event.preventDefault();
            }
            emit(selected.name, selected.action);
        }
    });
    choose(savedConsent());
}
