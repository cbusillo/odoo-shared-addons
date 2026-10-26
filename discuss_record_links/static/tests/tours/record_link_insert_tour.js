import { registry } from "@web/core/registry"
import {
    composerSelector,
    composerStepTimeout,
    getComposerInput,
    getComposerValue,
    getConfigParameterValue,
    assertFixtureThread,
    setComposerValue,
} from "./discuss_tour_helpers"

const messageLinkSelector = ".o-mail-Discuss .o-mail-Message a[href*='/web#']"

registry.category("web_tour.tours").add("drl_record_link_insert", {
    test: true,
    url: "/web",
    steps: () => {
        const productId = getConfigParameterValue("drl_insert_product_id")
        if (!productId) {
            throw new Error("Missing insertion tour fixture")
        }
        const expectedUrl = `${window.location.origin}/web#id=${productId}&model=product.product&view_type=form`
        return [
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
                trigger:
                    ".o-mail-Discuss textarea.o-mail-Composer-input:value(/web#id=/), .o-mail-Discuss .o-mail-Composer [contenteditable='true']:contains(/web#id=/)",
                run() {
                    const text = getComposerValue().trim()
                    if (text !== expectedUrl) {
                        throw new Error(
                            `Selecting a record must replace the search with its URL; got ${JSON.stringify(text)}`,
                        )
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
        ]
    },
})
