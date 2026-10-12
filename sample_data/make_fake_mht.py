"""
Builds a FAKE OneNote section export (.mht) for testing ingest.py.

All content here is made up (the company "Contoso" is Microsoft's standard
fictional company). The structure is a best guess at what OneNote writes when
you do File > Export > Section > Single File Web Page (*.mht):

  - An MHT file is really an email-style MIME message ("multipart/related").
  - One part is the HTML of the section, encoded as quoted-printable.
  - Other parts are images and other resources.
  - Each page starts with its title in a <p> styled with a large font
    (font-size:20.0pt), followed by a grey date and time line.

Run:  python make_fake_mht.py      -> writes fake_section.mht next to this file
"""

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import charset
from pathlib import Path
import html

# Force quoted-printable for the HTML part, like real MHT files use.
charset.add_charset("utf-8", charset.QP, charset.QP, "utf-8")

# ---------------------------------------------------------------------------
# Fake pages: (title, date, list of blocks). A block is either a string
# (a paragraph), ("ul", [items]) for a bullet list, or ("table", rows).
# ---------------------------------------------------------------------------
PAGES = [
    (
        "Deployment runbook - Orders API",
        "Monday, March 3, 2025",
        [
            "This page describes how we deploy the Orders API to the staging and production "
            "environments. The service runs on Azure App Service with two deployment slots, "
            "staging and production, and we swap slots instead of deploying straight to production.",
            "Before you start, make sure the release branch has passed the full CI pipeline, "
            "including the integration tests against the shared test database. If any test is "
            "flaky, rerun it once. If it fails twice, stop and raise it in the team channel.",
            ("ul", [
                "Check the release notes are written and linked from the ticket.",
                "Confirm the database migration script has been reviewed by a second developer.",
                "Tell the support team the planned deployment window at least one day ahead.",
                "Make sure someone from the on-call rota is available during the deployment.",
            ]),
            "Step one is to run the database migration against staging. The migrations are "
            "written to be backwards compatible, which means the old version of the code must "
            "still work after the migration runs. We never drop or rename a column in the same "
            "release that stops using it. Instead we stop using it first, then remove it in a "
            "later release once we are sure nothing reads it anymore.",
            "Step two is to deploy the build artifact to the staging slot. Use the release "
            "pipeline in Azure DevOps and pick the build number from the CI run you checked "
            "earlier. Do not rebuild from source at this point, because a rebuild can pick up "
            "a different version of a dependency and you would be deploying something nobody tested.",
            "Step three is the smoke test. Open the staging URL and run the smoke test "
            "collection. It creates a test order, reads it back, updates the delivery address "
            "and cancels it. All four calls should return success within two seconds. Also check "
            "Application Insights for any new exceptions in the last fifteen minutes.",
            "Step four is the slot swap. In the Azure portal, open the App Service, go to "
            "Deployment slots and choose Swap. Source is staging, target is production. The swap "
            "warms up the staging instances before routing traffic, so users should not notice "
            "anything. Watch the live metrics for at least ten minutes after the swap finishes.",
            "Rollback is the same operation in reverse: swap the slots again. Because the old "
            "version is still sitting in the staging slot after a swap, rolling back takes about "
            "a minute. This is the main reason we use slots. The database migration does not "
            "need to be rolled back because it is backwards compatible, as described above.",
            ("table", [
                ["Environment", "URL", "Owner"],
                ["Staging", "orders-staging.contoso.example", "Platform team"],
                ["Production", "orders.contoso.example", "Platform team"],
            ]),
            "Known issues: the first request after a swap sometimes takes four or five seconds "
            "because the connection pool to the database is cold. We have a ticket open to add "
            "a warm-up endpoint that the swap can call. Until that is done, it is fine to ignore "
            "a single slow request right after the swap, but anything longer is worth investigating.",
            "After the deployment, update the ticket with the build number and the time of the "
            "swap, post a short message in the release channel, and close the change request. "
            "If anything went wrong, even if it was fixed, write two or three lines in the "
            "deployment log page so the next person knows what to look out for.",
        ],
    ),
    (
        "Onboarding notes for new developers",
        "Tuesday, March 11, 2025",
        [
            "Welcome to the team. These notes cover the first week. Ask questions early; nobody "
            "expects you to know our systems yet, and most of our setup is not obvious.",
            ("ul", [
                "Day 1: laptop setup, accounts, and access to Azure DevOps and the Azure portal.",
                "Day 2: clone the main repositories and get the Orders API running locally.",
                "Day 3: pair with a teammate on a small bug fix and go through a code review.",
                "Day 4 and 5: pick up a starter ticket from the board, tagged good-first-issue.",
            ]),
            "Local development uses Docker Compose to run SQL Server and a fake payment provider. "
            "Run docker compose up from the repository root, then start the API from Visual "
            "Studio. The seed script creates ten test customers and a few hundred orders.",
            "Coding standards are in the wiki. The short version: write tests for new logic, keep "
            "pull requests small, and explain the why in the pull request description rather "
            "than the what, since the diff already shows the what.",
        ],
    ),
    (
        "Meeting notes - API versioning discussion",
        "Thursday, April 3, 2025",
        [
            "Attendees: Alex, Priya, Sam, Jordan. Goal: agree how we version public APIs before "
            "the mobile team starts using the Orders API directly.",
            "Options discussed were URL versioning (/v1/orders), a header (api-version), and "
            "query string versioning. Priya pointed out that Azure API Management supports all "
            "three, so tooling is not the deciding factor.",
            "Decision: use URL versioning for major versions only. Minor, backwards compatible "
            "changes do not get a new version. A major version stays supported for at least "
            "twelve months after the next one is released.",
            ("ul", [
                "Action: Sam to write the versioning guideline page in the wiki.",
                "Action: Jordan to add /v1 routes to the Orders API, keeping old routes as aliases.",
                "Action: Alex to tell the mobile team about the decision.",
            ]),
        ],
    ),
    (
        "Troubleshooting: payment webhook failures",
        "Wednesday, May 14, 2025",
        [
            "Symptom: orders stay in PendingPayment even though the customer was charged. This "
            "almost always means the payment provider's webhook did not reach us, or reached us "
            "and failed validation.",
            "First check the webhook log table for the order id. If there is no row, the call "
            "never arrived: check the provider dashboard for delivery errors and confirm the "
            "webhook URL has not changed. If there is a row with status Rejected, the signature "
            "check failed, which usually means the signing secret was rotated on one side only.",
            "To fix a single stuck order, use the admin tool's Reconcile button, which asks the "
            "provider for the payment status and updates the order. Do not edit the database "
            "row by hand, because that skips the events that trigger the confirmation email.",
        ],
    ),
    (
        "Ideas",
        "Friday, June 6, 2025",
        [
            "Short page on purpose, to test small pages.",
            ("ul", ["Cache product prices for 60 seconds.", "Add a dark mode to the admin tool."]),
        ],
    ),
]

# ---------------------------------------------------------------------------
# HTML helpers that imitate OneNote's inline-styled markup.
# ---------------------------------------------------------------------------
P_STYLE = "margin:0in;font-family:Calibri;font-size:11.0pt"


def block_to_html(block):
    if isinstance(block, str):
        return f"<p style='{P_STYLE}'>{html.escape(block)}</p>\n"
    kind, data = block
    if kind == "ul":
        items = "".join(
            f"<li style='margin-top:0;margin-bottom:0;vertical-align:middle'>"
            f"<span style='font-family:Calibri;font-size:11.0pt'>{html.escape(i)}</span></li>\n"
            for i in data
        )
        return f"<ul type=disc style='direction:ltr;unicode-bidi:embed;margin-top:0in;margin-bottom:0in'>\n{items}</ul>\n"
    if kind == "table":
        rows = ""
        for row in data:
            cells = "".join(
                f"<td style='border:solid #A3A3A3 1.0pt;vertical-align:top;width:1.6in;padding:2.0pt 3.0pt 2.0pt 3.0pt'>"
                f"<p style='{P_STYLE}'>{html.escape(c)}</p></td>"
                for c in row
            )
            rows += f"<tr>{cells}</tr>\n"
        return f"<table border=1 cellpadding=0 cellspacing=0 style='direction:ltr;border-collapse:collapse;border-style:solid;border-color:#A3A3A3;border-width:1pt'>\n{rows}</table>\n"
    raise ValueError(kind)


def page_to_html(title, date, blocks):
    body = "".join(block_to_html(b) for b in blocks)
    return f"""
<div style='direction:ltr;margin-top:0in;margin-left:0in;width:6.5in'>
<div style='direction:ltr;margin-top:0in;margin-left:0in;width:6.5in'>
<p style='margin:0in;font-family:"Calibri Light";font-size:20.0pt' lang=en-US>{html.escape(title)}</p>
</div>
<div style='direction:ltr;margin-top:.0423in;margin-left:0in;width:1.6416in'>
<p style='margin:0in;font-size:10.0pt;color:#767676'><span style='font-family:Calibri'>{date}</span></p>
<p style='margin:0in;font-size:10.0pt;color:#767676'><span style='font-family:Calibri'>9:30 AM</span></p>
</div>
<div style='direction:ltr;margin-top:.4in;margin-left:0in;width:6.5in'>
{body}</div>
</div>
<br clear=all style='page-break-before:always'>
"""


def build_html():
    pages = "".join(page_to_html(*p) for p in PAGES)
    return f"""<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:dt="uuid:C2F41010-65B3-11d1-A29F-00AA00C14882"
xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta http-equiv=Content-Type content="text/html; charset=utf-8">
<meta name=ProgId content=OneNote.File>
<meta name=Generator content="Microsoft OneNote 15">
<link id=Main-File rel=Main-File href="Engineering.htm">
<link rel=File-List href="Engineering_files/filelist.xml">
<title>Engineering</title>
</head>
<body lang=en-US style='font-family:Calibri;font-size:11.0pt'>
{pages}
<img width=48 height=48 src="Engineering_files/image001.png">
</body>
</html>
"""


# A tiny valid 1x1 PNG, so the MHT has an image part like a real export.
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def main():
    msg = MIMEMultipart("related", type="text/html")

    html_part = MIMEText(build_html(), "html", "utf-8")
    html_part["Content-Location"] = "file:///C:/Users/fake/Engineering.htm"
    msg.attach(html_part)

    img = MIMEImage(PNG_1X1, "png")
    img["Content-Location"] = "file:///C:/Users/fake/Engineering_files/image001.png"
    msg.attach(img)

    out = Path(__file__).with_name("fake_section.mht")
    out.write_bytes(msg.as_bytes())
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
