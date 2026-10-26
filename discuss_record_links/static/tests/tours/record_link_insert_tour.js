import { registry } from "@web/core/registry"
import {
    composerSelector,
    composerStepTimeout,
    getComposerInput,
    getComposerValue,
    assertFixtureThread,
    setComposerValue,
} from "./discuss_tour_helpers"

const messageLinkSelector = [
    ".o_Message .o_Message_content a[href*='/web#']",
    ".o_Message .o_Message_content a[href*='/odoo#']",
    ".o_Message .o_Message_content a[href*='/odoo/']",
    ".o-mail-Message a[href*='/web#']",
    ".o-mail-Message a[href*='/odoo#']",
    ".o-mail-Message a[href*='/odoo/']",
    ".o-mail-Message-content a[href*='/web#']",
    ".o-mail-Message-content a[href*='/odoo#']",
    ".o-mail-Message-content a[href*='/odoo/']",
    ".o-mail-Message-body a[href*='/web#']",
    ".o-mail-Message-body a[href*='/odoo#']",
    ".o-mail-Message-body a[href*='/odoo/']",
].join(", ")

registry.category("web_tour.tours").add("drl_record_link_insert", {
    test: true,
    url: "/web",
    steps: () => [
        {
            content: "Wait for web client",
            trigger: ".o_web_client",
            timeout: 20000,
        },
        {
            content: "Focus composer",
            trigger: composerSelector,
            run() {
                assertFixtureThread()
                const composerElement = getComposerInput()
                if (!composerElement) {
                    throw new Error("Composer input not found")
                }
                composerElement.click()
            },
            timeout: composerStepTimeout,
        },
        {
            content: "Type bracket to open suggestions",
            trigger: composerSelector,
            run() {
                setComposerValue("[pro widget", {
                    triggerSuggestionAutocomplete: true,
                })
            },
        },
        {
            content: "Select first record suggestion",
            trigger: ".o-mail-Composer-suggestion",
            run: "click",
            timeout: 10000,
        },
        {
            content: "Ensure URL inserted",
            trigger: composerSelector,
            run() {
                const text = getComposerValue().trim()
                if (
                    !text.includes("/web#id=") ||
                    !text.includes("&model=") ||
                    text.startsWith("[")
                ) {
                    throw new Error("Selecting a record must replace the search with its URL")
                }
            },
        },
        {
            content: "Send message",
            trigger:
                ".o-mail-Composer .o-mail-Composer-send, .o-mail-Composer button[title='Send']",
            run: "click",
            timeout: 10000,
        },
        {
            content: "Inserted URL present in message",
            trigger: messageLinkSelector,
            timeout: 20000,
        },
    ],
})
