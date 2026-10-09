/** @odoo-module */

import { registry } from "@web/core/registry"
import {
    composerSelector,
    composerStepTimeout,
    getConfigParameterValue,
    getComposerInput,
    openDiscussApplication,
    openDiscussThread,
    setComposerValue,
} from "./discuss_tour_helpers"

registry.category("web_tour.tours").add("drl_record_link_fid_label", {
    test: true,
    url: "/web",
    steps: () => {
        const productId = getConfigParameterValue("drl_fid_label_product_id")
        const expectedLabel = getConfigParameterValue("drl_fid_label_expected_label")
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
                content: "Type raw fid URL",
                trigger: composerSelector,
                run() {
                    setComposerValue(
                        `${window.location.origin}/web#fid=${productId}&model=product.product&view_type=form`,
                    )
                },
            },
            {
                content: "Send",
                trigger:
                    ".o-mail-Composer .o-mail-Composer-send, .o-mail-Composer button[title='Send']",
                run: "click",
            },
            {
                content: "Labelized",
                trigger: labeledLinkSelector,
                run() {
                    const anchorElement =
                        document.querySelector(labeledLinkSelector)
                    if (!anchorElement) {
                        throw new Error("Labelized link not found")
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
