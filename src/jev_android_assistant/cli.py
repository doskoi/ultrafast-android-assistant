"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from .agent import AndroidAssistant
from .android import DEFAULT_ADB, AdbDevice
from .policy import DualPolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded Laya/Jev Android UI navigation")
    parser.add_argument("--adb", default=DEFAULT_ADB)
    parser.add_argument("--serial")
    parser.add_argument("--package", required=True, help="Android application package allowed for this run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--primary-provider", choices=("laya", "jev"), default=None)
    parser.add_argument("--secondary-provider", choices=("laya", "jev", "none"), default=None)
    parser.add_argument("--min-probability", type=float, default=0.55)
    parser.add_argument("--completion-threshold", type=float, default=0.85)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect", help="print the redacted, indexed action space without a model call")
    suggest = subparsers.add_parser("suggest", help="ask the configured provider for one action without executing it")
    suggest.add_argument("goal")
    run = subparsers.add_parser("run", help="execute a bounded read-only navigation loop")
    run.add_argument("goal")
    run.add_argument("--max-steps", type=int, default=30)
    return parser


def main() -> None:
    args = _parser().parse_args()
    device = AdbDevice(adb=args.adb, serial=args.serial, package=args.package)
    assistant = AndroidAssistant(
        device,
        DualPolicy(
            primary=args.primary_provider,
            secondary=args.secondary_provider,
            laya_model=args.model,
            jev_model=args.model,
            fallback_threshold=args.min_probability,
            completion_threshold=args.completion_threshold,
        ),
        min_probability=args.min_probability,
        completion_threshold=args.completion_threshold,
    )
    try:
        if args.command == "inspect":
            snapshot = assistant.inspect()
            output = {
                "activity": snapshot.activity,
                "package": snapshot.package,
                "fingerprint": snapshot.fingerprint,
                "text": snapshot.text,
                "elements": [element.model_view() for element in snapshot.elements],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        elif args.command == "suggest":
            _, decision = assistant.suggest(args.goal)
            print(json.dumps({"status": "suggested", "decision": decision.__dict__}, ensure_ascii=False, indent=2))
        else:
            for result in assistant.run(args.goal, max_steps=args.max_steps):
                print(json.dumps(result, ensure_ascii=False), flush=True)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
