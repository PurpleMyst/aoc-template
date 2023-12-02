import datetime
import shlex
import subprocess
import sys
import typing as t
import webbrowser
from functools import partial, wraps
from os import chdir, environ
from pathlib import Path

import browser_cookie3
import html2text
import requests
import toml
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

NOW = datetime.datetime.now()
DEFAULT_DAY = NOW.day
DEFAULT_YEAR = NOW.year

load_dotenv()

session = requests.Session()
if "SESSION_COOKIE" in environ:
    session.cookies.update({"session": environ["SESSION_COOKIE"]})
else:
    session.cookies.update(browser_cookie3.load(domain_name="adventofcode.com"))
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


def year_and_day(f):
    day = arg(
        "-d", "--day", choices=range(1, 25 + 1), default=DEFAULT_DAY, required=False
    )
    year = arg(
        "-y",
        "--year",
        choices=range(2015, DEFAULT_YEAR + 1),
        default=DEFAULT_YEAR,
        required=False,
    )
    return day(year(f))


@year_and_day
@aliases("ss")
@wrap_errors((requests.HTTPError,))
def start_solve(day: int = DEFAULT_DAY, year: int = DEFAULT_YEAR) -> None:
    "Start solving a day, by default today."
    crate = f"day{day:02}"
    crate_path = Path(crate)

    if crate_path.exists():
        print(f"{crate} already exists.")
        return

    resp = session.get(f"https://adventofcode.com/{year}/day/{day}/input")
    resp.raise_for_status()
    puzzle_input = resp.text

    with open("Cargo.toml") as manifest_f:
        manifest = toml.load(manifest_f)
    if crate not in manifest["workspace"]["members"]:
        manifest["workspace"]["members"].append(crate)
    with open("Cargo.toml", "w") as manifest_f:
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

    fetch_problem(year, day)

    run(("git", "add", crate))
    webbrowser.open_new(f"https://adventofcode.com/{year}/day/{day}")


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


@year_and_day
@arg("level", help="Which part to submit.", choices=(1, 2))
@aliases("a")
@wrap_errors((requests.HTTPError, AssertionError))
def answer(
    answer: str, level: int, day: int = DEFAULT_DAY, year: int = DEFAULT_YEAR
) -> None:
    "Submit your answer!"
    resp = session.post(
        f"https://adventofcode.com/{year}/day/{day}/answer",
        data={"answer": answer, "level": str(level)},
    )
    resp.raise_for_status()

    # Get the main text, removing the "return to" link, and show it in markdown form.
    soup = BeautifulSoup(resp.text, features="html.parser").main
    assert soup is not None, "no main element?"
    return_link = soup.find(href=f"/{year}/day/{day}")
    if isinstance(return_link, Tag):
        return_link.decompose()
    h = html2text.HTML2Text()
    h.ignore_links = True
    print(h.handle(str(soup)).strip())


@aliases("fp")
@in_root_dir
@year_and_day
def fetch_problem(year: int = DEFAULT_YEAR, day: int = DEFAULT_DAY) -> None:
    "Fetch the problem statement."
    resp = session.get(f"https://adventofcode.com/{year}/day/{day}")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, features="html.parser").main
    h = html2text.HTML2Text()
    t = h.handle(str(soup)).strip()
    Path(f"day{day:02}", "problem.md").write_text(t)


def show_session_cookie() -> None:
    "Conquer outer space."
    print(c("Your session cookie:", "yellow"), session.cookies["session"])


def update_pipreqs() -> None:
    "Update the requirements.txt file via pipreqs."
    run(("pipreqs", ".", "--force"))


def main() -> None:
    environ["RUST_BACKTRACE"] = "1"
    environ["RUSTFLAGS"] = "-C target-cpu=native"
    dispatch_commands(
        (
            start_solve,
            answer,
            set_baseline,
            compare,
            criterion,
            iai,
            watch_run,
            do_run,
            run_release,
            run_prototype,
            fetch_problem,
            update_pipreqs,
            show_session_cookie,
        ),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bye!")
