"""Summarize manual observations; never extrapolate an estimated runtime."""
import argparse
import csv
from datetime import datetime, timezone


def summarize(rows):
    points = []
    for row in rows:
        try:
            point = (int(row["epoch"]), int(row["battery"]), row["charging"])
            if not 0 <= point[1] <= 100 or point[2] != "0":
                raise ValueError("All samples must be known, not charging")
            points.append(point)
        except (KeyError, ValueError):
            raise ValueError("Use a measurement window with known battery and charging=0 throughout") from None
    points.sort()
    if len(points) < 2 or points[-1][0] <= points[0][0]: raise ValueError("Need two observations at different times")
    if any(b[1] > a[1] for a, b in zip(points, points[1:])): raise ValueError("Battery increased; choose an uninterrupted discharge window")
    hours = (points[-1][0]-points[0][0])/3600
    loss = points[0][1]-points[-1][1]
    return {"start": datetime.fromtimestamp(points[0][0], timezone.utc).isoformat(),
            "hours": round(hours, 2), "percentage_points_lost": loss,
            "percentage_points_per_hour": round(loss/hours, 3), "samples": len(points)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    args = parser.parse_args()
    with open(args.csv, newline="", encoding="utf-8") as stream: rows = list(csv.DictReader(stream))
    try:
        for key, value in summarize(rows).items(): print(f"{key}: {value}")
    except ValueError as exc: parser.error(str(exc))
    print("Coarse battery observations, not proof of suspend. Compare equivalent overnight windows.")
