"""Email content builders. Kept separate from transport so copy/templates
can evolve without touching the SMTP sender."""


def password_reset_email(code: str, ttl_minutes: int) -> tuple[str, str, str]:
    """Build the password-reset OTP email.

    Returns (subject, plain_text_body, html_body).
    """
    subject = "Your BlackClap password reset code"

    plain = (
        f"Your BlackClap password reset code is: {code}\n\n"
        f"This code expires in {ttl_minutes} minutes. "
        "Enter it in the app to set a new password.\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "your password won't change."
    )

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            max-width:480px;margin:0 auto;padding:24px;color:#1a1a1a">
  <h2 style="color:#9333EA;margin:0 0 16px">BlackClap</h2>
  <p style="font-size:16px;margin:0 0 16px">Use this code to reset your password:</p>
  <div style="font-size:32px;font-weight:700;letter-spacing:8px;
              background:#f4f0fb;color:#9333EA;padding:16px;text-align:center;
              border-radius:12px;margin:0 0 16px">{code}</div>
  <p style="font-size:14px;color:#666;margin:0 0 8px">
    This code expires in {ttl_minutes} minutes.
  </p>
  <p style="font-size:14px;color:#666;margin:0">
    If you didn't request this, you can safely ignore this email — your
    password won't change.
  </p>
</div>"""

    return subject, plain, html
