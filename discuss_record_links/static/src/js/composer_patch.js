import { patch } from "@web/core/utils/patch"
import { Composer } from "@mail/core/common/composer"
const originalNavigableListProps = Object.getOwnPropertyDescriptor(
    Composer.prototype,
    "navigableListProps",
)?.get

const getNavigableListProps = function () {
    const props = originalNavigableListProps ? originalNavigableListProps.call(this) : {}
    const items = this.suggestion?.search.results
    if (!items || items.type !== "RecordLink") {
        return props
    }
    props.options = items.suggestions.map((suggestion) => ({
        label: suggestion.label,
        source: `${window.location.origin}/web#id=${suggestion.id}&model=${suggestion.model}&view_type=form`,
        classList: "o-mail-Composer-suggestion",
    }))
    return props
}

const composerPatch = {}
Object.defineProperty(composerPatch, "navigableListProps", {
    configurable: true,
    enumerable: true,
    get: getNavigableListProps,
})

patch(Composer.prototype, composerPatch)
