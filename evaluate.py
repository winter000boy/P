"""Answers the research question on the held-out test set:
detection rate, false-positive rate, and latency the guard adds per request."""
import statistics
import time

from guard import THRESHOLD, Guard
from train import load_data

test = load_data()["test"]
guard = Guard()
guard.attack_score("warm-up")  # first call loads kernels; keep it out of the timings

scores, latency_ms = [], []
for text in test["text"]:
    start = time.perf_counter()
    scores.append(guard.attack_score(text))
    latency_ms.append((time.perf_counter() - start) * 1000)
labels = test["label"]
attacks, benign = sum(labels), len(labels) - sum(labels)

print(f"Test set: {len(labels)} prompts ({attacks} attacks, {benign} benign)\n")
print("threshold  detection-rate  false-positive-rate")
for t in sorted({0.3, 0.5, 0.7, 0.9, THRESHOLD}):
    tp = sum(s >= t and y == 1 for s, y in zip(scores, labels))
    fp = sum(s >= t and y == 0 for s, y in zip(scores, labels))
    mark = "  <- guard.py THRESHOLD" if t == THRESHOLD else ""
    print(f"   {t:.2f}       {tp / attacks:6.1%}           {fp / benign:6.1%}{mark}")

latency_ms.sort()
print("\nGuard latency per request (classifier, batch size 1, CPU):")
print(f"  mean {statistics.mean(latency_ms):.1f} ms | p50 {latency_ms[len(latency_ms) // 2]:.1f} ms"
      f" | p95 {latency_ms[int(len(latency_ms) * 0.95)]:.1f} ms | max {latency_ms[-1]:.1f} ms")
