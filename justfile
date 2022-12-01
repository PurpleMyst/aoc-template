set shell := ["pwsh.exe", "-c"]
export RUST_BACKTRACE := "1"

default_baseline := "previous"

alias ss := start-solve
start-solve *args:
    python3 ./start_solve.py {{args}}

alias sb := set-baseline
set-baseline day name=default_baseline:
    cargo bench --bench criterion -- "{{day}}" --save-baseline "{{name}}" --verbose

alias cmp := compare
compare day name=default_baseline:
    cargo bench --bench criterion -- "{{day}}" --baseline "{{name}}" --verbose

criterion day name=default_baseline:
    cargo bench --bench criterion -- "{{day}}" --verbose

iai:
    cargo bench --bench iai

alias wr := watch-run
watch-run:
    Set-Location "{{invocation_directory()}}" && cargo watch --clear --exec run

alias r := run
run:
    Set-Location "{{invocation_directory()}}" && cargo run

alias rr := run-release
run-release:
    Set-Location "{{invocation_directory()}}" && cargo run --release

alias rp := run-prototype
run-prototype:
    Set-Location "{{invocation_directory()}}" && cargo watch --clear --shell "python3 prototype.py"
