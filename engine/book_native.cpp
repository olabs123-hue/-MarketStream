#include <cstddef>
#include <cstdint>
#include <limits>
// Strictly bounded native top-of-book calculation; returns 0 on success.
extern "C" int ms_top_of_book(const std::int64_t* bids, const std::int64_t* asks, std::size_t count, std::int64_t* out) {
 if (!bids || !asks || !out || count == 0 || count > 1000) return 1;
 std::int64_t best_bid=0, best_ask=std::numeric_limits<std::int64_t>::max();
 for (std::size_t i=0;i<count;++i) {
  if(bids[i]<=0 || asks[i]<=0) return 2;
  if(bids[i]>best_bid) best_bid=bids[i];
  if(asks[i]<best_ask) best_ask=asks[i];
 }
 if(best_bid>=best_ask) return 3;
 out[0]=best_bid;out[1]=best_ask;out[2]=best_ask-best_bid;
 return 0;
}
