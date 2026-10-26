import { patch } from "@web/core/utils/patch"
import { UseSuggestion } from "@mail/core/common/suggestion_hook"

const originalInsert = UseSuggestion.prototype.insert

function insertSuggestion(option) {
    if (this.search.results?.type !== "RecordLink" || !option?.source) {
        return originalInsert.call(this, option)
    }
    if (this.composerService.htmlEnabled) {
        return originalInsert.call(this, { ...option, label: option.source })
    }
    const position = this.detection.position
    this.composer.composerText =
        this.composer.composerText.substring(0, position) +
        this.composer.composerText.substring(this.composer.selection.end)
    this.clearSearch()
    this.composer.insertText(`${option.source} `, position)
}

patch(UseSuggestion.prototype, { insert: insertSuggestion })
