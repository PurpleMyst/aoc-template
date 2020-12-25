import argparse
import datetime
import pathlib
import subprocess
import webbrowser

import requests
import toml

DESCRIPTION = "Start solving an Advent of Code day"

MAIN = """fn main() {{
    let (part1, part2) = {crate}::solve();
    println!("{{}}", part1);
    println!("{{}}", part2);
}}"""

LIB = """#[inline]
pub fn solve() -> (usize, usize) {{
    todo!()
}}"""


def main() -> None:
    now = datetime.datetime.now()
    default_day = now.day
    default_year = now.year

    argp = argparse.ArgumentParser(description=DESCRIPTION)
    argp.add_argument(
        "-d",
        "--day",
        type=int,
        choices=range(1, 25 + 1),
        default=default_day,
        required=False,
    )
    argp.add_argument(
        "-y",
        "--year",
        type=int,
        choices=range(2015, default_year + 1),
        default=default_year,
        required=False,
    )
    argv = argp.parse_args()
    day: int = argv.day
    year: int = argv.year

    with open("session.txt") as session_f:
        session = session_f.read().strip()

    crate = f"day{day:02}"
    crate_path = pathlib.Path(crate)

    if crate_path.exists():
        print(f"{crate} already exists.")
        return

    with open("Cargo.toml") as manifest_f:
        manifest = toml.load(manifest_f)

    manifest["workspace"]["members"].append(crate)

    with open("Cargo.toml", "w") as manifest_f:
        toml.dump(manifest, manifest_f)

    subprocess.run(["cargo", "new", "--bin", crate], check=True)
    subprocess.run(
        [
            "cargo",
            "add",
            "--manifest-path",
            "benchmark/Cargo.toml",
            "--path",
            f"../{crate}",
            crate,
        ],
        check=True,
    )

    src = crate_path / "src"

    with (src / "main.rs").open("w") as main:
        main.write(MAIN.format(crate=crate))

    with (src / "lib.rs").open("w") as lib:
        lib.write(LIB.format(crate=crate))

    with (src / "input.txt").open("w", newline="\n") as input_f:
        resp = requests.get(
            f"https://adventofcode.com/{year}/day/{day}/input",
            cookies={"session": session},
        )
        resp.raise_for_status()
        input_f.write(resp.text)

    subprocess.run(["git", "add", crate], check=True)
    webbrowser.open_new(f"https://adventofcode.com/{year}/day/{day}")


if __name__ == "__main__":
    main()
