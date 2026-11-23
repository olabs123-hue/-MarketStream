// Standalone C++17 order-book reference component; not wired into the Python live feed.
#include <algorithm>
#include <cassert>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>

class OrderBook {
    std::map<int, int, std::greater<int>> bids;
    std::map<int, int> asks;
public:
    void update(bool bid, int price_cents, int quantity) {
        if (price_cents <= 0 || quantity < 0) throw std::invalid_argument("invalid level");
        if (bid) {
            if (!quantity) bids.erase(price_cents);
            else bids[price_cents] = quantity;
        } else {
            if (!quantity) asks.erase(price_cents);
            else asks[price_cents] = quantity;
        }
    }
    int best_bid() const { return bids.empty() ? 0 : bids.begin()->first; }
    int best_ask() const { return asks.empty() ? 0 : asks.begin()->first; }
    int spread() const { return (best_bid() && best_ask()) ? best_ask() - best_bid() : 0; }
};

int main() {
    OrderBook b;
    b.update(true, 9999, 5);
    b.update(true, 10000, 2);
    b.update(false, 10003, 4);
    assert(b.best_bid() == 10000 && b.best_ask() == 10003 && b.spread() == 3);
    b.update(true, 10000, 0);
    assert(b.best_bid() == 9999 && b.spread() == 4);
    std::cout << "C++ order-book smoke tests passed\n";
}
