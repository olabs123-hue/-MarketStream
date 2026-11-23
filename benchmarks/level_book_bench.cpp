// Repeatable single-threaded C++ map price-level update microbenchmark.
// Not a matching engine, wire-to-wire latency, or end-to-end trading benchmark.
#include "../engine/level_book.hpp"
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    std::uint64_t iterations = 200000;
    if (argc == 2) {
        try {
            iterations = std::stoull(argv[1]);
        } catch (const std::exception&) { return 2; }
    }
    if (iterations == 0 || iterations > 10000000) return 2;
    marketstream::LevelBook book(1024);
    book.update(false, 200000, 1);
    for (std::int64_t i=0; i<256; ++i) book.update(true, 100000 + i, 1);
    std::uint64_t checksum = 0;
    const auto start = std::chrono::steady_clock::now();
    for (std::uint64_t i=0; i<iterations; ++i) {
        if (!book.update(true, 100000 + static_cast<std::int64_t>(i % 256), 1 + static_cast<std::int64_t>(i % 100))) return 3;
        checksum += static_cast<std::uint64_t>(book.top().bid);
    }
    const auto end = std::chrono::steady_clock::now();
    const double secs = std::chrono::duration<double>(end-start).count();
    std::cout << "{\"scope\":\"single-threaded in-memory C++17 std::map level replacement and top-of-book read\","
              << "\"iterations\":" << iterations << ",\"elapsed_seconds\":" << secs
              << ",\"updates_per_second\":" << iterations/secs
              << ",\"checksum\":" << checksum << "}\n";
}
