"""Print random combinations (or given numbers) for reading.

Usage: python sample.py [count] [seed]    or    python sample.py 30714...
"""
import random
import sys
import check

S = check.load()


def compose(number):
    return [S[int(d)]["lines"][k] for k, d in enumerate(number)]


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "6"
    if len(arg) == 14:
        nums = [arg]
    else:
        rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else None)
        nums = ["".join(rng.choice("0123456789") for _ in range(14)) for _ in range(int(arg))]
    for num in nums:
        print(f"No. {num[:5]} {num[5:10]} {num[10:]}")
        for d, line in zip(num, compose(num)):
            print(f"  {d}  {line}")
        print()
