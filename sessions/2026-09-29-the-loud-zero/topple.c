// In-place sandpile stabilisation. h and mask are (R+2)x(C+2) with a 1-cell border
// of mask==0 sink cells. Alternating sweep direction spreads avalanches fast.
#include <stdint.h>
int64_t stabilize(int32_t *h, const uint8_t *mask, int R, int C) {
    const int W = C + 2;
    int64_t total = 0;
    int changed = 1, dir = 0;
    while (changed) {
        changed = 0;
        if (dir == 0) {
            for (int r = 1; r <= R; r++) for (int c = 1; c <= C; c++) {
                int i = r * W + c;
                if (h[i] >= 4 && mask[i]) {
                    int32_t t = h[i] >> 2; h[i] -= t << 2;
                    h[i-1] += t; h[i+1] += t; h[i-W] += t; h[i+W] += t;
                    total += t; changed = 1;
                }
            }
        } else {
            for (int r = R; r >= 1; r--) for (int c = C; c >= 1; c--) {
                int i = r * W + c;
                if (h[i] >= 4 && mask[i]) {
                    int32_t t = h[i] >> 2; h[i] -= t << 2;
                    h[i-1] += t; h[i+1] += t; h[i-W] += t; h[i+W] += t;
                    total += t; changed = 1;
                }
            }
        }
        dir ^= 1;
    }
    for (int i = 0; i < (R + 2) * W; i++) if (!mask[i]) h[i] = 0;
    return total;
}
