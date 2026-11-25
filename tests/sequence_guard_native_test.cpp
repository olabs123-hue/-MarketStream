#include "../engine/sequence_guard.hpp"
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>

int main() {
    using marketstream::SequenceGuard;
    using D = SequenceGuard::Decision;
    SequenceGuard g;
    assert(g.check(0, false).decision == D::needs_snapshot);
    auto first = g.check(0, true);
    assert(first.decision == D::accept && !first.resynchronized);
    // A rejected book must not advance the sequence.
    assert(!g.has_last());
    g.commit(0, first.resynchronized);
    assert(g.has_last() && g.last() == 0 && !g.needs_snapshot());

    assert(g.check(0, true).decision == D::duplicate_or_stale);
    assert(g.check(-1, true).decision == D::duplicate_or_stale);
    auto next = g.check(1, false);
    assert(next.decision == D::accept);
    g.commit(1, next.resynchronized);
    assert(g.last() == 1);

    auto gap = g.check(3, false);
    assert(gap.decision == D::gap && g.needs_snapshot());
    assert(g.gaps_detected() == 1 && g.last() == 1);
    assert(g.check(2, false).decision == D::needs_snapshot);
    auto recover = g.check(4, true);
    assert(recover.decision == D::accept && recover.resynchronized);
    g.commit(4, recover.resynchronized);
    assert(g.resyncs() == 1 && !g.needs_snapshot());
    assert(g.check(5, false).decision == D::accept);
    // Avoid overflow of signed sequence arithmetic near int64 maximum.
    SequenceGuard edge;
    const auto max = std::numeric_limits<std::int64_t>::max();
    auto s = edge.check(max - 1, true);
    assert(s.decision == D::accept);
    edge.commit(max - 1, false);
    assert(edge.check(max, false).decision == D::accept);
    std::cout << "native sequence guard tests passed\n";
}
