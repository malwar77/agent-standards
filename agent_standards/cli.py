"""agent-standards CLI.

    init                 create .agent-standards profile (base optional)
    discover [PATH]      mine standards from a codebase
    review               approve/reject discovered candidates
    inject "task"        print relevant standards for an AI agent
    enforce [PATH]       hard-gate check for critical standards (CI/pre-commit)
    score FILE...        did changed code follow the standards?
    list                 list standards in the active profile
    sync                 copy project standards to the base profile
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .discover.ast_mine import discover
from .enforce.check import enforce
from .evals import score_change
from .index.store import Store, Standard
from .inject.injector import inject, RENDERERS


def _store(args) -> Store:
    base = getattr(args, "base", None) or os.environ.get("AGENT_STANDARDS_BASE")
    return Store(project_dir=args.profile, base_dir=base)


def cmd_init(args):
    store = _store(args)
    print(f"project profile: {store.project_dir}")
    if store.base_dir:
        print(f"base profile:    {store.base_dir}")
    print("ready.")


def cmd_discover(args):
    store = _store(args)
    strong, weak = discover(args.path, min_observations=args.min_observations,
                            min_consistency=args.min_consistency)
    saved = 0
    for std in strong:
        store.save(std)
        saved += 1
    for std in weak:
        if args.keep_weak:
            store.save(std)
            saved += 1
    print(f"discovered: {len(strong)} strong, {len(weak)} weak; saved {saved} "
          f"candidate(s) to {store.project_dir}/standards/")
    if args.json:
        print(json.dumps([s.to_dict() for s in strong + weak], indent=1))


def cmd_review(args):
    store = _store(args)
    for status in ("candidate",):
        for std in store.load_all(statuses=(status,)):
            ev = std.evidence
            ev_line = (f"  evidence: {ev.followed}/{ev.observed} "
                       f"({ev.consistency:.0%})" if ev else "  (no evidence)")
            print(f"[{std.id}] {std.title}\n{ev_line}")
            if args.auto_approve and ev and ev.consistency >= args.threshold:
                std.status = "approved"
                store.save(std)
                print("  -> auto-approved")
            elif args.reject:
                std.status = "rejected"
                store.save(std)
                print("  -> rejected")
            elif not args.auto_approve:
                ans = input("  approve? [y/N] ").strip().lower()
                if ans == "y":
                    std.status = "approved"
                    store.save(std)


def cmd_inject(args):
    store = _store(args)
    stds = store.load_all(statuses=("approved",))
    if not stds:
        print("no approved standards; run discover + review first",
              file=sys.stderr)
        return 1
    out = inject(args.task, stds, fmt=args.format, top_k=args.top_k,
                 token_budget=args.token_budget)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {args.output}")
    else:
        print(out)
    return 0


def cmd_enforce(args):
    store = _store(args)
    result = enforce(args.path, store, tolerance=args.tolerance)
    print(result.report())
    return 0 if result.passed else 1


def cmd_score(args):
    store = _store(args)
    stds = store.load_all(statuses=("approved",))
    for std, current, recorded in score_change(args.files, stds):
        cur = f"{current:.0%}" if current is not None else "n/a"
        rec = f"{recorded:.0%}" if recorded is not None else "n/a"
        flag = ""
        if current is not None and recorded is not None and current < recorded:
            flag = "  <- regressed in changed code"
        print(f"{std.id}: changed-code {cur} vs recorded {rec}{flag}")
    return 0


def cmd_list(args):
    store = _store(args)
    for std in store.load_all(statuses=("approved", "candidate")):
        crit = " [critical]" if std.critical else ""
        ev = std.evidence
        ev_line = (f"  {ev.consistency:.0%} ({ev.followed}/{ev.observed})"
                   if ev else "")
        print(f"{std.status:9} {std.id}{crit}\n{ev_line}")


def cmd_sync(args):
    store = _store(args)
    moved = store.sync_to_base()
    print(f"synced {moved} standard(s) to base profile {store.base_dir}")


def build_parser():
    p = argparse.ArgumentParser(prog="agent-standards",
                                description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--profile", default=".agent-standards",
                   help="project profile dir (default .agent-standards)")
    p.add_argument("--base", default=None,
                   help="base profile dir (default $AGENT_STANDARDS_BASE)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    d = sub.add_parser("discover")
    d.add_argument("path", nargs="?", default=".")
    d.add_argument("--min-observations", type=int, default=5)
    d.add_argument("--min-consistency", type=float, default=0.7)
    d.add_argument("--keep-weak", action="store_true")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_discover)

    r = sub.add_parser("review")
    r.add_argument("--auto-approve", action="store_true")
    r.add_argument("--reject", action="store_true")
    r.add_argument("--threshold", type=float, default=0.9)
    r.set_defaults(func=cmd_review)

    i = sub.add_parser("inject")
    i.add_argument("task")
    i.add_argument("--format", choices=list(RENDERERS), default="markdown")
    i.add_argument("--top-k", type=int, default=5)
    i.add_argument("--token-budget", type=int, default=800)
    i.add_argument("--output", default=None)
    i.set_defaults(func=cmd_inject)

    e = sub.add_parser("enforce")
    e.add_argument("path", nargs="?", default=".")
    e.add_argument("--tolerance", type=float, default=0.05)
    e.set_defaults(func=cmd_enforce)

    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    s.set_defaults(func=cmd_score)

    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("sync").set_defaults(func=cmd_sync)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
