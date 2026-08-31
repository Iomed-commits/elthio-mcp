#!/usr/bin/env python3
"""
Elthio MCP Server
Exposes supplement safety tools to Claude
and other MCP-compatible AI agents.
"""
import json
import sys
import os
import urllib.request as _ur
import urllib.parse  as _up

BASE_URL = os.environ.get(
    "ELTHIO_API_URL",
    "https://elthio-production.up.railway.app"
)

# ── MCP Protocol helpers ──────────────────────
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def recv():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())

# ── Tool definitions ──────────────────────────
TOOLS = [
    {
        "name": "check_supplement_safety",
        "description": (
            "Check if a supplement is safe with "
            "a user's medications and existing "
            "supplements. Returns interaction "
            "data, safety score, quality grade, "
            "filler detection, NIH verification, "
            "and timing recommendation. "
            "Use this whenever a user asks about "
            "supplement safety, drug interactions, "
            "or whether they can take a supplement "
            "with their medications."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplement": {
                    "type": "string",
                    "description": (
                        "The supplement to check. "
                        "Include brand and form for "
                        "best results. "
                        "e.g. 'Magnesium Bisglycinate "
                        "400mg' or 'Fish Oil 1000mg'"
                    ),
                },
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of user's prescription "
                        "medications. "
                        "e.g. ['Warfarin', "
                        "'Levothyroxine']"
                    ),
                },
                "supplements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "User's existing supplements "
                        "for interaction checking."
                    ),
                },
            },
            "required": ["supplement"],
        },
    },
    {
        "name": "grade_supplement_quality",
        "description": (
            "Get the quality grade (A-D) for a "
            "supplement based on bioavailability, "
            "filler detection, and NIH verification. "
            "Use this when a user asks about "
            "supplement quality, which form is best, "
            "whether a supplement has concerning "
            "fillers, or wants to compare brands."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplement": {
                    "type": "string",
                    "description": (
                        "Supplement name to grade. "
                        "e.g. 'Magnesium Oxide' or "
                        "'NOW Foods Vitamin D3 5000IU'"
                    ),
                },
                "other_ingredients": {
                    "type": "string",
                    "description": (
                        "Other ingredients text from "
                        "the label for filler "
                        "detection. Optional."
                    ),
                },
            },
            "required": ["supplement"],
        },
    },
    {
        "name": "get_supplement_timing",
        "description": (
            "Get the optimal time to take a "
            "supplement and why. Returns slot "
            "(morning/bedtime/with food/etc), "
            "clinical reasoning, and personalized "
            "instruction. Use this when a user "
            "asks when to take a supplement or "
            "how to build a timing schedule."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplement": {
                    "type": "string",
                    "description": (
                        "Supplement name. "
                        "e.g. 'Magnesium Glycinate'"
                    ),
                },
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "User's medications — "
                        "affects timing "
                        "recommendations."
                    ),
                },
            },
            "required": ["supplement"],
        },
    },
    {
        "name": "check_full_stack",
        "description": (
            "Check a complete supplement and "
            "medication stack for all interactions, "
            "conflicts, synergies, and generate "
            "a full daily timing schedule. "
            "Use this when a user wants to check "
            "their entire supplement regimen or "
            "build a complete daily schedule."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "medications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "All prescription medications."
                    ),
                },
                "supplements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "All supplements and vitamins."
                    ),
                },
                "wake_time": {
                    "type": "string",
                    "description": (
                        "Wake time in HH:MM format. "
                        "e.g. '07:00'"
                    ),
                },
                "breakfast_time": {
                    "type": "string",
                    "description": "Breakfast time HH:MM",
                },
                "dinner_time": {
                    "type": "string",
                    "description": "Dinner time HH:MM",
                },
                "bedtime": {
                    "type": "string",
                    "description": "Bedtime HH:MM",
                },
            },
            "required": ["supplements"],
        },
    },
    {
        "name": "verify_nih_label",
        "description": (
            "Verify if a supplement matches "
            "a record in the NIH Dietary Supplement "
            "Label Database (DSLD). Returns "
            "verification status, DSLD ID, and "
            "confidence level. Use this when a "
            "user asks if a supplement is "
            "legitimate or wants to verify "
            "label accuracy."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplement": {
                    "type": "string",
                    "description": (
                        "Supplement name to verify "
                        "against NIH DSLD."
                    ),
                },
            },
            "required": ["supplement"],
        },
    },
]

# ── Tool execution ────────────────────────────
def call_api(path, method="GET", body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req  = _ur.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with _ur.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def execute_tool(name, arguments):
    try:
        if name == "check_supplement_safety":
            supp  = arguments.get("supplement", "")
            meds  = arguments.get("medications", [])
            supps = arguments.get("supplements", [])

            # Run quality check
            q_url = (
                f"/api/quality-check?name="
                f"{_up.quote(supp)}"
            )
            q_data = call_api(q_url)

            # Run interaction check if meds provided
            interactions = []
            score        = None
            if meds or supps:
                i_data = call_api(
                    "/med-check", "POST",
                    {
                        "medications": meds,
                        "supplements": [supp] + supps,
                    }
                )
                interactions = \
                    i_data.get("interactions", [])
                score = i_data.get("score")

            # Determine safe
            critical = [
                i for i in interactions
                if (i.get("severity","")).lower()
                   == "critical"
            ]
            safe = len(critical) == 0

            quality = q_data.get("form_quality", {})
            dsld    = q_data.get("dsld", {})

            result = {
                "supplement":    supp,
                "safe":          safe,
                "score":         score,
                "grade":         quality.get("grade"),
                "bioavailability":
                    quality.get("bioavailability"),
                "timing":        q_data.get(
                    "timing_slot"),
                "timing_reason": q_data.get(
                    "timing_instruction"),
                "nih_verified":
                    dsld.get("status") == "VERIFIED",
                "nih_status":    dsld.get("status"),
                "fillers":       q_data.get(
                    "filler_summary", []),
                "clean_label":   len(
                    q_data.get("filler_summary",[])
                ) == 0,
                "interactions":  [
                    {
                        "title":    i.get("title"),
                        "severity": i.get("severity"),
                        "instruction":
                            i.get("instruction"),
                        "reason":   i.get("reason"),
                    }
                    for i in interactions[:5]
                ],
                "better_alternative":
                    quality.get("better_alternative"),
                "form_note":
                    quality.get("form_note"),
                "data_sources": [
                    "NIH Office of Dietary Supplements",
                    "FDA FAERS",
                    "NIH DSLD",
                ],
                "disclaimer": (
                    "Educational only — not medical "
                    "advice. Always confirm with "
                    "your pharmacist."
                ),
            }

            # Format human-readable summary
            summary_parts = []
            if not safe:
                for c in critical:
                    summary_parts.append(
                        f"⛔ CRITICAL: "
                        f"{c.get('title')} — "
                        f"{c.get('instruction')}"
                    )
            else:
                summary_parts.append(
                    f"✓ {supp} appears safe "
                    f"with your medications"
                )
            if result["grade"]:
                summary_parts.append(
                    f"Quality grade: "
                    f"{result['grade']} "
                    f"({result['bioavailability'] or 'unknown'} bioavailability)"
                )
            if result["timing"]:
                summary_parts.append(
                    f"Best timing: "
                    f"{result['timing']} — "
                    f"{result['timing_reason'] or ''}"
                )
            if result["fillers"]:
                filler_names = [
                    f.get("ingredient", f)
                    if isinstance(f, dict) else f
                    for f in result["fillers"]
                ]
                summary_parts.append(
                    f"⚠️ Fillers detected: "
                    f"{', '.join(filler_names)}"
                )
            if result["better_alternative"]:
                summary_parts.append(
                    f"💡 Better alternative: "
                    f"{result['better_alternative']}"
                )

            return {
                "summary": "\n".join(summary_parts),
                "data":    result,
            }

        elif name == "grade_supplement_quality":
            supp  = arguments.get("supplement", "")
            other = arguments.get(
                "other_ingredients", "")
            url   = (
                f"/api/quality-check?name="
                f"{_up.quote(supp)}"
                + (
                    f"&other_ingredients="
                    f"{_up.quote(other)}"
                    if other else ""
                )
            )
            data    = call_api(url)
            quality = data.get("form_quality", {})
            dsld    = data.get("dsld", {})
            fillers = data.get("filler_summary", [])

            grade = quality.get("grade", "?")
            grade_desc = {
                "A": "Excellent — highly bioavailable form, clean label",
                "B": "Good — solid bioavailability, minor concerns",
                "C": "Average — moderate bioavailability or some fillers",
                "D": "Poor — low bioavailability or concerning fillers",
            }.get(grade, "Unknown")

            summary = (
                f"Grade {grade}: {grade_desc}\n"
                f"{quality.get('form_note', '')}\n"
            )
            if fillers:
                fnames = [
                    f.get("ingredient", f)
                    if isinstance(f, dict) else f
                    for f in fillers
                ]
                summary += (
                    f"⚠️ Fillers: "
                    f"{', '.join(fnames)}\n"
                )
            else:
                summary += "✓ Clean label\n"
            if quality.get("better_alternative"):
                summary += (
                    f"💡 Better form: "
                    f"{quality['better_alternative']}"
                )

            nih_status = dsld.get("status","NOT_FOUND")
            nih_label  = {
                "VERIFIED":  "✓ NIH DSLD Verified",
                "POSSIBLE":  "~ NIH Partial Match",
                "MISMATCH":  "! NIH Label Mismatch",
                "NOT_FOUND": "? Not in NIH DSLD",
            }.get(nih_status, "? Not in NIH DSLD")
            summary += f"\n{nih_label}"

            return {"summary": summary, "data": data}

        elif name == "get_supplement_timing":
            supp = arguments.get("supplement", "")
            meds = arguments.get("medications", [])
            url  = (
                f"/api/quality-check?name="
                f"{_up.quote(supp)}"
            )
            data = call_api(url)

            SLOT_LABELS = {
                "morning":
                    "🌅 Morning — with breakfast",
                "evening":
                    "🌆 Evening — with dinner",
                "bedtime":
                    "🌙 Bedtime — 30-60 min before sleep",
                "with_food":
                    "🍽 With Food — any main meal",
                "empty_stomach":
                    "⏰ Before Breakfast — empty stomach",
                "midday":
                    "☀️ Midday — with lunch",
                "pre_workout":
                    "💪 Pre-Workout — 30-60 min before",
                "post_workout":
                    "🏋️ Post-Workout — within 30 min",
            }
            slot    = data.get("timing_slot","morning")
            label   = SLOT_LABELS.get(slot, slot)
            reason  = data.get("timing_instruction","")
            summary = (
                f"Best time for {supp}:\n"
                f"{label}\n"
            )
            if reason:
                summary += f"Why: {reason}"

            # Check drug separation if meds provided
            if meds:
                try:
                    sep_data = call_api(
                        "/api/separation-coach",
                        "POST",
                        {
                            "medications":  meds,
                            "supplements":  [supp],
                            "wake_time":    "07:00",
                            "breakfast_time":"07:30",
                            "lunch_time":   "12:30",
                            "dinner_time":  "18:30",
                            "bedtime":      "22:30",
                        }
                    )
                    drug_notes = sep_data.get(
                        "drug_timing_notes", [])
                    if drug_notes:
                        summary += "\n\n⚠️ Drug timing notes:"
                        for note in drug_notes[:2]:
                            summary += (
                                f"\n• {note.get('drug')} + "
                                f"{note.get('supplement')}: "
                                f"{note.get('instruction')}"
                            )
                except Exception:
                    pass

            return {"summary": summary, "data": data}

        elif name == "check_full_stack":
            meds  = arguments.get("medications", [])
            supps = arguments.get("supplements", [])
            body  = {
                "medications":    meds,
                "supplements":    supps,
                "wake_time":      arguments.get(
                    "wake_time", "07:00"),
                "breakfast_time": arguments.get(
                    "breakfast_time", "07:30"),
                "lunch_time":     "12:30",
                "dinner_time":    arguments.get(
                    "dinner_time", "18:30"),
                "bedtime":        arguments.get(
                    "bedtime", "22:30"),
            }
            data = call_api(
                "/api/separation-coach", "POST", body)

            schedule     = data.get("schedule", {})
            conflicts    = data.get("conflicts", [])
            drug_notes   = data.get(
                "drug_timing_notes", [])
            crowding     = data.get(
                "crowding_warnings", [])

            SLOT_LABELS = {
                "morning":       "🌅 Morning",
                "evening":       "🌆 Evening",
                "bedtime":       "🌙 Bedtime",
                "with_food":     "🍽 With Food",
                "empty_stomach": "⏰ Before Breakfast",
                "midday":        "☀️ Midday",
            }

            summary = "YOUR DAILY SUPPLEMENT SCHEDULE\n"
            summary += "=" * 35 + "\n\n"
            for slot_key, slot_data in schedule.items():
                if not slot_data:
                    continue
                items = slot_data.get("items", [])
                if not items:
                    continue
                label = SLOT_LABELS.get(
                    slot_key, slot_key)
                sub   = slot_data.get("sub", "")
                summary += f"{label}"
                if sub:
                    summary += f" — {sub}"
                summary += "\n"
                for item in items:
                    summary += (
                        f"  • {item.get('name')}: "
                        f"{item.get('instruction','')}\n"
                    )
                summary += "\n"

            if drug_notes:
                summary += "⚠️ DRUG-SUPPLEMENT NOTES\n"
                for note in drug_notes[:3]:
                    summary += (
                        f"• {note.get('drug')} + "
                        f"{note.get('supplement')}: "
                        f"{note.get('instruction')}\n"
                    )
                summary += "\n"

            if conflicts:
                summary += "⚠️ TIMING CONFLICTS\n"
                for c in conflicts[:3]:
                    summary += (
                        f"• {c.get('supplement_a')} + "
                        f"{c.get('supplement_b')}: "
                        f"separate by "
                        f"{c.get('timing_hours',2)}+ hours\n"
                    )

            summary += (
                "\nNote: Educational only — "
                "not medical advice."
            )
            return {"summary": summary, "data": data}

        elif name == "verify_nih_label":
            supp = arguments.get("supplement", "")
            url  = (
                f"/api/verify-supplement?name="
                f"{_up.quote(supp)}"
            )
            data = call_api(url)
            status = data.get("status", "NOT_FOUND")
            labels = {
                "VERIFIED": (
                    f"✓ VERIFIED — {supp} matches "
                    f"a registered NIH DSLD record"
                ),
                "POSSIBLE": (
                    f"~ PARTIAL MATCH — {supp} "
                    f"partially matches NIH records. "
                    f"Review extracted ingredients."
                ),
                "MISMATCH": (
                    f"! MISMATCH — {supp} label "
                    f"may not match NIH records."
                ),
                "NOT_FOUND": (
                    f"? NOT FOUND — {supp} was not "
                    f"found in the NIH DSLD database."
                ),
            }
            summary = labels.get(
                status, labels["NOT_FOUND"])
            if data.get("dsld_url"):
                summary += (
                    f"\nFederal record: "
                    f"{data['dsld_url']}"
                )
            return {"summary": summary, "data": data}

        else:
            return {
                "error": f"Unknown tool: {name}"
            }

    except Exception as e:
        return {
            "error":   str(e),
            "summary": (
                f"Could not complete {name}: "
                f"{str(e)}"
            ),
        }

# ── MCP main loop ─────────────────────────────
def main():
    while True:
        msg = recv()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id":      msg_id,
                "result":  {
                    "protocolVersion": "2024-11-05",
                    "capabilities":    {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name":    "elthio",
                        "version": "1.0.0",
                    },
                },
            })

        elif method == "tools/list":
            send({
                "jsonrpc": "2.0",
                "id":      msg_id,
                "result":  {"tools": TOOLS},
            })

        elif method == "tools/call":
            params = msg.get("params", {})
            name   = params.get("name", "")
            args   = params.get("arguments", {})
            result = execute_tool(name, args)

            # Format as MCP content
            content_text = result.get(
                "summary",
                json.dumps(
                    result.get("data", result),
                    indent=2
                )
            )
            send({
                "jsonrpc": "2.0",
                "id":      msg_id,
                "result":  {
                    "content": [
                        {
                            "type": "text",
                            "text": content_text,
                        }
                    ],
                    "isError": "error" in result,
                },
            })

        elif method == "notifications/initialized":
            pass  # Acknowledge — no response needed

        else:
            if msg_id is not None:
                send({
                    "jsonrpc": "2.0",
                    "id":      msg_id,
                    "error":   {
                        "code":    -32601,
                        "message": "Method not found",
                    },
                })

if __name__ == "__main__":
    main()
