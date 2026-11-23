// Stateful price-level snapshot reconciliation against a C++17 LevelBook.
// This is an educational L2 snapshot delta processor, not trade matching.
// Returns 0 on success; nonzero on validation/reconciliation failure.
#include "level_book.hpp"
#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <new>

struct MarketBookState {
    std::unique_ptr<marketstream::LevelBook> book{new marketstream::LevelBook(1000)};
    std::map<std::int64_t, std::int64_t> bids;
    std::map<std::int64_t, std::int64_t> asks;
};

extern "C" {
void* ms_state_new() noexcept {
    try { return new MarketBookState(); } catch (...) { return nullptr; }
}
void ms_state_free(void* ptr) noexcept { delete static_cast<MarketBookState*>(ptr); }

int ms_state_replace(
    void* ptr, const std::int64_t* bp, const std::int64_t* bq, std::size_t bn,
    const std::int64_t* ap, const std::int64_t* aq, std::size_t an,
    std::int64_t* out) noexcept {
    if (!ptr || !bp || !bq || !ap || !aq || !out || !bn || !an || bn > 1000 || an > 1000) return 1;
    try {
        auto* state = static_cast<MarketBookState*>(ptr);
        std::map<std::int64_t, std::int64_t> bids, asks;
        for (std::size_t i = 0; i < bn; ++i) {
            if (bp[i] <= 0 || bq[i] <= 0 || !bids.emplace(bp[i], bq[i]).second) return 2;
        }
        for (std::size_t i = 0; i < an; ++i) {
            if (ap[i] <= 0 || aq[i] <= 0 || !asks.emplace(ap[i], aq[i]).second) return 2;
        }
        if (bids.rbegin()->first >= asks.begin()->first) return 3;

        // Prepare replacement off to the side. Failure never partially alters live state.
        auto candidate = std::make_unique<marketstream::LevelBook>(*state->book);
        std::int64_t updates = 0;
        for (const auto& [price, quantity] : state->bids) {
            (void)quantity;
            if (bids.find(price) == bids.end()) {
                if (!candidate->update(true, price, 0)) return 4;
                ++updates;
            }
        }
        for (const auto& [price, quantity] : state->asks) {
            (void)quantity;
            if (asks.find(price) == asks.end()) {
                if (!candidate->update(false, price, 0)) return 4;
                ++updates;
            }
        }
        for (const auto& [price, quantity] : bids) {
            auto it = state->bids.find(price);
            if (it == state->bids.end() || it->second != quantity) {
                if (!candidate->update(true, price, quantity)) return 4;
                ++updates;
            }
        }
        for (const auto& [price, quantity] : asks) {
            auto it = state->asks.find(price);
            if (it == state->asks.end() || it->second != quantity) {
                if (!candidate->update(false, price, quantity)) return 4;
                ++updates;
            }
        }
        const auto top = candidate->top();
        if (top.bid != bids.rbegin()->first || top.ask != asks.begin()->first) return 5;
        state->book.swap(candidate);
        state->bids.swap(bids);
        state->asks.swap(asks);
        out[0] = top.bid;
        out[1] = top.ask;
        out[2] = top.spread;
        out[3] = static_cast<std::int64_t>(top.bid_levels);
        out[4] = static_cast<std::int64_t>(top.ask_levels);
        out[5] = updates;
        return 0;
    } catch (...) { return 6; }
}
}
