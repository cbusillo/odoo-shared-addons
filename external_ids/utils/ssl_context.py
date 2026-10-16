import ssl


def build_ssl_context(use_ssl: bool, verify_ssl: bool) -> ssl.SSLContext | None:
    if not use_ssl:
        return None

    secure_context = ssl.create_default_context()
    if not verify_ssl:
        # insecure-tls: verification is off only where a site sets verify_ssl=False.
        # Allowed for private network paths to vendor-owned databases (Fishbowl),
        # where enforcing certificates risks breaking imports.
        # Decision: https://github.com/cbusillo/odoo-tenant-cm/pull/175#issuecomment-6222897727
        secure_context.check_hostname = False
        secure_context.verify_mode = ssl.CERT_NONE
    return secure_context
