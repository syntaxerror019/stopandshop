import re
from datetime import date, timedelta
from pathlib import Path

import pdfplumber


DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def extract_schedule_period(pdf_path):
    """
    Extract the actual schedule period from a Stop & Shop Wall Schedule PDF.

    The PDF has an 8-date header:
        Saturday  - ignored
        Sunday    - first actual schedule day
        Monday
        Tuesday
        Wednesday
        Thursday
        Friday
        Saturday  - last actual schedule day

    Returns:
        {
            "start": date(...),
            "end": date(...),
            "dates": [...]
        }

    Raises:
        ValueError if a valid schedule period cannot be found.
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # Extract all text from the PDF
    text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += "\n" + page_text

    # Find every date appearing in the document
    found_dates = []

    for month, day, year in DATE_RE.findall(text):
        try:
            d = date(int(year), int(month), int(day))
            found_dates.append(d)
        except ValueError:
            # Ignore impossible dates
            pass

    # Remove duplicates while preserving order
    dates = list(dict.fromkeys(found_dates))

    # Look for a consecutive 8-day sequence.
    #
    # The first day is the unused Saturday.
    for i in range(len(dates) - 7):
        sequence = dates[i:i + 8]

        if all(
            sequence[j] == sequence[0] + timedelta(days=j)
            for j in range(8)
        ):
            # Ignore the first Saturday.
            actual_schedule = sequence[1:]

            return {
                "start": actual_schedule[0],
                "end": actual_schedule[-1],
                "dates": actual_schedule,
            }

    raise ValueError(
        "Could not find an 8-day consecutive schedule period in the PDF."
    )


if __name__ == "__main__":
    result = extract_schedule_period("../uploads/current.pdf")

    print("Schedule found!")
    print("Start:", result["start"])
    print("End:  ", result["end"])

    print("\nActual schedule days:")
    for d in result["dates"]:
        print(" ", d.strftime("%A %m/%d/%Y"))