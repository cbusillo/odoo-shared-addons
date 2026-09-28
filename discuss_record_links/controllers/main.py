from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

from ..models.config_util import ModelCfg, extract_template_fields, load_config, parse_prefix, render_template


def _ensure_internal_user(env) -> None:
    # Record-link search and labels exist for the backend Discuss/Chatter UI.
    # Portal and public users never need them.
    if not env.user._is_internal():
        raise AccessError(env._("Record links are only available to internal users."))


def _display_fields(model_cfg: ModelCfg) -> list[str]:
    display_fields = {"display_name"}
    display_fields.update(extract_template_fields(model_cfg.display_template))
    return sorted(display_fields)


def _render_label(model_cfg: ModelCfg, row: dict) -> str:
    return render_template(model_cfg.display_template or "{{ display_name }}", row) or row.get("display_name")


class DiscussRecordLinks(http.Controller):
    """Search and label records for Discuss links.

    Both routes run with the caller's access rights: model ACLs and record
    rules decide what is returned. Records the caller cannot read are left
    out instead of failing the whole response.
    """

    @http.route("/discuss_record_links/search", type="jsonrpc", auth="user", methods=["POST"])
    def search(self, term: str = ""):
        env = request.env
        _ensure_internal_user(env)
        cfg = load_config(env)

        model_filter, query = parse_prefix(term or "", cfg)
        tokens = [t for t in (query or "").strip().split() if t]

        def build_domain(model_config: ModelCfg) -> fields.Domain:
            if not tokens:
                return fields.Domain([])
            search_fields = model_config.search or ["name"]
            search_domain: fields.Domain | None = None
            for token in tokens:
                or_domain = fields.Domain.OR([[(field, "ilike", token)] for field in search_fields])
                search_domain = fields.Domain.AND([search_domain, or_domain]) if search_domain is not None else or_domain
            return search_domain or fields.Domain([])

        suggestions = []
        for model_cfg in cfg.values():
            if model_filter and model_cfg.model != model_filter:
                continue
            if model_cfg.model not in env:
                continue
            model = env[model_cfg.model]
            if not model.has_access("read"):
                continue
            domain = build_domain(model_cfg)
            try:
                rows = model.search_read(domain, _display_fields(model_cfg), limit=model_cfg.limit)
            except AccessError:
                # A configured search or template field is restricted for this user.
                continue
            for r in rows:
                suggestions.append(
                    {
                        "group": model_cfg.label,
                        "model": model_cfg.model,
                        "id": r["id"],
                        "label": _render_label(model_cfg, r),
                    }
                )

        # Return a single flat list; client groups by .group
        return {"suggestions": suggestions}

    @http.route("/discuss_record_links/labels", type="jsonrpc", auth="user", methods=["POST"])
    def labels(self, targets: list[dict] | None = None):
        """Return rendered labels for a list of {model, id} using configured templates.

        Only models configured for record links are labelled.

        targets example: [{"model": "motor", "id": 42}, ...]
        """
        env = request.env
        _ensure_internal_user(env)
        cfg = load_config(env)
        by_model_cfg: dict[str, ModelCfg] = {model_cfg.model: model_cfg for model_cfg in cfg.values()}

        result: list[dict] = []
        if not targets:
            return result
        # Group ids by configured model
        by_model: dict[str, set[int]] = {}
        for t in targets:
            if not isinstance(t, dict):
                continue
            model = t.get("model")
            rid = t.get("id")
            if model not in by_model_cfg or model not in env:
                continue
            try:
                record_id = int(rid)
            except (TypeError, ValueError):
                continue
            if record_id > 0:
                by_model.setdefault(model, set()).add(record_id)

        for model, idset in by_model.items():
            model_cfg = by_model_cfg[model]
            records = env[model].browse(sorted(idset)).exists()._filtered_access("read")
            if not records:
                continue
            try:
                rows = records.read(_display_fields(model_cfg))
            except AccessError:
                # A template field (or a computed name) is restricted for this
                # user: label each record by display_name, and skip any record
                # whose name the user cannot compute.
                for record in records:
                    try:
                        # Compute alone so one failing record does not fail its batch.
                        display_name = record.with_prefetch(record._ids).display_name
                    except AccessError:
                        continue
                    result.append({"model": model, "id": record.id, "label": display_name})
                continue
            for r in rows:
                result.append({"model": model, "id": r["id"], "label": _render_label(model_cfg, r)})

        return result
