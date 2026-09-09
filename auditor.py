"""Daily loss-pattern audit for the AI trading system.

Run this from a daily scheduler. ``new_rules.json`` stores an audit date so an
accidental second invocation will not call DeepSeek again that UTC day.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

import config


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MEMORY_FILE = Path(__file__).with_name("memory.json")
RULES_FILE = Path(__file__).with_name("new_rules.json")
MAX_TRADES = 50


def load_json_array(path):
    """Load a JSON array, treating a missing file as empty."""

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return value


def load_rules_document():
    """Load saved rules and initialize a document when none exists."""

    if not RULES_FILE.exists():
        return {"last_audit_date": None, "rules": []}
    with RULES_FILE.open("r", encoding="utf-8") as json_file:
        document = json.load(json_file)
    if not isinstance(document, dict):
        raise ValueError("new_rules.json must contain a JSON object")
    document.setdefault("last_audit_date", None)
    document.setdefault("rules", [])
    return document


from memory_store import reconcile_closed_trades


def request_rules(trades):
    """Ask DeepSeek for evidence-based confidence-reduction rules."""

    system_prompt = """
You are a trading-risk auditor. Analyze confirmed closed trade records to find repeated loss patterns. Factor in price action, cross-asset relationships, volume (tick volume and relative volume), and volatility (ATR).

Only propose a rule when supplied data demonstrates the same setup or condition caused at least 3 losses. Do not claim causality from one loss or from missing context. A rule must lower model confidence for that setup only; never increase risk, open a position, or bypass risk controls.

Return ONLY a JSON object in exactly this shape:
{
  "rules": [
    {
      "setup": "precise, testable setup or indicator condition (e.g. H1 relative_volume < 0.45 with elevated ATR, or conflicting cross-asset move)",
      "confidence_reduction_points": 15,
      "evidence": "concise description of matching losses",
      "affected_symbol": "symbol",
      "sample_size": 3
    }
  ]
}
If no pattern meets the threshold, return {"rules": []}.
confidence_reduction_points must be an integer from 1 to 50.
""".strip()

    response = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Audit these most recent confirmed trades. A missing "
                        "realized P/L means you must not assume that trade lost.\n\n"
                        + json.dumps(trades, separators=(",", ":"))
                    ),
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()

    try:
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"DeepSeek returned an invalid audit response: {error}")

    rules = result.get("rules")
    if not isinstance(rules, list):
        raise ValueError("DeepSeek audit response must contain a rules array")

    validated_rules = []
    for rule in rules:
        try:
            reduction = int(rule["confidence_reduction_points"])
            sample_size = int(rule["sample_size"])
            setup = str(rule["setup"]).strip()
            evidence = str(rule["evidence"]).strip()
            affected_symbol = str(rule["affected_symbol"]).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"DeepSeek returned a malformed rule: {error}")

        if not setup or not evidence or not affected_symbol:
            raise ValueError("DeepSeek returned a rule with an empty required field")
        if not 1 <= reduction <= 50 or sample_size < 3:
            raise ValueError("DeepSeek returned a rule outside the safety limits")

        validated_rules.append({
            "setup": setup,
            "confidence_reduction_points": reduction,
            "evidence": evidence,
            "affected_symbol": affected_symbol,
            "sample_size": sample_size,
        })

    return validated_rules


def save_rules(document):
    """Atomically persist the audit document."""

    temporary_file = RULES_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as json_file:
        json.dump(document, json_file, indent=2)
        json_file.write("\n")
    temporary_file.replace(RULES_FILE)


def run_audit(force=False):
    """Run one audit, unless this UTC day has already been audited."""

    # Automatically reconcile any closed trades from MT5 first
    try:
        reconciled_count = reconcile_closed_trades()
        if reconciled_count > 0:
            print(f"[AUDITOR] Reconciled {reconciled_count} closed trade(s) from MT5.")
    except Exception as e:
        print(f"[AUDITOR] Note: Trade reconciliation warning: {e}")

    today = datetime.now(timezone.utc).date().isoformat()
    document = load_rules_document()
    if not force and document.get("last_audit_date") == today:
        print("[AUDITOR] Audit already completed today (UTC).")
        return {
            "status": "already_audited",
            "message": "Audit already completed today (UTC). Use force=True to re-run.",
            "rules": document.get("rules", []),
            "last_audit_date": document.get("last_audit_date"),
        }

    all_trades = load_json_array(MEMORY_FILE)
    # Prioritize closed trades with realized outcome
    closed_trades = [t for t in all_trades if t.get("status") == "CLOSED" or t.get("realized_pnl") is not None]
    trades = (closed_trades if len(closed_trades) >= 3 else all_trades)[-MAX_TRADES:]

    if not trades:
        print("[AUDITOR] No confirmed trades in memory.json; nothing to audit.")
        return {
            "status": "no_trades",
            "message": "No confirmed trades to audit.",
            "rules": document.get("rules", []),
        }

    document["rules"] = request_rules(trades)
    document["last_audit_date"] = today
    document["last_audit_at"] = datetime.now(timezone.utc).isoformat()
    document["trades_analyzed"] = len(trades)
    save_rules(document)
    print(f"[AUDITOR] Saved {len(document['rules'])} rule(s).")
    return {
        "status": "success",
        "rules": document["rules"],
        "trades_analyzed": len(trades),
        "last_audit_at": document["last_audit_at"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit recent confirmed trades.")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    try:
        run_audit(force=arguments.force)
    except requests.exceptions.RequestException as error:
        raise SystemExit(f"[AUDITOR] DeepSeek request failed: {error}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        raise SystemExit(f"[AUDITOR] Audit failed: {error}")
