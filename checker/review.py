import argparse
import csv
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = BASE_DIR / "results" / "ai_diagnoses.csv"
REVIEW_FILE = BASE_DIR / "results" / "responsible_ai_log.csv"


def load_diagnosis(case_id):
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["case_id"] == case_id:
                return row
    return None


def review_case(case_id):

    diagnosis = load_diagnosis(case_id)

    if not diagnosis:
        print(f"Case {case_id} not found.")
        return

    print("=" * 70)
    print("                    NETSAGE HUMAN REVIEW")
    print("=" * 70)

    print(f"\nCASE: {case_id}")

    print("\nAI ROOT CAUSE:")
    print(diagnosis["root_cause"])

    print("\nCONFIDENCE:")
    print(diagnosis["confidence"])

    print("\nOSI LAYER:")
    print(diagnosis["osi_layer"])

    print("\nEVIDENCE:")
    for item in diagnosis["evidence"].split(" | "):
        print(f"  - {item}")

    print("\nNEXT COMMAND:")
    print(diagnosis["next_command"])

    print("\nFIX STEPS:")
    for i, step in enumerate(
        diagnosis["fix_steps"].split(" | "),
        1
    ):
        print(f"  {i}. {step}")

    print("\n" + "-" * 70)
    print("HUMAN DECISION")
    print("-" * 70)

    while True:
        decision = input(
            "\n[A] Accept  [E] Edit  [R] Reject: "
        ).strip().upper()

        if decision in ("A", "E", "R"):
            break

        print("Please enter A, E, or R.")

    if decision == "A":

        human_correction = ""
        reason = input(
            "Optional review comment: "
        ).strip()

        status = "ACCEPTED"

    elif decision == "E":

        print("\nEnter the human correction.")
        human_correction = input(
            "Correction: "
        ).strip()

        reason = input(
            "Reason for edit: "
        ).strip()

        status = "EDITED"

    else:

        human_correction = input(
            "Why is the diagnosis rejected? "
        ).strip()

        reason = human_correction
        status = "REJECTED"

    # -----------------------------------------------------
    # SAVE REVIEW
    # -----------------------------------------------------

    file_exists = REVIEW_FILE.exists()

    with open(
        REVIEW_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        fieldnames = [
            "timestamp",
            "case_id",
            "ai_root_cause",
            "ai_confidence",
            "decision",
            "human_correction",
            "reason"
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),
            "case_id":
                case_id,
            "ai_root_cause":
                diagnosis["root_cause"],
            "ai_confidence":
                diagnosis["confidence"],
            "decision":
                status,
            "human_correction":
                human_correction,
            "reason":
                reason
        })

    print("\n" + "=" * 70)
    print("                 REVIEW SAVED")
    print("=" * 70)

    print(f"Case:     {case_id}")
    print(f"Decision: {status}")
    print(f"Saved to: {REVIEW_FILE}")

    print("=" * 70)


def main():

    parser = argparse.ArgumentParser(
        description="NetSage Human Review"
    )

    parser.add_argument(
        "--case",
        required=True,
        help="Case ID, e.g. 005"
    )

    args = parser.parse_args()

    case_id = args.case.strip().zfill(3)

    review_case(case_id)


if __name__ == "__main__":
    main()