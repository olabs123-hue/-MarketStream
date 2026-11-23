#include "../engine/level_book.hpp"
#include <cassert>
#include <iostream>
#include <limits>
#include <stdexcept>
using marketstream::LevelBook;
int main() {
    LevelBook book(2);
    assert(book.top().spread == 0);
    assert(book.update(true, 10000, 4));
    assert(book.update(true, 9999, 7));
    assert(!book.update(true, 9998, 1));
    assert(book.update(false, 10003, 5));
    assert(!book.update(false, 10000, 1));
    assert(!book.update(true, 10003, 1));
    assert(book.top().bid == 10000 && book.top().ask == 10003);
    assert(book.top().spread == 3 && book.top().bid_levels == 2);
    assert(book.update(true, 10000, 9));
    assert(book.update(true, 10000, 0));
    assert(book.top().bid == 9999 && book.top().spread == 4);
    assert(book.update(false, 10003, 0));
    assert(book.top().ask == 0 && book.top().spread == 0);
    try { book.update(true, -1, 1); assert(false); } catch (const std::invalid_argument&) {}
    try { book.update(false, 10200, -1); assert(false); } catch (const std::invalid_argument&) {}
    assert(book.update(false, std::numeric_limits<std::int64_t>::max(), 1));
    assert(book.top().ask == std::numeric_limits<std::int64_t>::max());
    book.clear();
    assert(book.top().bid_levels == 0 && book.top().ask_levels == 0);
    try { LevelBook bad(0); assert(false); } catch (const std::invalid_argument&) {}
    std::cout << "Stateful C++17 level book checks passed\n";
}
