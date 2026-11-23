#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <stdexcept>

namespace marketstream {

// Stateful educational L2 price-level book: absolute size replaces prior level.
// Prices use integer cents and sizes use integer synthetic units.
// This is not a matching engine, trade tape, or exchange protocol implementation.
class LevelBook {
public:
    struct Top {
        std::int64_t bid = 0;
        std::int64_t ask = 0;
        std::int64_t spread = 0;
        std::size_t bid_levels = 0;
        std::size_t ask_levels = 0;
    };

    explicit LevelBook(std::size_t max_levels = 10000) : max_levels_(max_levels) {
        if (max_levels == 0) throw std::invalid_argument("max_levels must be positive");
    }

    // Returns false if a new level would cross the book or exceed capacity.
    // Invalid price/size inputs throw, without changing the book.
    bool update(bool is_bid, std::int64_t price_cents, std::int64_t size) {
        if (price_cents <= 0 || size < 0) throw std::invalid_argument("invalid level");
        if (is_bid) {
            if (size == 0) { bids_.erase(price_cents); return true; }
            if (!asks_.empty() && price_cents >= asks_.begin()->first) return false;
            if (bids_.find(price_cents) == bids_.end() && bids_.size() >= max_levels_) return false;
            bids_[price_cents] = size;
        } else {
            if (size == 0) { asks_.erase(price_cents); return true; }
            if (!bids_.empty() && price_cents <= bids_.begin()->first) return false;
            if (asks_.find(price_cents) == asks_.end() && asks_.size() >= max_levels_) return false;
            asks_[price_cents] = size;
        }
        return true;
    }

    Top top() const {
        const auto bid = bids_.empty() ? 0 : bids_.begin()->first;
        const auto ask = asks_.empty() ? 0 : asks_.begin()->first;
        return {bid, ask, (bid && ask) ? ask - bid : 0, bids_.size(), asks_.size()};
    }

    void clear() noexcept { bids_.clear(); asks_.clear(); }

private:
    const std::size_t max_levels_;
    std::map<std::int64_t, std::int64_t, std::greater<std::int64_t>> bids_;
    std::map<std::int64_t, std::int64_t> asks_;
};
}
