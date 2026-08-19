import re
from datetime import date, timedelta
from pathlib import Path

import pdfplumber


DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def extract_schedule_period(pdf_path, today=None):
    """
    Extract and classify a Stop & Shop wall schedule.

    Returns:
        {
            "period": "this_week" | "next_week" | "unknown",
            "confidence": 0.0 - 1.0,
            "needs_review": True | False,
            "reason": "...",

            "start": date(...) | None,
            "end": date(...) | None,
            "dates": [...]
        }

    `today` can be supplied for testing. If omitted, date.today()
    is used.
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    if today is None:
        today = date.today()

    # =========================================================
    # 1. Extract PDF text
    # =========================================================

    text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += "\n" + (page.extract_text() or "")

    # =========================================================
    # 2. Extract dates
    # =========================================================

    found_dates = []

    for month, day, year in DATE_RE.findall(text):
        try:
            d = date(int(year), int(month), int(day))
            found_dates.append(d)
        except ValueError:
            # Invalid dates are ignored
            pass

    # Remove duplicates while preserving order
    dates = list(dict.fromkeys(found_dates))

    if not dates:
        raise ValueError("No valid dates found in PDF.")

    # =========================================================
    # 3. Find an 8-day consecutive sequence
    # =========================================================

    sequences = []

    for i in range(len(dates) - 7):

        candidate = dates[i:i + 8]

        if all(
            candidate[j] == candidate[0] + timedelta(days=j)
            for j in range(8)
        ):
            sequences.append(candidate)

    if not sequences:
        raise ValueError(
            "Could not find an 8-day consecutive schedule period."
        )

    # Usually there will only be one.
    # If there are multiple, use the first one for now.
    sequence = sequences[0]

    # =========================================================
    # 4. Validate the sequence
    # =========================================================

    first_date = sequence[0]
    last_date = sequence[-1]

    # The wall schedule should begin with an unused Saturday.
    first_is_saturday = first_date.weekday() == 5

    # The actual schedule should be Sunday -> Saturday.
    actual_schedule = sequence[1:]

    start = actual_schedule[0]
    end = actual_schedule[-1]

    actual_is_sunday_to_saturday = (
        start.weekday() == 6 and
        end.weekday() == 5 and
        (end - start).days == 6
    )

    # =========================================================
    # 5. Determine expected weeks
    # =========================================================

    # Python weekday:
    #
    # Monday = 0
    # Tuesday = 1
    # ...
    # Saturday = 5
    # Sunday = 6

    current_week_sunday = today - timedelta(
        days=(today.weekday() + 1) % 7
    )

    next_week_sunday = current_week_sunday + timedelta(days=7)

    current_week_end = current_week_sunday + timedelta(days=6)
    next_week_end = next_week_sunday + timedelta(days=6)

    this_week_dates = [
        current_week_sunday + timedelta(days=i)
        for i in range(7)
    ]

    next_week_dates = [
        next_week_sunday + timedelta(days=i)
        for i in range(7)
    ]

    # =========================================================
    # 6. Compare schedule against expected weeks
    # =========================================================

    if actual_schedule == this_week_dates:

        period = "this_week"
        confidence = 1.00
        reason = (
            "Schedule exactly matches the current Sunday-Saturday week."
        )

    elif actual_schedule == next_week_dates:

        period = "next_week"
        confidence = 1.00
        reason = (
            "Schedule exactly matches the next Sunday-Saturday week."
        )

    else:

        # How far is the schedule from each expected week?
        this_distance = abs(
            (start - current_week_sunday).days
        )

        next_distance = abs(
            (start - next_week_sunday).days
        )

        if this_distance < next_distance:
            period = "this_week"
            distance = this_distance
            expected_start = current_week_sunday

        elif next_distance < this_distance:
            period = "next_week"
            distance = next_distance
            expected_start = next_week_sunday

        else:
            period = "unknown"
            distance = this_distance
            expected_start = None

        # -----------------------------------------------------
        # Calculate confidence
        # -----------------------------------------------------

        # Start at a fairly high confidence.
        confidence = 0.80

        # Exact Sunday start is important.
        if start.weekday() == 6:
            confidence += 0.10
        else:
            confidence -= 0.20

        # Exact Saturday end is important.
        if end.weekday() == 5:
            confidence += 0.05
        else:
            confidence -= 0.10

        # Correct 7-day schedule length.
        if (end - start).days == 6:
            confidence += 0.05
        else:
            confidence -= 0.15

        # Penalize distance from expected week.
        confidence -= min(distance * 0.10, 0.50)

        confidence = max(0.0, min(1.0, confidence))

        if period == "unknown":
            reason = (
                "Schedule is equally distant from the current and "
                "next schedule week."
            )
        elif distance == 0:
            reason = (
                f"Schedule starts exactly on the expected "
                f"{period.replace('_', ' ')} Sunday."
            )
        else:
            reason = (
                f"Schedule is {distance} day(s) away from the "
                f"expected {period.replace('_', ' ')} Sunday."
            )

    # =========================================================
    # 7. Apply structural confidence adjustments
    # =========================================================

    if not first_is_saturday:
        confidence_adjustment = -0.20
    else:
        confidence_adjustment = 0.0

    if not actual_is_sunday_to_saturday:
        confidence_adjustment -= 0.15

    confidence = max(
        0.0,
        min(1.0, confidence + confidence_adjustment)
    )

    # If the structural validation failed badly,
    # don't pretend we're certain.
    if not first_is_saturday or not actual_is_sunday_to_saturday:
        period = "unknown" if confidence < 0.60 else period

    # =========================================================
    # 8. Manual-review threshold
    # =========================================================

    needs_review = (
        confidence < 0.80 or
        period == "unknown"
    )

    # =========================================================
    # 9. Add structural information to reason
    # =========================================================

    if first_is_saturday:
        reason += " The first unused header date is a Saturday."
    else:
        reason += " WARNING: first header date is not a Saturday."

    if actual_is_sunday_to_saturday:
        reason += " The schedule covers Sunday through Saturday."
    else:
        reason += (
            " WARNING: schedule does not cleanly cover "
            "Sunday through Saturday."
        )

    return {
        "period": period,
        "confidence": round(confidence, 3),
        "needs_review": needs_review,
        "reason": reason,

        "start": start,
        "end": end,
        "dates": actual_schedule,

        # Useful debugging information
        "header_start": first_date,
        "header_end": last_date,
        "current_week_start": current_week_sunday,
        "current_week_end": current_week_end,
        "next_week_start": next_week_sunday,
        "next_week_end": next_week_end,
    }


# =============================================================
# Example
# =============================================================

if __name__ == "__main__":

    result = extract_schedule_period(
        "../uploads/current.pdf"
    )

    print("\n==============================")
    print("       SCHEDULE RESULT")
    print("==============================")

    print("Period:       ", result["period"])
    print("Confidence:   ", result["confidence"])
    print("Needs review: ", result["needs_review"])
    print("Reason:        ", result["reason"])

    print("\nSchedule:")
    print(
        result["start"].strftime("%A %m/%d/%Y"),
        "->",
        result["end"].strftime("%A %m/%d/%Y")
    )

    print("\nDays:")

    for d in result["dates"]:
        print(" ", d.strftime("%A %m/%d/%Y"))