#!/usr/bin/env python3

import argparse
import re
import subprocess


def cdf(t, x):
    count = 0.0
    for value in t:
        if value <= x:
            count += 1.0
        else:
            break

    return count / len(t)


def git_numstat(repository, after, before):
    cmd = [
            "git",
            "-C",
            repository,
            "log",
            "--no-merges",
            "--format=%H",
            "--numstat"
            ]

    if after:
        cmd.append("--after", after)

    if before:
        cmd.append("--before", before)

    res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True)

    added = []
    removed = []
    changed = []
    a = r = c = 0
    # stdout format is
    #   <commit>
    #   <empty>
    #   <added><blank><removed><blank><file1>
    #   <added><blank><removed><blank><file2>
    #   ...
    # Total up the stat lines for each commit and record them when we see the
    # next commit. This causes a false record at index 0.
    for line in res.stdout.splitlines():
        if re.fullmatch(b"[a-f0-9]{40}", line):
            added.append(a)
            removed.append(r)
            changed.append(c)
            a = r = c = 0
            continue

        stat = line.split()
        if len(stat) == 0:
            continue

        # Skip binary files
        if stat[0] == b"-":
            continue

        a += int(stat[0])
        r += int(stat[1])
        c = a + r

    added.sort()
    removed.sort()
    changed.sort()

    return added, removed, changed

def main(args):
    added, removed, changed = git_numstat(
            args.repository,
            args.since,
            args.before)

    print("added", "p_added")
    for x in added:
        print(x, cdf(added, x))

    print("\n\nremoved", "p_removed")
    for x in removed:
        print(x, cdf(removed, x))

    print("\n\nchanged", "p_changed")
    for x in changed:
        print(x, cdf(changed, x))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="foo")

    parser.add_argument("repository", help="path to the repository to analyse")

    parser.add_argument("--after", help="""
            forego analysis of commits before this timespec. Passed directly to
            git-log.""")
    parser.add_argument("--before", help="Opposite of --after")

    main(parser.parse_args())
