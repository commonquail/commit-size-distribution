#!/usr/bin/env python3

import argparse
import hashlib
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import re
import subprocess
import tempfile


def cachefile_name(repository, after, before):
    cmd = ["git", "-C", repository, "rev-parse", "HEAD"]
    head_rev = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)

    digest = hashlib.sha256()
    digest.update(bytes(repository, "UTF-8"))
    digest.update(head_rev.stdout)
    digest.update(bytes(str(after), "UTF-8"))
    digest.update(bytes(str(before), "UTF-8"))
    key = digest.hexdigest() + ".csv"

    return os.path.join(
            tempfile.gettempdir(),
            "commit-size-distribution",
            os.path.basename(os.path.relpath(repository)),
            key)


def git_numstat(repository, after, before):
    cachefile = cachefile_name(repository, after, before)

    if os.path.exists(cachefile):
        return pd.read_csv(cachefile, index_col=0, parse_dates=False)
    else:
        res = uncached_git_numstat(repository, after, before)
        os.makedirs(os.path.dirname(cachefile), exist_ok=True)
        res.to_csv(cachefile)
        return res


def uncached_git_numstat(repository, after, before):
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

    return pd.DataFrame({
        "added": added[1:],
        "removed": removed[1:],
        "changed": changed[1:],
        })


# Adapted from https://stackoverflow.com/a/43455567/482758
def mark_hours(ax):
    """
    Effeciently draws vertical lines at increments of 400,
    the middle optimal-inspection-rate, per
    https://www.ibm.com/developerworks/rational/library/11-proven-practices-for-peer-review/
    :param ax: The x axis
    """
    _, x_max = ax.get_xlim()
    xs = np.array(range(400, int(x_max), 400), copy=False)
    x_points = np.repeat(xs, repeats=3)
    y_points = np.repeat(
            np.array((0, 1.05, np.nan))[None, :],
            repeats=len(xs),
            axis=0).flatten()

    plt.plot(
            x_points,
            y_points,
            scaley=False,
            color="black",
            linewidth="0.5")


def main(args):
    df = git_numstat(
            args.repository,
            args.after,
            args.before)

    plt.style.use("ggplot")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set(
            title="Size of non-merge commits",
            xlabel="Lines of code",
            ylabel="Probability")

    ax.yaxis.set_ticks(np.arange(0, 1.1, 0.1))

    x_range = None
    if args.max_size:
        # Although the range kwarg's documentation suggests it represents the
        # "max size" it always uses the supplied value, inflating the x_max
        # when the specified limit exceeds the max input. Compare the max input
        # to prevent that.
        x_range = (0, min(args.max_size, df.changed.max()))

    ax.hist(
            [df.added, df.removed, df.changed],
            bins=len(df.changed),
            normed=True,
            histtype="step",
            range=x_range,
            color=("green", "red", "blue"),
            cumulative=-1,
            label=("added", "removed", "changed"))

    ax.legend().set_visible(True)

    if args.mark_hours:
        mark_hours(ax)

    if args.plot_outfile:
        fig.savefig(
                args.plot_outfile,
                transparent=False,
                bbox_inches="tight")

    if args.preview:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""
Plot Git commit patch-size distribution.

Run this command with the path to a Git repository. It will print three
cumulative distribution functions of the number of added, removed, and total
changed lines in every non-merge commit reachable from HEAD.

Either plot-outfile, --preview, or both must be specified.

History analysis takes time linear in the number of commits, which could be a
while, but is cached to speed up successive runs.
""")

    parser.add_argument("repository", help="path to the repository to analyse")
    parser.add_argument(
            "plot_outfile",
            metavar="plot-outfile",
            nargs="?",
            help="""
            path to write a PNG plot to. Required if --preview is omitted.""")

    parser.add_argument("--after", help="""
            forego analysis of commits before this timespec. Passed directly to
            git-log.""")
    parser.add_argument("--before", help="Opposite of --after")
    parser.add_argument(
            "--mark-hours",
            action="store_true",
            help="""
            draw vertical lines at increments of 400 to indicate hours
            necessary for review, according to SmartBear's Cisco study""")
    parser.add_argument(
            "--max-size",
            type=int,
            help="""
            threshold above which commit sizes should be considered noise and
            be disregarded""")
    parser.add_argument(
            "--preview",
            action="store_true",
            help="""
            open a preview of the plot in the foreground. Required if
            plot-outfile is omitted.""")

    args = parser.parse_args()

    if not args.plot_outfile and not args.preview:
        parser.error("plot-outfile or --preview required")

    main(args)
