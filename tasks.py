# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "argh==0.26.2",
#     "beautifulsoup4==4.12.2",
#     "browser_cookie3==0.16.2",
#     "html2text==2020.1.16",
#     "python-dotenv==1.0.0",
#     "requests==2.27.1",
#     "tabulate==0.9.0",
#     "termcolor==1.1.0",
#     "tomlkit==0.12.3",
# ]
# ///
import shlex
import subprocess
import sys
import typing as t
import webbrowser
from datetime import datetime
from functools import partial, wraps
from os import chdir, environ, startfile
from pathlib import Path
from uuid import uuid4

import browser_cookie3
import html2text
import requests
import tomlkit as toml
from argh import aliases, arg, dispatch_commands, named, wrap_errors
from bs4 import BeautifulSoup
from bs4.element import Tag
from dotenv import load_dotenv
from termcolor import colored as c

cb = partial(c, attrs=["bold"])

MAIN = """\
fn main() {{
    let (part1, part2) = {crate}::solve();
    println!("{{part1}}");
    println!("{{part2}}");
}}\
"""

LIB = """\
use std::fmt::Display;

#[inline]
pub fn solve() -> (impl Display, impl Display) {
    ("TODO", "TODO")
}\
"""

DEFAULT_BASELINE = "previous"

WORKSPACE_MANIFEST_PATH = Path(__file__).parent / "Cargo.toml"

NOW = datetime.now()

DAYS_LEFT = set(range(1, 26)) - {int(p.name[len("day") :]) for p in Path(__file__).parent.glob("day*")}

YEAR = toml.parse(WORKSPACE_MANIFEST_PATH.read_text()).get("metadata", {}).get("year", NOW.year)

load_dotenv()

session = requests.Session()
if "SESSION_COOKIE" in environ:
    session.cookies.update({"session": environ["SESSION_COOKIE"]})
else:
    session.cookies.update(browser_cookie3.firefox(domain_name="adventofcode.com"))
session.headers.update({"User-Agent": "PurpleMyst/aoc-template with much love! <3"})


def run(cmd: t.Sequence[str | Path], /, **kwargs) -> subprocess.CompletedProcess:
    check = kwargs.pop("check", True)
    print(
        cb("$", "green"),
        shlex.join(map(str, cmd)),
        c(f"(w/ options {kwargs})", "green") if kwargs else "",
    )
    proc = subprocess.run(cmd, **kwargs)
    if check and proc.returncode != 0:
        print(cb("Failed.", "red"))
        sys.exit(proc.returncode)
    return proc


def add_line(p: Path, l: str) -> None:
    ls = p.read_text().splitlines()
    ls.insert(-1, l)
    if ls[-1] != "":
        # add or keep trailing newline
        ls.append("")
    p.write_text("\n".join(ls), newline="\n")


def in_root_dir(f):
    @wraps(f)
    def inner(*args, **kwargs):
        chdir(Path(__file__).parent)
        return f(*args, **kwargs)

    return inner


@arg("-d", "--day", choices=DAYS_LEFT, default=min(DAYS_LEFT, default=0), required=False)
@aliases("ss")
@wrap_errors((requests.HTTPError,))
def start_solve(day: int = min(DAYS_LEFT, default=0)) -> None:
    "Start solving a day, by default today."
    crate = f"day{day:02}"
    crate_path = Path(crate)

    if crate_path.exists():
        print(f"{crate} already exists.")
        return

    resp = session.get(f"https://adventofcode.com/{YEAR}/day/{day}/input")
    resp.raise_for_status()
    puzzle_input = resp.text

    manifest = toml.parse(WORKSPACE_MANIFEST_PATH.read_text())
    if crate not in manifest["workspace"]["members"]:  # type: ignore
        manifest["workspace"]["members"].append(crate)  # type: ignore

    metadata = manifest["workspace"].setdefault("metadata", {})  # type: ignore
    metadata[crate] = {"start_time": datetime.now()}

    with WORKSPACE_MANIFEST_PATH.open("w") as manifest_f:
        toml.dump(manifest, manifest_f)

    run(("cargo", "new", "--bin", crate))
    run(
        (
            "cargo",
            "add",
            "--manifest-path",
            "benchmark/Cargo.toml",
            "--path",
            crate,
            crate,
        )
    )

    src = crate_path / "src"
    (src / "main.rs").write_text(MAIN.format(crate=crate), newline="\n")
    (src / "lib.rs").write_text(LIB, newline="\n")
    (src / "input.txt").write_text(puzzle_input, newline="\n")

    benches = Path("benchmark", "benches")
    add_line(benches / "criterion.rs", f"    {crate},")
    add_line(benches / "iai.rs", f"    {crate}: {crate}_solve,")

    fetch_problem(YEAR, day)

    run(("git", "add", crate))
    webbrowser.open_new(f"https://adventofcode.com/{YEAR}/day/{day}")


@aliases("sb")
@in_root_dir
def set_baseline(day: str, name: str = DEFAULT_BASELINE) -> None:
    "Run a criterion benchmark, setting its results as the new baseline."
    run(
        (
            "cargo",
            "bench",
            "--bench",
            "criterion",
            "--",
            day,
            "--save-baseline",
            name,
            "--verbose",
        )
    )


@aliases("cmp")
@in_root_dir
def compare(day: str, name: str = DEFAULT_BASELINE) -> None:
    "Run a criterion benchmark, comparing its results to the saved baseline."
    run(
        (
            "cargo",
            "bench",
            "--bench",
            "criterion",
            "--",
            day,
            "--baseline",
            name,
            "--verbose",
        )
    )


@in_root_dir
@aliases("cmp-stash")
def compare_by_stashing(day: str, name: str = DEFAULT_BASELINE) -> None:
    "Stash the current changes, set the baseline and then compare the new changes."
    run(("git", "stash", "push", "-m", "Stashing for benchmarking"))
    set_baseline(day, name)
    run(("git", "stash", "pop"))
    compare(day, name)


@in_root_dir
def criterion(day: str) -> None:
    "Run a criterion benchmark, without caring about baselines."
    run(("cargo", "bench", "--bench", "criterion", "--", day, "--verbose"))


@in_root_dir
def iai() -> None:
    "Run the iai benchmark."
    run(("cargo", "bench", "--bench", "iai"))


@aliases("wr")
def watch_run() -> None:
    "Run the solution everytime it changes."
    del environ["RUSTFLAGS"]
    run(("cargo", "watch", "--clear", "--exec", "run"))


@aliases("r")
@named("run")
def do_run() -> None:
    "Run the solution in debug mode."
    del environ["RUSTFLAGS"]
    run(("cargo", "run"))


@aliases("rr")
def run_release() -> None:
    "Run the solution, in release mode."
    run(("cargo", "run", "--release"))


@aliases("rp")
def run_prototype() -> None:
    "Run a python file named prototype.py everytime something changes."
    run(("cargo", "watch", "--clear", "--shell", "python3 prototype.py"))


@arg("level", help="Which part to submit.", choices=(1, 2))
@aliases("a")
@wrap_errors((requests.HTTPError, AssertionError))
def answer(answer: str, level: int) -> None:
    "Submit your answer!"

    day = Path.cwd().resolve().name
    if not day.startswith("day"):
        print(cb("Not in a day directory.", "red"))
        return

    resp = session.post(
        f"https://adventofcode.com/{YEAR}/day/{day}/answer",
        data={"answer": answer, "level": str(level)},
    )
    resp.raise_for_status()

    # Get the main text, removing the "return to" link, and show it in markdown form.
    soup = BeautifulSoup(resp.text, features="html.parser").main
    assert soup is not None, "no main element?"
    return_link = soup.find(href=f"/{YEAR}/day/{day}")
    if isinstance(return_link, Tag):
        return_link.decompose()
    h = html2text.HTML2Text()
    h.ignore_links = True
    print(h.handle(str(soup)).strip())


@in_root_dir
def fetch_problem(year, day) -> None:
    "Fetch the problem statement."
    resp = session.get(f"https://adventofcode.com/{year}/day/{day}")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, features="html.parser").main
    h = html2text.HTML2Text()
    t = h.handle(str(soup)).strip()
    Path(f"day{day:02}", "problem.md").write_text(t, newline="\n")


def show_session_cookie() -> None:
    "Conquer outer space."
    print(c("Your session cookie:", "yellow"), session.cookies["session"])


@in_root_dir
@aliases("mct")
def measure_completion_time() -> None:
    "Measure completion time for all days."
    from tabulate import tabulate

    manifest = toml.parse(WORKSPACE_MANIFEST_PATH.read_text())

    table = []
    for day in Path().glob("day*"):
        day_metadata = manifest["workspace"].get("metadata", {}).get(day.name, {})  # type: ignore
        start_time = day_metadata.get("start_time")
        end_time = day_metadata.get("completion_time")
        src = day / "src"
        if start_time is None:
            start_time = datetime.fromtimestamp((src / "input.txt").stat().st_ctime)
        if end_time is None:
            end_time = datetime.fromtimestamp(max(f.stat().st_mtime for f in src.glob("**/*.rs")))
        completion_time = end_time - start_time
        table.append((day.name, str(completion_time)))
    print(tabulate(table, headers=["Day", "Completion Time"], tablefmt="fancy_grid"))


@aliases("sct")
def set_completion_time() -> None:
    "Set the completion time for the day you're currently in."

    day = Path.cwd().resolve().name
    if not day.startswith("day"):
        print(cb("Not in a day directory.", "red"))
        return

    manifest = toml.parse(WORKSPACE_MANIFEST_PATH.read_text())
    metadata = manifest["workspace"].setdefault("metadata", {})  # type: ignore
    metadata.setdefault(day, {})["completion_time"] = datetime.now()

    with WORKSPACE_MANIFEST_PATH.open("w") as manifest_f:
        toml.dump(manifest, manifest_f)


@in_root_dir
def flamegraph(day: str, *, remote="linode") -> None:
    "Run a flamegraph benchmark on a remote."
    import tarfile
    import tempfile

    from rich.console import Console

    console = Console()

    def filter(info):
        if any(s in info.name for s in (".git", "target")):
            console.log(f"{info.name!r} [red]skipped.[/red]")
            return None
        console.log(f"{info.name!r} [green]added to tarball.[/green]")
        return info

    # Generate a zipped tarball of the current source code.
    archive_stem = str(uuid4())
    archive_name = f"{archive_stem}.tar.gz"
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir, archive_name)
        with console.status("Compressing..."), tarfile.open(archive_path, "w:gz") as tar:
            tar.add(".", filter=filter)

        # Upload it to the remote via scp and untar it.
        run(("scp", "-C", archive_path, f"{remote}:/tmp/{archive_name}"))
        run(("ssh", remote, "tar", "-xzf", f"/tmp/{archive_name}", "--one-top-level", "-C", "/tmp"))

    # Run the benchmark on the remote.
    run(
        (
            "ssh",
            remote,
            "cd",
            f"/tmp/{archive_stem}",
            "&&",
            "CARGO_PROFILE_BENCH_DEBUG=true",
            "cargo",
            "flamegraph",
            "--bench",
            "criterion",
            "--",
            "--bench",
            day,
        )
    )

    # Download the flamegraph.
    run(("scp", f"{remote}:/tmp/{archive_stem}/flamegraph.svg", "."))

    # Remove the archive from the remote.
    run(("ssh", remote, "rm", "-rf", f"/tmp/{archive_stem}", f"/tmp/{archive_name}"))

    # Open the flamegraph.
    startfile("flamegraph.svg")


def main() -> None:
    # environ["RUST_BACKTRACE"] = "1"
    environ["RUSTFLAGS"] = "-C target-cpu=native"
    dispatch_commands(
        (
            start_solve,
            answer,
            set_baseline,
            compare,
            compare_by_stashing,
            criterion,
            iai,
            watch_run,
            do_run,
            run_release,
            run_prototype,
            show_session_cookie,
            measure_completion_time,
            set_completion_time,
            flamegraph,
        ),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bye!")
