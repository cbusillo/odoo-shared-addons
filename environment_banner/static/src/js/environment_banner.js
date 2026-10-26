import { Component } from "@odoo/owl"
import { registry } from "@web/core/registry"
import { session } from "@web/session"

const NON_PRODUCTION_ENVIRONMENTS = new Set(["dev", "testing", "localhost"])

const normalizeHostnamePatterns = (hostnames) => {
    if (!Array.isArray(hostnames)) {
        return []
    }
    return hostnames
        .map((hostname) => (hostname || "").trim().toLowerCase())
        .filter(Boolean)
}

const escapeRegularExpression = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

const hostnamePatternToRegularExpression = (pattern) => {
    const escapedPattern = escapeRegularExpression(pattern).replace(/\\\*/g, ".*")
    return new RegExp(`^${escapedPattern}$`)
}

const matchesHostnamePattern = (hostname, pattern) => hostnamePatternToRegularExpression(pattern).test(hostname)

const hasEnvironmentLabel = (hostname, label) => {
    const dottedLabel = `.${label}.`
    const dashedLabel = `-${label}.`
    return (
        hostname.startsWith(`${label}.`)
        || hostname.includes(dottedLabel)
        || hostname.endsWith(`.${label}`)
        || hostname.startsWith(`${label}-`)
        || hostname.includes(dashedLabel)
        || hostname.endsWith(`-${label}`)
    )
}

const getEnvironmentBannerConfig = () => {
    const config = session["environment_banner"] || {}
    return {
        enabled: config["enabled"] !== false,
        productionHostnamePatterns: normalizeHostnamePatterns(config["production_hostnames"]),
    }
}

const resolveEnvironmentName = (hostname) => {
    if (hasEnvironmentLabel(hostname, "dev")) {
        return "dev"
    }
    if (hasEnvironmentLabel(hostname, "testing")) {
        return "testing"
    }
    const hasLocalSuffix = hostname.endsWith(".local") || hostname.includes(".local.")
    const hasLocalLabel = hostname.endsWith("-local") || hostname.includes("-local.")

    if (
        hostname.includes("localhost")
        || hasLocalSuffix
        || hasLocalLabel
        || hostname === "127.0.0.1"
        || hostname === "::1"
    ) {
        return "localhost"
    }
    return "other"
}

const isProductionHost = ({ hostname, environmentName, productionHostnamePatterns }) => {
    if (productionHostnamePatterns.length) {
        return productionHostnamePatterns.some((pattern) => matchesHostnamePattern(hostname, pattern))
    }
    return !NON_PRODUCTION_ENVIRONMENTS.has(environmentName)
}

export class EnvironmentBanner extends Component {
    static template = "environment_banner.EnvironmentBanner"

    get bannerClasses() {
        const baseClasses = "environment-banner text-center font-bold"

        const environmentClasses = {
            dev: "environment-dev",
            testing: "environment-testing",
            localhost: "environment-localhost",
            other: "environment-other",
        }

        return `${baseClasses} ${environmentClasses[this.state.environmentName] || environmentClasses.other}`
    }

    get bannerText() {
        const environmentLabels = {
            dev: "Development Environment",
            testing: "Testing Environment",
            localhost: "Local Development",
            other: "Non-Production Environment",
        }

        return environmentLabels[this.state.environmentName] || environmentLabels.other
    }

    setup() {
        const hostname = window.location.hostname || ""
        const config = getEnvironmentBannerConfig()
        const environmentName = resolveEnvironmentName(hostname.toLowerCase())
        const isProduction = isProductionHost({
            hostname: hostname.toLowerCase(),
            environmentName,
            productionHostnamePatterns: config.productionHostnamePatterns,
        })
        this.state = { hostname, environmentName, showBanner: config.enabled && !isProduction }
    }
}

export const environmentBanner = {
    Component: EnvironmentBanner,
}

registry.category("main_components").add("environment_banner", environmentBanner)
