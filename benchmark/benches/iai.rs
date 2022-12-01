macro_rules! doit {
    ($($day:ident: $solve:ident),+$(,)?) => {
        $(use $day::solve as $solve;)+
        iai::main!($($solve),+);
    };
}

doit!(
    day01: day01_solve,
    day02: day02_solve,
    day03: day03_solve,
    day04: day04_solve,
    day05: day05_solve,
    day06: day06_solve,
    day07: day07_solve,
    day08: day08_solve,
    day09: day09_solve,
    day10: day10_solve,
    day11: day11_solve,
    day12: day12_solve,
    day13: day13_solve,
    day14: day14_solve,
    day15: day15_solve,
    day16: day16_solve,
    day17: day17_solve,
    day18: day18_solve,
    day19: day19_solve,
    day20: day20_solve,
    day21: day21_solve,
    day22: day22_solve,
    day23: day23_solve,
    day24: day24_solve,
    day25: day25_solve,
);
