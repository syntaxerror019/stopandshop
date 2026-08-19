import traceback
import resend
import time

from worker.processed import load_processed, save_processed
from worker.processor import process_email
from worker.email import send_reply

ERROR_HTML = """
<p>
    I received your email, but there was
    a problem processing the schedule.
</p>
<p><strong>Problem:</strong></p>
<blockquote>{error_message}</blockquote>
<p><strong>How to fix it:</strong></p>
<p>
    Please correct the issue described above
    and send the schedule email again.
</p>
<p>
    If you believe this error is incorrect,
    please contact the system administrator.
</p>
<hr>
<p><small>Email ID: {email_id}</small></p>
"""


def main():
    print("\n" + "=" * 60)
    print("Checking Resend inbox...")
    print("=" * 60)

    processed = load_processed()
    print(f"Previously processed emails: {len(processed)}")

    try:
        emails = resend.Emails.Receiving.list().get("data", [])
    except Exception:
        print("\nERROR: Could not retrieve emails.")
        traceback.print_exc()
        return

    print(f"Emails returned by Resend: {len(emails)}")

    for email in emails:
        email_id = email["id"]

        if email_id in processed:
            print(f"Skipping already processed email: {email_id}")
            continue

        try:
            process_email(email)
            processed.add(email_id)
            save_processed(processed)
            print(f"Marked {email_id} as processed.")

        except Exception as e:
            print(f"\nERROR processing email {email_id}")
            traceback.print_exc()

            try:
                send_reply(
                    email,
                    "Problem processing your schedule",
                    ERROR_HTML.format(error_message=str(e), email_id=email_id),
                )
                print("Error notification sent.")
            except Exception:
                print("ERROR: Could not send error notification.")
                traceback.print_exc()

            processed.add(email_id)
            save_processed(processed)


if __name__ == "__main__":
    while True:
        main()
        time.sleep(5)
