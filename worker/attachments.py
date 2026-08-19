from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

import resend
from worker.config import SAVE_DIRECTORY


def download_attachment(email, attachment):
    """
    Retrieve an attachment from Resend and save it locally.

    Example resulting filename:

        2026-08-19_153607_wall schedule.pdf
    """

    email_id = email["id"]
    attachment_id = attachment["id"]

    print(f"Retrieving attachment {attachment_id}...")

    # --------------------------------------------------------
    # GET ATTACHMENT INFORMATION
    # --------------------------------------------------------

    result = resend.Emails.Receiving.Attachments.get(
        email_id=email_id,
        attachment_id=attachment_id,
    )

    download_url = result["download_url"]

    # --------------------------------------------------------
    # SANITIZE ORIGINAL FILENAME
    # --------------------------------------------------------

    # Path(...).name prevents filenames such as:
    #
    # ../../something.pdf
    #
    # from escaping our directory.

    original_filename = Path(
        result["filename"]
    ).name

    if not original_filename:
        raise ValueError(
            "The PDF attachment did not have a valid filename."
        )

    # --------------------------------------------------------
    # GET EMAIL TIMESTAMP
    # --------------------------------------------------------

    created_at = email.get("created_at")

    if created_at:

        timestamp = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        ).astimezone().strftime(
            "%Y-%m-%d_%H%M%S"
        )

    else:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H%M%S"
        )

    # --------------------------------------------------------
    # CREATE DIRECTORY
    # --------------------------------------------------------

    SAVE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # CREATE UNIQUE FILENAME
    # --------------------------------------------------------

    filename = (
        f"{timestamp}_{original_filename}"
    )

    destination = SAVE_DIRECTORY / filename

    # If two emails arrive during the same second,
    # prevent overwriting the first one.

    if destination.exists():

        destination = (
            SAVE_DIRECTORY
            / f"{timestamp}_{email_id}_{original_filename}"
        )

    # --------------------------------------------------------
    # DOWNLOAD FILE
    # --------------------------------------------------------

    print(f"Downloading {original_filename}...")

    with urlopen(download_url) as response:

        data = response.read()

    if not data:
        raise ValueError(
            "The attachment download returned an empty file."
        )

    # --------------------------------------------------------
    # SAVE FILE
    # --------------------------------------------------------

    with open(destination, "wb") as f:

        f.write(data)

    print(
        f"Saved attachment to {destination}"
    )

    return destination
