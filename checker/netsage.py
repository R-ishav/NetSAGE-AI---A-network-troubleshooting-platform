import argparse
import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel

from checker import analyze_case


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CASES_FILE = BASE_DIR / "data" / "cases.csv"
RESULTS_DIR = BASE_DIR / "results"
OUTPUT_FILE = RESULTS_DIR / "ai_diagnoses.csv"


# =========================================================
# AI OUTPUT SCHEMA
# =========================================================

class Diagnosis(BaseModel):
    case_id: str
    root_cause: str
    confidence: float
    osi_layer: str
    evidence: list[str]
    next_command: str
    fix_steps: list[str]
    human_review_required: bool


# =========================================================
# GROQ CLIENT
# =========================================================

load_dotenv()


def get_groq_client():
    """Create the Groq client only when an analysis is requested."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Set it in the environment "
            "or in a local .env file."
        )

    return Groq(api_key=api_key)


# =========================================================
# AI SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are NetSage AI, an AI-assisted Cisco network
troubleshooting assistant.

Analyze the supplied network case using ONLY the
provided evidence.

Your task is to identify the most likely root cause
and provide an explainable troubleshooting recommendation.

IMPORTANT RULES:

1. Do not invent evidence.
2. Use the supplied network evidence as the primary source.
3. Treat Python rule-checker findings as supporting evidence.
4. Do not blindly trust the Python checker.
5. confidence MUST be a number from 0.0 to 1.0.
6. evidence MUST be an array of specific evidence strings.
7. next_command MUST contain ONE useful, non-empty
   troubleshooting command.
8. fix_steps MUST be an ordered array of practical steps.
9. human_review_required MUST always be true.
10. Do not claim that a fix has already been applied.
11. If evidence is insufficient, lower the confidence.
12. Return ONLY the required JSON object.
"""


# =========================================================
# LOAD CASES
# =========================================================

def load_cases():

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"Cases file not found:\n{CASES_FILE}"
        )

    with open(
        CASES_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return list(csv.DictReader(file))


# =========================================================
# LOAD SAVED RESULTS
# =========================================================

def load_existing_results():

    if not OUTPUT_FILE.exists():
        return {}

    existing = {}

    with open(
        OUTPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            evidence_text = (
                row.get("evidence", "")
                .strip()
            )

            fix_steps_text = (
                row.get("fix_steps", "")
                .strip()
            )

            evidence = []

            if evidence_text:
                evidence = [
                    item.strip()
                    for item in evidence_text.split(" | ")
                    if item.strip()
                ]

            fix_steps = []

            if fix_steps_text:
                fix_steps = [
                    item.strip()
                    for item in fix_steps_text.split(" | ")
                    if item.strip()
                ]

            try:
                confidence = float(
                    row.get("confidence", 0)
                )
            except (ValueError, TypeError):
                confidence = 0.0

            human_review = (
                row.get(
                    "human_review_required",
                    "True"
                ).strip().lower()
                == "true"
            )

            existing[row["case_id"]] = {
                "case_id": row["case_id"],
                "root_cause": row.get(
                    "root_cause",
                    ""
                ),
                "confidence": confidence,
                "osi_layer": row.get(
                    "osi_layer",
                    ""
                ),
                "evidence": evidence,
                "next_command": row.get(
                    "next_command",
                    ""
                ),
                "fix_steps": fix_steps,
                "human_review_required":
                    human_review
            }

    return existing

# =========================================================
# BUILD AI PROMPT
# =========================================================

def build_prompt(case, checker_findings):

    return f"""
CASE ID:
{case["case_id"]}

SYMPTOM:
{case["symptom"]}

TOPOLOGY:
{case["topology"]}

NETWORK EVIDENCE:
{case["show_outputs"]}

PYTHON RULE CHECKER FINDINGS:
{json.dumps(checker_findings)}

Analyze this case and produce the required diagnosis.
"""


# =========================================================
# SAVE RESULTS
# =========================================================

def save_results(results):

    RESULTS_DIR.mkdir(exist_ok=True)

    fieldnames = [
        "case_id",
        "root_cause",
        "confidence",
        "osi_layer",
        "evidence",
        "next_command",
        "fix_steps",
        "human_review_required"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for result in results:

            evidence = result.get("evidence", [])
            fix_steps = result.get("fix_steps", [])

            # Make sure these are lists before saving.
            # This prevents character-by-character saving.

            if isinstance(evidence, str):
                evidence = [evidence]

            if isinstance(fix_steps, str):
                fix_steps = [fix_steps]

            writer.writerow({
                "case_id": result.get("case_id", ""),
                "root_cause": result.get("root_cause", ""),
                "confidence": result.get("confidence", 0),
                "osi_layer": result.get("osi_layer", ""),
                "evidence": " | ".join(evidence),
                "next_command": result.get("next_command", ""),
                "fix_steps": " | ".join(fix_steps),
                "human_review_required":
                    result.get(
                        "human_review_required",
                        True
                    )
            })


# =========================================================
# GROQ AI CALL
# =========================================================

def ask_groq(case, checker_findings):

    prompt = build_prompt(
        case,
        checker_findings
    )

    client = get_groq_client()

    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0,

        reasoning_effort="low",

        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "netsage_diagnosis",

                "strict": True,

                "schema": {
                    "type": "object",

                    "properties": {

                        "case_id": {
                            "type": "string"
                        },

                        "root_cause": {
                            "type": "string"
                        },

                        "confidence": {
                            "type": "number"
                        },

                        "osi_layer": {
                            "type": "string"
                        },

                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },

                        "next_command": {
                            "type": "string"
                        },

                        "fix_steps": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },

                        "human_review_required": {
                            "type": "boolean"
                        }
                    },

                    "required": [
                        "case_id",
                        "root_cause",
                        "confidence",
                        "osi_layer",
                        "evidence",
                        "next_command",
                        "fix_steps",
                        "human_review_required"
                    ],

                    "additionalProperties": False
                }
            }
        }
    )

    raw = response.choices[0].message.content

    if not raw:
        raise ValueError(
            "Groq returned an empty response."
        )

    diagnosis = Diagnosis.model_validate_json(
        raw
    )

    # Additional validation

    if not 0 <= diagnosis.confidence <= 1:
        raise ValueError(
            "Confidence must be between 0 and 1."
        )

    if not diagnosis.next_command.strip():
        raise ValueError(
            "AI returned an empty next_command."
        )

    if diagnosis.human_review_required is not True:
        raise ValueError(
            "human_review_required must be true."
        )

    if not diagnosis.evidence:
        raise ValueError(
            "AI returned no evidence."
        )

    if not diagnosis.fix_steps:
        raise ValueError(
            "AI returned no fix steps."
        )

    return diagnosis


# =========================================================
# DISPLAY SAVED DIAGNOSIS
# =========================================================
def display_diagnosis(result):

    print("\n" + "=" * 70)
    print(
        f"                 CASE {result['case_id']} "
        f"AI DIAGNOSIS"
    )
    print("=" * 70)

    print("\nROOT CAUSE:")
    print(result["root_cause"])

    print("\nCONFIDENCE:")
    print(result["confidence"])

    print("\nOSI LAYER:")
    print(result["osi_layer"])

    # -----------------------------------------------------
    # EVIDENCE
    # -----------------------------------------------------

    print("\nEVIDENCE:")

    evidence = result.get("evidence", [])

    # If loaded from CSV as one string,
    # convert it back into a list.

    if isinstance(evidence, str):

        evidence = [
            item.strip()
            for item in evidence.split(" | ")
            if item.strip()
        ]

    for item in evidence:
        print(f"  - {item}")

    # -----------------------------------------------------
    # NEXT COMMAND
    # -----------------------------------------------------

    print("\nNEXT COMMAND:")
    print(result["next_command"])

    # -----------------------------------------------------
    # FIX STEPS
    # -----------------------------------------------------

    print("\nFIX STEPS:")

    fix_steps = result.get("fix_steps", [])

    # If loaded from CSV as one string,
    # convert it back into a list.

    if isinstance(fix_steps, str):

        fix_steps = [
            item.strip()
            for item in fix_steps.split(" | ")
            if item.strip()
        ]

    for index, step in enumerate(
        fix_steps,
        start=1
    ):
        print(f"  {index}. {step}")

    # -----------------------------------------------------
    # HUMAN REVIEW
    # -----------------------------------------------------

    print("\nHUMAN REVIEW REQUIRED:")
    print(
        str(
            result["human_review_required"]
        ).upper()
    )

    print("=" * 70)

# =========================================================
# RUN ONE NEW AI ANALYSIS
# =========================================================

def analyze_single_case(
    case,
    existing_results,
    all_results,
    force=False
):

    case_id = case["case_id"]

    # -----------------------------------------------------
    # EXISTING RESULT
    # -----------------------------------------------------

    if case_id in existing_results and not force:

        print(
            f"\nCase {case_id} already has a saved diagnosis."
        )

        print(
            "No API call made."
        )

        display_diagnosis(
            existing_results[case_id]
        )

        return existing_results[case_id]

    try:
        get_groq_client()
    except RuntimeError as error:
        print(f"Configuration error: {error}")
        return None


    # -----------------------------------------------------
    # PYTHON CHECKER
    # -----------------------------------------------------

    print(
        f"\nAnalyzing Case {case_id}..."
    )

    try:

        checker_findings = analyze_case(
            case
        )

    except Exception as error:

        print(
            f"Python checker error: {error}"
        )

        checker_findings = []


    print("\nPYTHON FINDINGS:")

    if checker_findings:

        for finding in checker_findings:
            print(
                f"  - {finding}"
            )

    else:

        print(
            "  - No deterministic issue detected"
        )


    # -----------------------------------------------------
    # GROQ
    # -----------------------------------------------------

    max_retries = 5

    diagnosis = None

    for attempt in range(
        1,
        max_retries + 1
    ):

        try:

            print(
                f"\nSending to Groq "
                f"(attempt {attempt}/{max_retries})..."
            )

            diagnosis = ask_groq(
                case,
                checker_findings
            )

            break

        except Exception as error:

            error_text = str(error)

            print(
                f"API error: {error_text}"
            )

            # 401 = invalid authentication.
            # Retrying cannot fix an invalid key.

            if (
                "401" in error_text
                or
                "invalid_api_key"
                in error_text.lower()
                or
                "invalid api key"
                in error_text.lower()
            ):

                print(
                    "\nFATAL: Groq API key was rejected."
                )

                print(
                    "Check GROQ_API_KEY and try again."
                )

                return None


            # Rate limit

            if (
                "429" in error_text
                or
                "rate limit"
                in error_text.lower()
                or
                "too many requests"
                in error_text.lower()
            ):

                wait_time = min(
                    20 * attempt,
                    60
                )

            else:

                wait_time = 5 * attempt


            print(
                f"Retrying in {wait_time} seconds..."
            )

            time.sleep(
                wait_time
            )


    # -----------------------------------------------------
    # FAILED
    # -----------------------------------------------------

    if diagnosis is None:

        print(
            f"\nCase {case_id} FAILED."
        )

        return None


    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    result = diagnosis.model_dump()

    # If rerunning, replace old result.

    all_results = [
        r
        for r in all_results
        if r["case_id"] != case_id
    ]

    all_results.append(
        result
    )

    save_results(
        all_results
    )

    existing_results[case_id] = result

    print("\nAI DIAGNOSIS:")

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    print(
        "\nResult saved."
    )

    return result


# =========================================================
# PARSE CASE IDS
# =========================================================

def parse_case_ids(value):

    ids = []

    for item in value.split(","):

        item = item.strip()

        if not item:
            continue

        # Preserve case IDs such as 001, 005, 031
        if item.isdigit():
            item = item.zfill(3)

        ids.append(item)

    if not ids:
        raise ValueError(
            "No case IDs supplied."
        )

    return ids
# =========================================================
# MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="NetSage AI Network Troubleshooting Assistant"
    )

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--case",
        help=(
            "Show/analyze specific case(s). "
            "Example: --case 001 or --case 001,015,023"
        )
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="Process all cases."
    )

    group.add_argument(
        "--view",
        help="View a saved diagnosis without using the API."
    )

    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Force a fresh AI analysis instead of using saved results."
    )

    args = parser.parse_args()


    # =====================================================
    # HEADER
    # =====================================================

    print("=" * 70)
    print("                       NETSAGE AI")
    print("=" * 70)


    # =====================================================
    # LOAD DATA
    # =====================================================

    cases = load_cases()

    cases_by_id = {
        case["case_id"]: case
        for case in cases
    }

    existing_results = load_existing_results()

    all_results = list(
        existing_results.values()
    )


    # =====================================================
    # VIEW
    # =====================================================

    if args.view:

        case_id = args.view.strip()

        if case_id not in existing_results:

            print(
                f"\nNo saved diagnosis found for Case {case_id}."
            )

            print(
                "Run the case first with:"
            )

            print(
                f"  py netsage.py --case {case_id}"
            )

            return

        print(
            f"\nShowing saved result for Case {case_id}"
        )

        print(
            "No API call made."
        )

        display_diagnosis(
            existing_results[case_id]
        )

        return


    # =====================================================
    # SPECIFIC CASE(S)
    # =====================================================

    if args.case:

        try:

            case_ids = parse_case_ids(
                args.case
            )

        except ValueError as error:

            print(
                f"\nError: {error}"
            )

            return


        for case_id in case_ids:

            if case_id not in cases_by_id:

                print(
                    f"\nCase {case_id} does not exist."
                )

                continue


            analyze_single_case(
                cases_by_id[case_id],
                existing_results,
                all_results,
                force=args.rerun
            )

            # Refresh after each case.

            existing_results = (
                load_existing_results()
            )

            all_results = list(
                existing_results.values()
            )

        return


    # =====================================================
    # ALL CASES
    # =====================================================

    if args.all:

        print(
            f"\nTotal cases loaded: {len(cases)}"
        )

        print(
            f"Saved results available: "
            f"{len(existing_results)}"
        )

        successful = 0
        failed = 0

        for index, case in enumerate(
            cases,
            start=1
        ):

            case_id = case["case_id"]

            print(
                f"\n[{index}/{len(cases)}] "
                f"Case {case_id}"
            )

            result = analyze_single_case(
                case,
                existing_results,
                all_results,
                force=args.rerun
            )

            if result is None:

                failed += 1

            else:

                successful += 1

            # Refresh saved results.

            existing_results = (
                load_existing_results()
            )

            all_results = list(
                existing_results.values()
            )

            time.sleep(2)


        print(
            "\n" + "=" * 70
        )

        print(
            "                    PROCESSING COMPLETE"
        )

        print(
            "=" * 70
        )

        print(
            f"Successful: {successful}"
        )

        print(
            f"Failed:     {failed}"
        )

        print(
            f"Total:      {len(cases)}"
        )

        print(
            f"\nResults saved to:"
        )

        print(
            OUTPUT_FILE
        )

        print(
            "=" * 70
        )


if __name__ == "__main__":
    main()