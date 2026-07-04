"""
Public, browser-facing account-deletion flow.

Google Play requires a publicly accessible URL where a user can request account
deletion WITHOUT the app. The Flutter Settings screen opens
`https://blackclap.com/delete-account` in an external browser, so these routes
are mounted at the site root (no `/api/v1` prefix) and render server-side HTML —
no JavaScript or tokens required.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.account.service import GRACE_PERIOD_DAYS, request_account_deletion

router = APIRouter(tags=["Account Deletion"])

_PAGE_STYLE = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0; padding: 24px; background: #0f0f10; color: #f2f2f2;
    display: flex; justify-content: center;
  }
  .card {
    width: 100%; max-width: 460px; background: #1c1c1e; border-radius: 16px;
    padding: 28px; margin-top: 24px; border: 1px solid #2c2c2e;
  }
  h1 { font-size: 22px; margin: 0 0 8px; }
  p { line-height: 1.5; color: #c7c7cc; font-size: 15px; }
  ul { color: #c7c7cc; font-size: 15px; line-height: 1.6; padding-left: 20px; }
  label { display: block; font-size: 13px; margin: 16px 0 6px; color: #aeaeb2; }
  input {
    width: 100%; padding: 12px 14px; border-radius: 10px; border: 1px solid #3a3a3c;
    background: #2c2c2e; color: #fff; font-size: 15px;
  }
  button {
    width: 100%; margin-top: 22px; padding: 14px; border: 0; border-radius: 10px;
    background: #e5484d; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer;
  }
  button:hover { background: #d13438; }
  .note { font-size: 13px; color: #8e8e93; margin-top: 18px; }
  .ok { color: #30d158; }
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · BlackClap</title>
<style>{_PAGE_STYLE}</style>
</head><body><div class="card">{body}</div></body></html>"""


@router.get("/delete-account", response_class=HTMLResponse)
async def delete_account_page() -> Any:
    """Render the account-deletion request form."""
    body = f"""
      <h1>Delete your BlackClap account</h1>
      <p>Enter your credentials to request deletion. When you confirm:</p>
      <ul>
        <li>Your account is deactivated immediately and hidden from other users.</li>
        <li>You have <strong>{GRACE_PERIOD_DAYS} days</strong> to change your mind —
            just log back in to cancel.</li>
        <li>After {GRACE_PERIOD_DAYS} days your profile, posts, likes and follows are
            permanently deleted, your uploaded media is removed, and your messages and
            comments are anonymized.</li>
      </ul>
      <form method="post" action="/delete-account">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" required autocomplete="email">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required autocomplete="current-password">
        <label for="confirm">Type <strong>DELETE</strong> to confirm</label>
        <input id="confirm" name="confirm" type="text" required autocomplete="off" placeholder="DELETE">
        <button type="submit">Delete my account</button>
      </form>
      <p class="note">Need help instead? Contact support@blackclap.com</p>
    """
    return HTMLResponse(_page("Delete account", body))


@router.post("/delete-account", response_class=HTMLResponse)
async def submit_delete_account(
    email: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Handle the deletion form. Always shows a generic confirmation so the page
    cannot be used to probe which emails / passwords are valid.
    """
    if confirm.strip().upper() == "DELETE":
        # Result intentionally ignored for the user-facing message (anti-enumeration).
        await request_account_deletion(db, email=email, password=password)

    deletion_date = (
        datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)
    ).strftime("%B %d, %Y")

    body = f"""
      <h1 class="ok">Request received</h1>
      <p>If an account matches those details, it has been deactivated and is
         scheduled for permanent deletion on <strong>{deletion_date}</strong>.</p>
      <p>Changed your mind? Simply log back in to the BlackClap app before that
         date and your account will be fully restored.</p>
      <p class="note">You can close this page.</p>
    """
    return HTMLResponse(_page("Request received", body))
