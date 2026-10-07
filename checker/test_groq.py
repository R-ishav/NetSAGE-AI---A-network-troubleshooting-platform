import json
import os

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError


class Diagnosis(BaseModel):
    case_id: str
    root_cause: str
    confidence: float
    osi_layer: str
    evidence: list[str]
    next_command: str
    fix_steps: list[str]
    human_review_required: bool


def main():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise SystemExit(
            "GROQ_API_KEY is not configured. Set it before running this smoke test."
        )

    print("Starting Groq strict schema test...")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "system",
            "content": """
You are NetSage AI, an AI-assisted network
troubleshooting system.

Analyze the supplied network evidence.

Return a diagnosis using the exact required schema.

Rules:
- confidence MUST be a number between 0 and 1.
- evidence MUST be an array of strings.
- fix_steps MUST be an array of strings.
- human_review_required MUST always be true.
- Do not invent evidence.
- Return ONLY JSON.
"""
        },
        {
            "role": "user",
            "content": """
Case ID: 001

Symptom:
PC-01 cannot communicate with the network.

Topology:
PC-01 -> Switch -> R1

Evidence:
PC-01 IP: 192.168.10.20
Subnet mask: 255.255.255.0
Default gateway: 192.168.20.1

R1 G0/0:
IP: 192.168.10.1
Status: up/up

Python finding:
Gateway mismatch detected.
"""
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

    print("\n========== RAW RESPONSE ==========")
    print(raw)

    print("\n========== PYDANTIC VALIDATION ==========")

    try:
        diagnosis = Diagnosis.model_validate_json(raw)

        print("Schema validation PASSED!")

        print("\n========== PARSED DIAGNOSIS ==========")
        print(json.dumps(
            diagnosis.model_dump(),
            indent=2
        ))

        if not 0 <= diagnosis.confidence <= 1:
            raise ValueError(
                "Confidence is outside 0-1 range."
            )

        if diagnosis.human_review_required is not True:
            raise ValueError(
                "human_review_required must be true."
            )

        print("\n======================================")
        print("       GROQ NETSAGE TEST PASSED")
        print("======================================")

    except (ValidationError, ValueError, json.JSONDecodeError) as e:

        print("\nSCHEMA TEST FAILED")
        print(e)


    print("\n========== USAGE ==========")
    print(response.usage)


if __name__ == "__main__":
    main()