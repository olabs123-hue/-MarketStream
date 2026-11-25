#pragma once
#include <cstdint>

namespace marketstream {

// Stateless event classification is performed before book parsing; commit only
// AFTER the order-book update succeeds. The live Python adapter remains the
// default until native-vs-Python differential tests are complete.
class SequenceGuard {
public:
    enum class Decision { accept, duplicate_or_stale, needs_snapshot, gap };
    struct Check {
        Decision decision;
        bool resynchronized;
    };

    Check check(std::int64_t seq, bool snapshot) noexcept {
        if (seq < 0) return {Decision::duplicate_or_stale, false};
        if (has_last_ && seq <= last_) return {Decision::duplicate_or_stale, false};
        const bool missing = has_last_ && (seq - last_ > 1);
        if (!snapshot) {
            if (missing) {
                ++gaps_;
                needs_snapshot_ = true;
                return {Decision::gap, false};
            }
            if (needs_snapshot_) return {Decision::needs_snapshot, false};
            return {Decision::accept, false};
        }
        return {Decision::accept, has_last_ && (missing || needs_snapshot_)};
    }

    // Caller MUST invoke this only after successfully applying a valid book
    // update. This keeps the sequence state atomic with respect to book state.
    void commit(std::int64_t seq, bool resynchronized) noexcept {
        last_ = seq;
        has_last_ = true;
        needs_snapshot_ = false;
        if (resynchronized) ++resyncs_;
    }

    bool needs_snapshot() const noexcept { return needs_snapshot_; }
    bool has_last() const noexcept { return has_last_; }
    std::int64_t last() const noexcept { return last_; }
    std::uint64_t gaps_detected() const noexcept { return gaps_; }
    std::uint64_t resyncs() const noexcept { return resyncs_; }

private:
    bool has_last_ = false;
    bool needs_snapshot_ = true;
    std::int64_t last_ = 0;
    std::uint64_t gaps_ = 0;
    std::uint64_t resyncs_ = 0;
};

} // namespace marketstream
