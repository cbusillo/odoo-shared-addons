from odoo import api


def pre_init_hook(env: api.Environment) -> None:
    env.cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'res_device_log' AND table_schema = current_schema()
        AND column_name IN ('platform', 'browser', 'device_type')
    """)
    columns = {row[0] for row in env.cr.fetchall()}
    if not columns:
        return
    if columns != {"platform", "browser", "device_type"}:
        raise RuntimeError("Historical device columns are incomplete; install before native field cleanup.")
    env.cr.execute("""
        ALTER TABLE res_device_log
        ADD COLUMN IF NOT EXISTS legacy_user_agent_unavailable boolean DEFAULT false
    """)
    env.cr.execute("""
        UPDATE res_device_log SET legacy_user_agent_unavailable = true
        WHERE user_agent IS NULL
    """)
