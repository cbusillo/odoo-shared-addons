/** @odoo-module */

import { registry } from "@web/core/registry"
import {
    composerSelector,
    composerStepTimeout,
    getComposerInput,
    getConfigParameterValue,
    openDiscussApplication,
    openDiscussThread,
    setComposerValue,
} from "./discuss_tour_helpers"

registry.category("web_tour.tours").add("drl_record_link_label", {
    test: true,
    url: "/web",
    steps: () => {
        const productId = getConfigParameterValue("drl_label_product_id")
        const expectedLabel = getConfigParameterValue("drl_label_expected_label")
        if (!productId || !expectedLabel) {
            throw new Error("Missing record link tour fixture")
        }
        const labeledLinkSelector = `:is(.o_Message, .o-mail-Message) a[data-oe-model="product.product"][data-oe-id="${productId}"][data-drl-labeled="1"]`
        return [
            { content: "Wait client", trigger: ".o_web_client", timeout: 20000 },
            {
                content: "Open Discuss",
                trigger: ".o_app, .o-mail-Discuss, .o-mail-Thread",
                run: openDiscussApplication,
            },
            {
                content: "Wait for Discuss channels",
                trigger:
                    ".o-mail-DiscussSidebarChannel, .o-mail-DiscussSidebar-item",
                timeout: 20000,
            },
            {
                content: "Open a thread",
                trigger: ".o-mail-Discuss, .o-mail-Thread",
                run() {
                    openDiscussThread()
                },
            },
            {
                content: "Focus composer",
                trigger: composerSelector,
                run() {
                    const composerElement = getComposerInput()
                    if (!composerElement) {
                        throw new Error("Composer input not found")
                    }
                    composerElement.click()
                },
                timeout: composerStepTimeout,
            },
            {
                content: "Insert fixture URL",
                trigger: composerSelector,
                run() {
                    setComposerValue(
                        `${window.location.origin}/web#id=${productId}&model=product.product&view_type=form`,
                    )
                },
            },
            // Send message
            {
                content: "Send message",
                trigger:
                    ".o-mail-Composer .o-mail-Composer-send, .o-mail-Composer button[title='Send']",
                run: "click",
                timeout: 10000,
            },
            {
                content: "Labelized link in message",
                trigger: labeledLinkSelector,
                run() {
                    const anchorElement =
                        document.querySelector(labeledLinkSelector)
                    if (!anchorElement) {
                        throw new Error("message link not found")
                    }
                    if (anchorElement.textContent.trim() !== expectedLabel) {
                        throw new Error(`Expected label ${JSON.stringify(expectedLabel)}, got ${JSON.stringify(anchorElement.textContent)}`)
                    }
                },
                timeout: 30000,
            },
        ]
    },
})
