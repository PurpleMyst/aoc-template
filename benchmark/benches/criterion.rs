use std::time::Duration;

use criterion::{criterion_group, criterion_main, Criterion};

macro_rules! doit {
    ($($day:ident),*$(,)?) => {
        pub fn aoc_benchmark(c: &mut Criterion) {
            $(c.bench_function(stringify!($day), |b| b.iter($day::solve));)+
            c.bench_function("all", |b| b.iter(|| ($($day::solve()),+)));
        }

        criterion_group! {
            name = benches;

            config = Criterion::default()
                .significance_level(0.1)
                .sample_size(500)
                .measurement_time(Duration::from_secs(30))
                .warm_up_time(Duration::from_secs(15))
                .noise_threshold(0.05);

            targets = aoc_benchmark
        }

        criterion_main!(benches);
    };
}

doit!(
);
