import shutil

from worker.config import WHITELIST, UPLOAD_DIR
from worker.email import send_reply
from worker.attachments import download_attachment
from tools.pdf_eval import extract_schedule_period

SCHEDULE_MAP = {
    "this_week": "current.pdf",
    "next_week": "next_week.pdf",
}


def normalize_email(address):
    return address.strip().lower()


def process_email(email):
    """
    Process one incoming email.

    Returns True if successfully processed.
    Returns False if intentionally rejected.
    """

    email_id = email["id"]
    sender = normalize_email(email["from"])
    subject = email.get("subject", "(no subject)")

    print()
    print("=" * 60)
    print(f"Email ID: {email_id}")
    print(f"From:    {sender}")
    print(f"Subject: {subject}")
    print("=" * 60)

    # ========================================================
    # WHITELIST
    # ========================================================

    if sender not in WHITELIST:
        print(f"Rejected email from unauthorized sender: {sender}")
        return False

    print("Sender is authorized.")

    # ========================================================
    # FIND ATTACHMENTS
    # ========================================================

    attachments = email.get("attachments", [])

    if not attachments:
        raise ValueError(
            "No attachments were found.\n\n"
            "Please attach the schedule as a PDF and "
            "send another email."
        )

    print(f"Found {len(attachments)} attachment(s).")

    # ========================================================
    # FIND PDF ATTACHMENTS
    # ========================================================

    pdf_attachments = [
        a for a in attachments
        if a.get("content_type", "").lower() == "application/pdf"
        or a.get("filename", "").lower().endswith(".pdf")
    ]

    if len(pdf_attachments) == 0:
        raise ValueError(
            "No PDF attachment was found.\n\n"
            "Please make sure the schedule is attached "
            "as a PDF file and send another email."
        )

    if len(pdf_attachments) > 1:
        names = [a.get("filename", "(unnamed PDF)") for a in pdf_attachments]
        raise ValueError(
            "Multiple PDF attachments were found:\n\n"
            + "\n".join(f"- {n}" for n in names)
            + "\n\nPlease send exactly one schedule PDF."
        )

    attachment = pdf_attachments[0]
    print(f"Using PDF: {attachment.get('filename')}")

    # ========================================================
    # DOWNLOAD PDF
    # ========================================================

    saved_path = download_attachment(email, attachment)

    # ========================================================
    # VALIDATE SCHEDULE
    # ========================================================

    result = extract_schedule_period(saved_path)

    period = result["period"]
    confidence = result["confidence"]
    needs_review = result["needs_review"]

    print(f"Period:     {period}")
    print(f"Confidence: {confidence}")
    print(f"Reason:     {result['reason']}")

    if needs_review:
        raise ValueError(
            f"The schedule could not be automatically classified.\n\n"
            f"Period: {period}\n"
            f"Confidence: {confidence}\n"
            f"Reason: {result['reason']}\n\n"
            f"Please verify the dates in the PDF and try again."
        )

    if period == "unknown":
        raise ValueError(
            "Could not determine whether this is a current or "
            "next week schedule.\n\n"
            f"Reason: {result['reason']}\n\n"
            "Please verify the dates and send again."
        )

    # ========================================================
    # SAVE TO UPLOADS
    # ========================================================

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    dest_filename = SCHEDULE_MAP[period]
    dest_path = UPLOAD_DIR / dest_filename

    shutil.copy2(saved_path, dest_path)

    print(f"Saved schedule to {dest_path}")

    # ========================================================
    # SUCCESS EMAIL
    # ========================================================

    start_str = result["start"].strftime("%A %m/%d/%Y")
    end_str = result["end"].strftime("%A %m/%d/%Y")

    period_label = "current week" if period == "this_week" else "next week"

    send_reply(
        email,
        "Schedule received successfully",
        f"""
        <p>
            Your schedule PDF was received and validated successfully.
        </p>

        <p>
            <strong>Period:</strong> {period_label}
            <br>
            <strong>Dates:</strong> {start_str} – {end_str}
            <br>
            <strong>Confidence:</strong> {confidence:.0%}
            <br>
            <strong>Saved as:</strong> {dest_filename}
        </p>

        <p>
            If this is incorrect, please contact the
            system administrator.
        </p>
        """
    )

    print("Success confirmation sent.")
    return True
