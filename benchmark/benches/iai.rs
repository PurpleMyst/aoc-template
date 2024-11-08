macro_rules! doit {
    ($($day:ident: $solve:ident),+$(,)?) => {
        $(use $day::solve as $solve;)+
        iai::main!($($solve),+);
    };
}

doit!(
);
