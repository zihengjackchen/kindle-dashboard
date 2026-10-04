"""Synthetic design fixture; never connected to the production service by default."""
from app.snapshots import Snapshot, WATCHLIST


def demo_snapshot():
    shared = dict(source="Design sample", as_of="2026-10-01T16:35:00Z", valid_until="2026-10-01T17:00:00Z")
    prices = (5600, 510, 600, 540, 190, 175, 160, 72, 12, 4.20, 65000, 2800)
    changes = (.45, .32, -.21, .86, -.34, .56, 1.21, -.74, .63, -.22, 1.14, -.38)
    return Snapshot.model_validate(dict(
        demo=True,
        weather=dict(**shared, location="San Francisco · sample", unit="F", temperature=64, feels_like=63,
                     condition="Clouds giving way", high=68, low=56, precipitation_percent=10,
                     forecast=[dict(day="FRI", condition="Mostly sunny", high=69, low=55),
                               dict(day="SAT", condition="Morning clouds", high=67, low=56),
                               dict(day="SUN", condition="Clear skies", high=70, low=54)]),
        quotes=[dict(**shared, symbol=symbol, price=price, change=round(price*pct/100, 2), change_percent=pct,
                     session="24h" if index >= 10 else "regular", basis="24h" if index >= 10 else "previous close")
                for index, (symbol, price, pct) in enumerate(zip(WATCHLIST, prices, changes))],
        nas=dict(**shared, name="Home NAS · sample", version="TrueNAS / example metrics", pool_health="ONLINE",
                 used_percent=62, cpu_percent=14, memory_percent=47, alerts=0, uptime="18 days"),
    ))
