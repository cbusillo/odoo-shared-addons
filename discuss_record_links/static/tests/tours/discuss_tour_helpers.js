const CHANNEL_NAME = "DRL Tour"
const COMPOSER_SELECTORS = [
    ".o-mail-Discuss .o-mail-Composer [contenteditable='true']",
    ".o-mail-Discuss textarea.o-mail-Composer-input",
]

export const composerSelector = COMPOSER_SELECTORS.join(", ")
export const composerStepTimeout = 40000

export const assertFixtureThread = () => {
    const header = document.querySelector(".o-mail-DiscussContent-threadName")
    if (header?.value !== CHANNEL_NAME) {
        throw new Error("The fixture Discuss thread is not active")
    }
}

export const isVisible = (element) => {
    if (!element) {
        return false
    }
    const style = window.getComputedStyle(element)
    if (style.display === "none" || style.visibility === "hidden") {
        return false
    }
    return element.getClientRects().length > 0
}

export const getComposerInput = () => {
    for (const selector of COMPOSER_SELECTORS) {
        const candidates = Array.from(document.querySelectorAll(selector))
        const visible = candidates.find((element) => isVisible(element) && !element.disabled)
        if (visible) {
            return visible
        }
    }
    return null
}

export const getComposerValue = () => {
    const composerElement = getComposerInput()
    if (!composerElement) {
        return ""
    }
    if (
        composerElement instanceof HTMLInputElement ||
        composerElement instanceof HTMLTextAreaElement
    ) {
        return composerElement.value
    }
    return composerElement.textContent || ""
}

export const setComposerValue = (value, { triggerSuggestionAutocomplete = false } = {}) => {
    const composerElement = getComposerInput()
    if (!composerElement) {
        throw new Error("Composer input not found")
    }
    if (
        composerElement instanceof HTMLInputElement ||
        composerElement instanceof HTMLTextAreaElement
    ) {
        composerElement.value = value
        composerElement.dispatchEvent(new Event("input", { bubbles: true }))
        composerElement.dispatchEvent(new Event("change", { bubbles: true }))
    } else {
        composerElement.textContent = value
        composerElement.dispatchEvent(new Event("input", { bubbles: true }))
    }
    if (triggerSuggestionAutocomplete) {
        composerElement.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "[" }))
    }
}

export const getConfigParameterValue = (parameterName) => {
    try {
        const request = new XMLHttpRequest()
        request.open("POST", "/web/dataset/call_kw", false)
        request.setRequestHeader("Content-Type", "application/json")
        request.send(
            JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: "ir.config_parameter",
                    method: "get_str",
                    args: [parameterName],
                    kwargs: {},
                },
                id: 1,
            }),
        )
        const response = JSON.parse(request.responseText || "{}")
        return response?.result || ""
    } catch {
        return ""
    }
}
